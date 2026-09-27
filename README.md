# bothub-harness

Reusable CLI + Python library for the [Bothub.chat](https://bothub.chat) API:
OpenAI-compatible chat/embeddings gateway plus the native account API, with
model selection, pricing tiers, balance checks, and a cost/refusal guard for
model choice.

Zero dependencies — stdlib `urllib` only. Python ≥ 3.10.

## Setup

```bash
export BOTHUB_TOKEN="<your JWT>"          # required
export BOTHUB_RESP="$HOME/.local/share/bothub/responses"  # SSE output dir (optional)
export BOTHUB_DOCS="$HOME/.local/share/bothub/docs"       # MODELS.md pricing (optional)
export BOTHUB_MODEL="claude-sonnet-4.6"                   # overrides selection (optional)
```

Run it:

```bash
# from a checkout — wrapper resolves its own path
bin/bothub balance

# or as a module
PYTHONPATH=. python3 -m bothub_harness balance

# or installed
pip install . && bothub balance
```

## Commands

```bash
bothub balance                          # token balance + plan (native /auth/me)
bothub me                               # full account profile JSON
bothub models [--refresh]               # live catalog + pricing tiers (1h cache)
bothub models --filter sonnet --tier mid
bothub select claude-sonnet-4.6         # persist default model
bothub select sonnet                    # unique substring works
bothub select                           # interactive menu (TTY)
bothub select --clear
bothub chat "write a bash port scanner"              # uses selected model
echo "prompt" | bothub chat -m deepseek-v3.2-exp     # stdin prompt
bothub chat -f big_file.py "review this" --no-stream
bothub chat "..." --stream              # SSE → $BOTHUB_RESP/<model>_<ts>.sse
bothub embed "text" -m e5-base-v2
```

`chat` flags: `--system/-s`, `--file/-f`, `--csec`, `--yes/-y`,
`--stream`/`--no-stream`, `--temperature`, `--out`, `--json`.

Default model resolution order: `--model` flag → `$BOTHUB_MODEL` →
persisted selection (`bothub select`).

## Model guard

`bothub_harness.guard.assess()` inspects the model + prompt before sending:

| Situation | Level |
|---|---|
| Opus/Fable model + cybersecurity task (`--csec` or detected vocabulary) | **BLOCK** — premium cost + frontier refusal risk; suggests sonnet/deepseek instead |
| Gemini model + cybersecurity task | **BLOCK** — documented refusals |
| High/premium tier (≥ $5/1M input) | WARN with $/1M pricing |
| Fable model + code request | WARN — planning only, won't emit code |
| Free tier (`:free`, `-exp`) | NOTE |

BLOCK advisories abort non-interactive runs; pass `--yes` to override, or
confirm at the TTY prompt. csec detection scans for security vocabulary
(exploit, bypass, side-channel, byovd, fuzz, privesc, ...).

Per Bothub's `needCutMaxTokens` convention, the harness **never** sends
`max_tokens`/`max_completion_tokens`.

## Library use

```python
from bothub_harness import Client, assess, catalog, pricing, balance
from bothub_harness.guard import blocked

client = Client()                       # bearer from $BOTHUB_TOKEN or ~/.bashrc
print(balance(client))                  # {'balance': ..., 'plan': 'ELITE', ...}
ads = assess('claude-opus-4.6', text='fuzz this parser', csec=True)
if not blocked(ads):
    resp = client.chat('claude-sonnet-4.6',
                       [{'role': 'user', 'content': 'hi'}])
    print(resp['choices'][0]['message']['content'])
```

Streaming to a file:

```python
with open('out.sse', 'w') as sink:
    for piece in client.chat_stream('deepseek-v3.2-exp', messages, sink):
        print(piece, end='')
```

## Layout

```
bothub_harness/
├── client.py    # HTTP, auth, 5 RPS throttle, 429/5xx retry, SSE streaming
├── models.py    # catalog cache + MODELS.md pricing → cost tiers
├── guard.py     # model/task suitability advisories
├── balance.py   # /auth/me → balance/plan
├── state.py     # selected-model persistence
└── cli.py       # argparse CLI
tests/           # pytest, FakeClient, no network
bin/bothub       # self-locating wrapper; symlink into ~/.local/bin
```

## Tests

```bash
python3 -m pytest tests/ -q     # 20 tests, no network needed
```
