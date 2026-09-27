"""Pricing table parsing and model resolution tests."""
import json
import pytest
from bothub_harness import models

MD = '''# Header
| `model-a` | Owner | 1 000 000 | 128 000 | 3,51 $ | 17,57 $ |
| `model-b:free` | Owner | 65 536 | 65 536 |  |  |
| `model-c` | | | | 0,29 $ | 1,46 $ |
| `model-d` | Owner | 200 000 | 32 000 | 17,57 $ | 87,84 $ |
not a table row
| `model-e` | Owner |  |  | < 0.01 $ |  |
'''


def test_pricing_parse(tmp_path):
    f = tmp_path / 'MODELS.md'
    f.write_text(MD)
    p = models.pricing(f)
    assert p['model-a'] == {'owner': 'Owner', 'context': 1000000, 'max_output': 128000,
                            'in': 3.51, 'out': 17.57, 'tier': 'mid'}
    assert p['model-b:free']['tier'] == 'free'
    assert p['model-c']['in'] == 0.29
    assert p['model-d']['tier'] == 'premium'
    assert p['model-e']['in'] == pytest.approx(0.01)
    assert 'not a table row' not in p


def test_tier_bands():
    assert models.tier('x', 0.5) == 'budget'
    assert models.tier('x', 2.0) == 'mid'
    assert models.tier('x', 7.0) == 'high'
    assert models.tier('x', 20.0) == 'premium'
    assert models.tier('x-exp', 5.0) == 'free'
    assert models.tier('x', None) == 'unknown'


class FakeClient:
    def models(self):
        return {'data': [{'id': 'alpha-1', 'owned_by': 'a', 'created': 1},
                         {'id': 'beta-2', 'owned_by': 'b', 'created': 2},
                         {'id': 'beta-pro', 'owned_by': 'b', 'created': 3}]}


def test_catalog_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(models, 'STATE_DIR', tmp_path)
    cat = models.catalog(FakeClient(), refresh=True)
    assert set(cat) == {'alpha-1', 'beta-2', 'beta-pro'}
    assert json.loads((tmp_path / 'models.json').read_text()) == cat
    assert models.catalog(None) == cat  # served from cache


def test_find_exact_substring_ambiguous(monkeypatch, tmp_path):
    monkeypatch.setattr(models, 'STATE_DIR', tmp_path)
    models.catalog(FakeClient(), refresh=True)
    assert models.find('alpha-1') == ('alpha-1', [])
    assert models.find('lpha') == ('alpha-1', [])
    mid, cands = models.find('beta')
    assert mid is None and set(cands) == {'beta-2', 'beta-pro'}
    assert models.find('nope') == (None, [])
