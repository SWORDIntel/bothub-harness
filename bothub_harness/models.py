"""Model catalog: live list with local cache, plus pricing parsed from MODELS.md."""
import json
import re
import time
from .client import STATE_DIR, docs_dir

CACHE_TTL = 3600
_ROW = re.compile(r'^\|\s*`([^`]+)`\s*(?:\|([^|]*))?(?:\|([^|]*))?(?:\|([^|]*))?'
                  r'(?:\|([^|]*))?(?:\|([^|]*))?\|?\s*$')


def _num(s):
    if s is None:
        return None
    s = s.strip().replace('\xa0', '').replace(' ', '').replace(',', '.').lstrip('<')
    s = s.replace('$', '').strip()
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return int(v) if v == int(v) and '.' not in s else v


def tier(model_id, in_price):
    if ':free' in model_id or model_id.endswith('-exp') or '-exp:' in model_id:
        return 'free'
    if in_price is None:
        return 'unknown'
    if in_price < 1:
        return 'budget'
    if in_price < 5:
        return 'mid'
    if in_price < 15:
        return 'high'
    return 'premium'


def pricing(path=None):
    """Parse MODELS.md pricing rows -> {id: {owner, context, max_output, in, out, tier}}."""
    path = path or docs_dir() / 'MODELS.md'
    table = {}
    if not path.is_file():
        return table
    for line in path.read_text(encoding='utf-8').splitlines():
        m = _ROW.match(line)
        if not m or m.group(1) in ('Model', '---') or set(m.group(1)) <= {'-'}:
            continue
        mid, owner, ctx, out, pin, pout = (g.strip() if g else '' for g in m.groups())
        in_price, out_price = _num(pin), _num(pout)
        table[mid] = {'owner': owner or None, 'context': _num(ctx), 'max_output': _num(out),
                      'in': in_price, 'out': out_price, 'tier': tier(mid, in_price)}
    return table


def catalog(client=None, refresh=False):
    """{id: {owned_by, created}} from the live /models endpoint with a disk cache."""
    cache = STATE_DIR / 'models.json'
    if not refresh and cache.is_file() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        return json.loads(cache.read_text())
    if client is None:
        if cache.is_file():
            return json.loads(cache.read_text())
        return {}
    data = client.models().get('data', [])
    result = {m['id']: {k: m.get(k) for k in ('owned_by', 'created')} for m in data if 'id' in m}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, sort_keys=True))
    tmp.replace(cache)
    return result


def merged(client=None, refresh=False):
    """Join live catalog with MODELS.md pricing: {id: {owned_by, in, out, tier, ...}}."""
    cat = catalog(client, refresh=refresh)
    prices = pricing()
    out = {}
    for mid, meta in cat.items():
        out[mid] = {**meta, **prices.get(mid, {'tier': tier(mid, None)})}
    for mid, p in prices.items():
        out.setdefault(mid, {**p, 'listed': False})
    return out


def find(query, client=None):
    """Resolve a model id: exact match, else unique substring, else candidate list."""
    ids = sorted(catalog(client) or pricing())
    if query in ids:
        return query, []
    q = query.lower()
    hits = [i for i in ids if q in i.lower()]
    if len(hits) == 1:
        return hits[0], []
    return None, hits
