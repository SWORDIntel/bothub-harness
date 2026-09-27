"""Persisted harness state: the operator's selected default model."""
import json
import os
from .client import STATE_DIR

_SELECTED = STATE_DIR / 'selected_model'


def selected():
    env = os.environ.get('BOTHUB_MODEL')
    if env:
        return env
    if _SELECTED.is_file():
        try:
            return json.loads(_SELECTED.read_text()).get('model')
        except (ValueError, OSError):
            return None
    return None


def select(model_id):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _SELECTED.with_suffix('.tmp')
    tmp.write_text(json.dumps({'model': model_id}))
    tmp.replace(_SELECTED)


def clear():
    _SELECTED.unlink(missing_ok=True)
