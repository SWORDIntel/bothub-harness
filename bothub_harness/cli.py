"""Bothub harness CLI: model selection, balance, guarded chat and embeddings."""
import argparse
import json
import sys
import time
from pathlib import Path

from .client import Client, ApiError, STATE_DIR, resp_dir
from . import guard, models as models_mod, state
from .balance import balance, profile


def _emit(advisories):
    for a in advisories:
        print(f'{a.level.upper()}: {a.message}', file=sys.stderr)


def _gate(model_id, text, csec, yes):
    advisories = guard.assess(model_id, text=text, csec=csec)
    _emit(advisories)
    if not guard.blocked(advisories):
        return
    if yes:
        return
    if sys.stdin.isatty():
        reply = input('Advisory level BLOCK — proceed anyway? [y/N] ')
        if reply.strip().lower() in ('y', 'yes'):
            return
    raise ValueError('Blocked by advisory; rerun with --yes to override')


def _resolve(client, query):
    mid, candidates = models_mod.find(query, client)
    if mid:
        return mid
    if not candidates:
        raise ValueError(f'No model matching {query!r}')
    if sys.stdin.isatty():
        for i, c in enumerate(candidates, 1):
            print(f'  {i}. {c}')
        reply = input(f'Select 1-{len(candidates)}: ').strip()
        if reply.isdigit() and 1 <= int(reply) <= len(candidates):
            return candidates[int(reply) - 1]
        raise ValueError('No selection made')
    raise ValueError(f'Ambiguous model {query!r}; candidates: {", ".join(candidates[:20])}')


def _fmt_price(info):
    if info.get('in') is None:
        return '-'
    return f"${info['in']}/${info.get('out', '?')}"


def cmd_models(args):
    client = Client()
    merged = models_mod.merged(client, refresh=args.refresh)
    rows = sorted(merged.items())
    if args.filter:
        q = args.filter.lower()
        rows = [(i, m) for i, m in rows if q in i.lower()]
    if args.tier:
        rows = [(i, m) for i, m in rows if m.get('tier') == args.tier]
    if args.json:
        print(json.dumps(dict(rows), indent=2, sort_keys=True))
        return
    for mid, info in rows:
        print(f"{mid:44} {info.get('tier') or '?':8} {_fmt_price(info):>16}  "
              f"{info.get('owner') or ''}")
    print(f'-- {len(rows)} models', file=sys.stderr)


def cmd_select(args):
    client = Client()
    if args.clear:
        state.clear()
        print('selection cleared')
        return
    query = args.model
    if not query:
        if not sys.stdin.isatty():
            raise ValueError('Pass a model id (non-interactive select)')
        merged = models_mod.merged(client)
        cur = state.selected()
        for i, (mid, info) in enumerate(sorted(merged.items()), 1):
            mark = '*' if mid == cur else ' '
            print(f'{mark} {i:3}. {mid:44} {info.get("tier") or "?":8} {_fmt_price(info)}')
        reply = input('Select number or model id: ').strip()
        if not reply:
            raise ValueError('No selection made')
        query = list(sorted(merged))[int(reply) - 1] if reply.isdigit() else reply
    mid = _resolve(client, query)
    state.select(mid)
    _emit(guard.assess(mid))
    print(mid)


def cmd_balance(args):
    client = Client()
    if args.json:
        print(json.dumps(balance(client), indent=2))
        return
    b = balance(client)
    print(f"user:      {b['user']} <{b['email']}>")
    print(f"plan:      {b['plan']} ({b['plan_price']} {b['currency']}, {b['payment']})")
    print(f"balance:   {b['balance']:,} tokens")
    print(f"available: {b['available']:,} tokens")


def cmd_me(args):
    print(json.dumps(profile(Client()), indent=2))


def cmd_chat(args):
    client = Client()
    model = args.model or state.selected()
    if not model:
        raise ValueError('No model: pass --model or run `bothub select`')
    model = _resolve(client, model)
    text = ' '.join(args.prompt) if args.prompt else ''
    if args.file:
        text += Path(args.file).read_text()
    if not text and not sys.stdin.isatty():
        text += sys.stdin.read()
    if not text.strip():
        raise ValueError('Empty prompt')
    messages = ([{'role': 'system', 'content': args.system}] if args.system else [])
    messages.append({'role': 'user', 'content': text})
    _gate(model, text, args.csec, args.yes)
    kw = {}
    if args.temperature is not None:
        kw['temperature'] = args.temperature
    if args.stream or (sys.stdout.isatty() and not args.no_stream):
        out = Path(args.out) if args.out else \
            resp_dir() / f'{model.replace("/", "_")}_{int(time.time())}.sse'
        with out.open('w') as sink:
            for piece in client.chat_stream(model, messages, sink, **kw):
                print(piece, end='', flush=True)
        print(f'\n-- saved: {out}', file=sys.stderr)
        return
    resp = client.chat(model, messages, **kw)
    if args.json:
        print(json.dumps(resp, indent=2))
        return
    print(resp['choices'][0]['message']['content'])
    usage = resp.get('usage')
    if usage:
        print(f"-- usage: {usage}", file=sys.stderr)


def cmd_embed(args):
    client = Client()
    model = args.model or 'e5-base-v2'
    resp = client.embeddings(model, ' '.join(args.text))
    print(json.dumps(resp, indent=2) if args.json else
          json.dumps(resp['data'][0]['embedding']))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='bothub', description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)

    p = sub.add_parser('models', help='list models with pricing tiers')
    p.add_argument('--refresh', action='store_true', help='bypass the 1h cache')
    p.add_argument('--filter', help='substring filter')
    p.add_argument('--tier', choices=['free', 'budget', 'mid', 'high', 'premium', 'unknown'])
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_models)

    p = sub.add_parser('select', help='persist the default model')
    p.add_argument('model', nargs='?', help='model id or unique substring (omit for menu)')
    p.add_argument('--clear', action='store_true')
    p.set_defaults(fn=cmd_select)

    p = sub.add_parser('balance', help='account balance and plan')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_balance)

    p = sub.add_parser('me', help='full account profile JSON')
    p.set_defaults(fn=cmd_me)

    p = sub.add_parser('chat', help='send a chat completion')
    p.add_argument('prompt', nargs='*', help='prompt text (else stdin/--file)')
    p.add_argument('--model', '-m', help='override selected model')
    p.add_argument('--system', '-s', help='system message')
    p.add_argument('--file', '-f', help='append file contents to the prompt')
    p.add_argument('--csec', action='store_true', help='flag task as cybersecurity')
    p.add_argument('--yes', '-y', action='store_true', help='override blocking advisories')
    p.add_argument('--stream', action='store_true', help='force SSE streaming')
    p.add_argument('--no-stream', action='store_true', help='force single response')
    p.add_argument('--temperature', type=float)
    p.add_argument('--out', help='SSE output file (default: $BOTHUB_RESP/<model>_<ts>.sse)')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_chat)

    p = sub.add_parser('embed', help='embed text')
    p.add_argument('text', nargs='+')
    p.add_argument('--model', '-m')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_embed)

    args = parser.parse_args(argv)
    try:
        args.fn(args)
    except (ValueError, KeyError, OSError, ApiError) as exc:
        parser.exit(1, f'Blocked: {exc}\n')


if __name__ == '__main__':
    main()
