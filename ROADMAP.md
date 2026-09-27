# bothub-harness roadmap

Reusable Bothub.chat harness — sibling of `nebius_harness`. Stdlib-only
(urllib), token resolved from `$BOTHUB_TOKEN` (env or ~/.bashrc), SSE
streams saved under `$BOTHUB_RESP`, pricing parsed from `$BOTHUB_DOCS/MODELS.md`.

- [x] Stdlib client (OpenAI gateway + native API, 5 RPS throttle, 429/5xx retry)
- [x] `models` — live catalog, 1h disk cache, pricing tiers from MODELS.md
- [x] `select` — persist default model, substring resolution, TTY menu
- [x] `balance` / `me` — subscription balance via `/auth/me`
- [x] `chat` — stdin/arg/file prompts, SSE stream to `$BOTHUB_RESP`, usage report
- [x] `embed` — embeddings endpoint
- [x] Guard: BLOCK on Opus/Fable+Gemini for csec tasks (`--csec` flag or keyword
      scan), cost warnings for high/premium tiers, Fable planning-only note,
      `--yes` override
- [x] `~/.local/bin/bothub` wrapper (self-locating, sources bashrc exports)
- [x] pytest suite (20 tests, FakeClient, no network)

## Usage

```bash
bothub balance                          # tokens + plan
bothub models [--refresh] [--filter q] [--tier budget|mid|high|premium|free]
bothub select claude-sonnet-4.6         # or substring, or bare `select` for menu
bothub chat "prompt" [-m model] [--csec] [--stream] [-y]
echo "prompt" | bothub chat             # stdin
bothub embed "text" -m e5-base-v2
```

Library: `from bothub_harness import Client, assess, catalog, balance`
