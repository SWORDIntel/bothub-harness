"""Guard advisory tests: opus/csec blocking, gemini refusal, fable planning."""
from bothub_harness import guard
from bothub_harness.guard import Advisory, assess, blocked

PRICES = {
    'claude-opus-4.6': {'in': 3.51, 'out': 17.57, 'tier': 'mid'},
    'claude-opus-4.1': {'in': 17.57, 'out': 87.84, 'tier': 'premium'},
    'claude-sonnet-4.6': {'in': 2.11, 'out': 10.54, 'tier': 'mid'},
    'claude-fable-5': {'in': 7.03, 'out': 35.13, 'tier': 'high'},
    'gemini-3.7-flash': {'in': 0.31, 'out': 1.54, 'tier': 'budget'},
    'gpt-5.6-sol': {'in': 1.0, 'out': 4.0, 'tier': 'mid'},
    'deepseek-v3.2-exp': {'in': 0.32, 'out': 0.48, 'tier': 'free'},
}


def test_opus_csec_flag_blocks():
    a = assess('claude-opus-4.6', csec=True, prices=PRICES)
    assert blocked(a)


def test_opus_csec_keywords_block():
    a = assess('claude-opus-4.6', text='write a driver bypass exploit', prices=PRICES)
    assert blocked(a)


def test_opus_benign_warns_cost_only():
    a = assess('claude-opus-4.1', text='summarize this RFC', prices=PRICES)
    assert not blocked(a)
    assert any(x.level == 'warn' for x in a)


def test_sonnet_csec_not_blocked():
    a = assess('claude-sonnet-4.6', csec=True, prices=PRICES)
    assert not blocked(a)


def test_gemini_csec_blocks():
    a = assess('gemini-3.7-flash', text='fuzz the parser for crashes', prices=PRICES)
    assert blocked(a)


def test_gemini_benign_ok():
    a = assess('gemini-3.7-flash', text='write a sorting function', prices=PRICES)
    assert not blocked(a)


def test_fable_code_request_warns():
    a = assess('claude-fable-5', text='implement a parser in C', prices=PRICES)
    assert any('planning' in x.message for x in a)


def test_free_tier_note():
    a = assess('deepseek-v3.2-exp', text='hello', prices=PRICES)
    assert any(x.level == 'note' for x in a)


def test_unknown_model_no_crash():
    assert isinstance(assess('never-heard-of-it', prices={}), list)


def test_advisory_repr():
    assert '[WARN]' in repr(Advisory('warn', 'x'))
