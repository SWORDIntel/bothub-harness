"""CLI-level tests with a stubbed client: selection state, gating, balance."""
import pytest
from bothub_harness import cli, state, guard, models as models_mod


class FakeClient:
    def __init__(self, *a, **kw):
        pass

    def models(self):
        return {'data': [{'id': 'claude-opus-4.6', 'owned_by': 'claude'},
                         {'id': 'claude-sonnet-4.6', 'owned_by': 'claude'},
                         {'id': 'gpt-5.6-sol', 'owned_by': 'gpt'}]}

    def me(self):
        return {'subscription': {'balance': 10793114, 'availableBalance': 10793114,
                                 'plan': {'type': 'ELITE', 'price': 5500,
                                          'currency': 'RUB'},
                                 'paymentPlan': 'DEBIT', 'region': 'GLOBAL'},
                'user': {'name': 'Test', 'email': 't@example.com'}}

    def chat(self, model, messages, stream=False, **kw):
        assert 'max_tokens' not in kw
        return {'choices': [{'message': {'content': 'hi'}}],
                'usage': {'total_tokens': 3}}


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv('BOTHUB_TOKEN', 'fake')
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path))
    monkeypatch.setattr(cli, 'Client', FakeClient)
    monkeypatch.setattr(models_mod, 'STATE_DIR', tmp_path)
    monkeypatch.setattr(state, 'STATE_DIR', tmp_path)
    monkeypatch.setattr(state, '_SELECTED', tmp_path / 'selected_model')
    monkeypatch.setattr(guard, 'pricing', lambda: {})
    return tmp_path


def test_balance(capsys):
    cli.main(['balance'])
    out = capsys.readouterr().out
    assert '10,793,114' in out and 'ELITE' in out


def test_select_and_reuse(capsys):
    cli.main(['select', 'gpt-5.6-sol'])
    assert capsys.readouterr().out.strip() == 'gpt-5.6-sol'
    assert state.selected() == 'gpt-5.6-sol'
    cli.main(['chat', 'hello', '--no-stream'])
    assert 'hi' in capsys.readouterr().out


def test_select_substring(capsys):
    cli.main(['select', 'sonnet'])
    assert 'claude-sonnet-4.6' in capsys.readouterr().out


def test_chat_opus_csec_blocked(capsys):
    with pytest.raises(SystemExit):
        cli.main(['chat', 'audit this driver', '--model', 'claude-opus-4.6',
                  '--csec', '--no-stream'])
    assert 'BLOCK' in capsys.readouterr().err


def test_chat_opus_csec_yes_proceeds(capsys):
    cli.main(['chat', 'audit this driver', '--model', 'claude-opus-4.6',
              '--csec', '--yes', '--no-stream'])
    assert 'hi' in capsys.readouterr().out


def test_chat_requires_model():
    with pytest.raises(SystemExit):
        cli.main(['chat', 'hello', '--no-stream'])
