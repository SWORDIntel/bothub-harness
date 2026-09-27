"""Model suitability advisories: premium-tier cost, refusal-prone families, csec."""
import re
from .models import pricing

CSEC_RE = re.compile(
    r'\b(exploit(?:ation|s)?|bypass(?:es|ing)?|side[- ]?channel|brute[- ]?force|'
    r'enumerat\w*|credential\w*|shellcode|payload\w*|rootkit|byovd|malware|ransom|'
    r'privesc|privilege escalation|exfiltrat\w*|lateral movement|pentest|red[- ]?team|'
    r'vulnerab\w*|cve-\d|rce\b|reverse shell|keylogg\w*|botnet|\bc2\b|beacon\w*|'
    r'fuzz\w*|disassembl\w*|decompil\w*|driver\w*|escalat\w*|phish\w*|backdoor|'
    r'auth(?:entication|orization)?[- ]?(?:bypass|attack)|attack\w*|offensive|'
    r'token[- ]?theft|hash[- ]?crack\w*|password[- ]?spray)', re.I)
OPUS_RE = re.compile(r'opus', re.I)
FABLE_RE = re.compile(r'fable', re.I)
GEMINI_RE = re.compile(r'gemini', re.I)
CODE_RE = re.compile(r'\b(implement|write|code|function|class|script|compile|refactor|'
                     r'debug|patch)\b', re.I)


class Advisory:
    """level: 'note' informs, 'warn' should be acknowledged, 'block' requires --yes."""
    def __init__(self, level, message):
        self.level = level
        self.message = message

    def __repr__(self):
        return f'[{self.level.upper()}] {self.message}'


def assess(model_id, text='', csec=False, prices=None):
    """Return suitability advisories for a model/task pair.

    csec: caller-flagged cybersecurity task; text is additionally scanned for
    security vocabulary. Opus/Fable tiers are premium-priced and, for csec,
    either refuse outright or burn budget on planning-style prose.
    """
    prices = prices if prices is not None else pricing()
    info = prices.get(model_id, {})
    advisories = []
    is_csec = csec or bool(CSEC_RE.search(text))
    cost = f"${info['in']}/1M in, ${info['out']}/1M out" if info.get('in') is not None \
        else 'pricing unknown'
    premium = info.get('tier') in ('high', 'premium')
    if info.get('tier') == 'free':
        advisories.append(Advisory('note', f'{model_id} is a free-tier model.'))
    elif premium:
        advisories.append(Advisory('warn', f'{model_id} is {info["tier"]} tier ({cost}).'))
    if FABLE_RE.search(model_id):
        advisories.append(Advisory(
            'warn' if CODE_RE.search(text) else 'note',
            f'{model_id} is a Fable variant: planning/review only, it will not emit '
            'working code. Use it for architecture, not implementation.'))
    if is_csec:
        if OPUS_RE.search(model_id) or FABLE_RE.search(model_id):
            advisories.append(Advisory(
                'block',
                f'{model_id} (Opus/Fable, {cost}) is a poor fit for cybersecurity '
                'work: premium cost plus frontier safety filters that tend to refuse '
                'or sanitize csec output. Prefer claude-sonnet-4.6, gpt-5.6-sol, or '
                'deepseek-v4-pro.'))
        elif GEMINI_RE.search(model_id):
            advisories.append(Advisory(
                'block',
                f'{model_id} (Gemini) refuses security-adjacent prompts outright; '
                'expect a refusal rather than code. Prefer a Claude/GPT model.'))
        elif is_csec and not advisories:
            advisories.append(Advisory(
                'note', f'csec-flagged task on {model_id} ({cost}); '
                'rephrase as generic systems work if the model refuses.'))
    return advisories


def blocked(advisories):
    return any(a.level == 'block' for a in advisories)
