from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .llm_client import (
    check_openai_connection,
    compare_answer_impact,
    compress_prompt,
    real_mode_enabled,
    verify_equivalence,
)
from .utils import count_tokens, guardian_agent_review, rule_based_clean, savings_summary


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

app = FastAPI(title="Prompt Guardian", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


class CompressRequest(BaseModel):
    prompt: str = Field(min_length=1)


class AgentStepRequest(BaseModel):
    step: int = Field(ge=1, le=5)


class AnswerImpactRequest(BaseModel):
    original: str = Field(min_length=1)
    compressed: str = Field(min_length=1)


class GuardianAgentRequest(BaseModel):
    prompt: str = Field(min_length=1)
    context: str = ""


AGENT_STEPS = [
    {
        "title": "Read project brief",
        "content": "Prompt Guardian compresses verbose prompts and verifies meaning preservation.",
    },
    {
        "title": "Inspect implementation target",
        "content": "The backend should expose /compress, /agent-demo/meta, and /agent-demo/step.",
    },
    {
        "title": "Re-read project brief",
        "content": "Prompt Guardian compresses verbose prompts and verifies meaning preservation.",
    },
    {
        "title": "Plan compaction",
        "content": "Duplicate context blocks should be removed before the next model call.",
    },
    {
        "title": "Summarize result",
        "content": "The demo shows token growth, redundancy detection, and compacted savings.",
    },
]


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "real_openai_mode": real_mode_enabled()}


@app.get("/openai-check")
def openai_check():
    return check_openai_connection()


@app.post("/compress")
def compress(request: CompressRequest):
    cleaned = rule_based_clean(request.prompt)
    compressed = compress_prompt(cleaned)
    verification = verify_equivalence(request.prompt, compressed)
    used_fallback = "[OpenAI fallback:" in compressed or any(
        "OpenAI verification fallback:" in item for item in verification["differences"]
    )
    return {
        "original": request.prompt,
        "cleaned": cleaned,
        "compressed": compressed,
        "metrics": savings_summary(request.prompt, compressed),
        "verification": verification,
        "mode": "openai-fallback" if used_fallback else "real-openai" if real_mode_enabled() else "stub",
    }


@app.post("/answer-impact")
def answer_impact(request: AnswerImpactRequest):
    return compare_answer_impact(request.original, request.compressed)


@app.post("/guardian-agent/review")
def guardian_agent(request: GuardianAgentRequest):
    return guardian_agent_review(request.prompt, request.context)


@app.get("/agent-demo/meta")
def agent_demo_meta():
    return {"steps": [{"step": index + 1, "title": item["title"]} for index, item in enumerate(AGENT_STEPS)]}


@app.post("/agent-demo/step")
def agent_demo_step(request: AgentStepRequest):
    selected = AGENT_STEPS[: request.step]
    seen = set()
    duplicates = []
    compacted = []
    context_tokens = 0

    for index, item in enumerate(selected, start=1):
        content = item["content"]
        context_tokens += count_tokens(content)
        key = content.lower().strip()
        if key in seen:
            duplicates.append({"step": index, "title": item["title"], "content": content})
            continue
        seen.add(key)
        compacted.append(content)

    compacted_tokens = sum(count_tokens(content) for content in compacted)
    saved_tokens = max(0, context_tokens - compacted_tokens)
    return {
        "current_step": request.step,
        "log": selected,
        "context_tokens": context_tokens,
        "compacted_context_tokens": compacted_tokens,
        "saved_tokens": saved_tokens,
        "redundant_steps_detected": duplicates,
        "savings_percent": round((saved_tokens / context_tokens * 100) if context_tokens else 0, 1),
    }
