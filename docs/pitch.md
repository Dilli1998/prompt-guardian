# Prompt Guardian Pitch

Prompt Guardian is a Codex-built developer tool for Codex-style agent workflows. It compresses verbose prompts, verifies that meaning was preserved with a second model pass, and demonstrates live context-bloat detection in a coding-agent simulation.

The demo has two flows. First, paste a verbose prompt and watch Prompt Guardian produce a shorter version with token and cost savings. Second, run the agent demo and see a duplicate context block detected, compacted, and measured.

The hackathon version is intentionally scoped: no auth, no database, and stub mode works without any API key. If an OpenAI key is available, the same backend can switch to real model calls with `USE_REAL_OPENAI=1`.

