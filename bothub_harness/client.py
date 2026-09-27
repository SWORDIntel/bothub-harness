"""Minimal stdlib client for the Bothub OpenAI-compatible and native APIs."""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENAI_BASE = 'https://openai.bothub.chat/v1'
NATIVE_BASE = 'https://bothub.chat/api/v2'
STATE_DIR = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'bothub-harness'
RATE_INTERVAL = 0.21  # 5 RPS per API key
RETRYABLE = (429, 500, 502, 503, 504)


class ApiError(RuntimeError):
    def __init__(self, status, body):
        self.status = status
        self.body = body
        super().__init__(f'HTTP {status}: {body[:400]}')


def token():
    tok = os.environ.get('BOTHUB_TOKEN')
    if tok:
        return tok
    bashrc = Path.home() / '.bashrc'
    if bashrc.is_file():
        m = re.search(r'^\s*export\s+BOTHUB_TOKEN=(["\']?)(.*?)\1\s*$',
                      bashrc.read_text(), re.M)
        if m:
            return m.group(2)
    raise ValueError('BOTHUB_TOKEN not set in environment or ~/.bashrc')


def resp_dir():
    d = Path(os.environ.get('BOTHUB_RESP', Path.home() / '.local/share/bothub/responses'))
    d.mkdir(parents=True, exist_ok=True)
    return d


def docs_dir():
    return Path(os.environ.get('BOTHUB_DOCS', Path.home() / '.local/share/bothub/docs'))


class Client:
    def __init__(self, bearer=None, openai_base=OPENAI_BASE, native_base=NATIVE_BASE,
                 max_retries=4):
        self.bearer = bearer if bearer is not None else token()
        self.openai_base = openai_base.rstrip('/')
        self.native_base = native_base.rstrip('/')
        self.max_retries = max_retries
        self._last = 0.0

    def _throttle(self):
        wait = RATE_INTERVAL - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def request(self, url, method='GET', payload=None, timeout=600):
        headers = {'Authorization': f'Bearer {self.bearer}'}
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode()
        body = ''
        for attempt in range(self.max_retries + 1):
            self._throttle()
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                return urllib.request.urlopen(req, timeout=timeout)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode('utf-8', 'replace')
                if exc.code not in RETRYABLE or attempt == self.max_retries:
                    raise ApiError(exc.code, body) from exc
            except urllib.error.URLError:
                if attempt == self.max_retries:
                    raise
            time.sleep(min(2 ** attempt, 8))

    def get_json(self, url):
        with self.request(url) as r:
            return json.loads(r.read())

    def post_json(self, url, payload):
        with self.request(url, 'POST', payload) as r:
            return json.loads(r.read())

    # --- OpenAI-compatible gateway ---
    def models(self):
        return self.get_json(f'{self.openai_base}/models')

    def chat(self, model, messages, stream=False, **kw):
        # Bothub accounts are configured needCutMaxTokens=false: never send
        # max_tokens / max_completion_tokens — full natural output is desired.
        kw.pop('max_tokens', None)
        kw.pop('max_completion_tokens', None)
        return self.post_json(f'{self.openai_base}/chat/completions',
                              {'model': model, 'messages': messages, 'stream': stream, **kw})

    def embeddings(self, model, text):
        return self.post_json(f'{self.openai_base}/embeddings', {'model': model, 'input': text})

    def chat_stream(self, model, messages, sink, **kw):
        """POST a streaming chat completion; append raw SSE lines to sink file,
        yield decoded content deltas."""
        kw.pop('max_tokens', None)
        kw.pop('max_completion_tokens', None)
        payload = {'model': model, 'messages': messages, 'stream': True, **kw}
        with self.request(f'{self.openai_base}/chat/completions', 'POST', payload) as r:
            for raw in r:
                line = raw.decode('utf-8', 'replace').rstrip('\n')
                sink.write(line + '\n')
                sink.flush()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    return
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                for choice in chunk.get('choices', []):
                    piece = choice.get('delta', {}).get('content')
                    if piece:
                        yield piece

    # --- Native API ---
    def me(self):
        return self.get_json(f'{self.native_base}/auth/me')
