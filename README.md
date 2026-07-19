# Prompt Guardian

A working prototype: compresses prompts, verifies the compression preserved
meaning using an LLM-as-judge, and simulates a live agent run to show
real-time context-bloat detection and compaction.

## What's real vs. stubbed right now

- **Rule-based cleaning**: fully real, no API needed.
- **Token counting**: real, using `tiktoken` (cl100k_base) as an approximation
  for Claude token counts — close enough to demo credible numbers.
- **LLM compression + verification**: runs in **stub mode** by default (no API
  key needed, deterministic fake-but-plausible output) so you can build/demo
  the whole flow today. Flip one env var to switch to the real OpenAI API.
- **Agent simulation**: the *sequence of steps* is scripted (5 pre-written
  steps), but the context accumulation, token counts, redundancy detection,
  and compaction are all computed for real off that scripted content. Be
  upfront about this in your pitch: "a simulated agent task with real context
  accounting," not "a fully autonomous agent."

## Running it

### Backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Runs in stub mode by default — no API key required, everything works.
Note: run this from the project root (the folder containing `backend/`), not
from inside `backend/` itself — `main.py` uses relative imports and needs to
be run as a package.

### To switch on the real OpenAI API

```bash
export USE_REAL_OPENAI=1
export OPENAI_API_KEY=sk-...
uvicorn backend.main:app --reload --port 8000
```

Optional: `export OPENAI_MODEL=gpt-4.1-mini` to pick a different model.

### Frontend

Just open `frontend/index.html` directly in a browser (it calls
`http://localhost:8000` — make sure the backend is running first). No build
step needed.

## API endpoints

- `GET /health` — check server + whether real API mode is on
- `POST /compress` — body `{"prompt": "..."}`, returns original/cleaned/
  compressed text, token counts, cost estimates, and verification result
- `GET /agent-demo/meta` — lists the 5 scripted agent steps
- `POST /agent-demo/step` — body `{"up_to_step": N}`, returns cumulative
  context stats up to step N, including redundancy detection and compaction

## Before your demo

1. Test with your **own real example prompt**, not just the placeholder —
   judges respond better to a prompt that looks like something they'd
   actually write.
2. If you have time, flip on the real API (`USE_REAL_OPENAI=1`) before judging —
   stub mode is honest and fine as a fallback, but real OpenAI output is more
   convincing live.
3. Rehearse the agent-demo section specifically — the "redundant context
   detected → compacting" moment at step 3 is your wow-moment. Narrate it
   out loud as it happens.
4. Have a backup: screen-record the working demo once, in case live API
   calls or network fail during judging.

## Next things to add if time allows (not required for MVP)

- Persist a history of past compressions in the session
- Support pasting a full chat transcript, not just a single prompt
- Show a running $-saved counter across multiple compressions in a session
- Add a second scripted agent scenario for variety
