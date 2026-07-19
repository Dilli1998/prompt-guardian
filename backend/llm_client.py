import json
import os

from openai import OpenAI
from openai import OpenAIError
from dotenv import load_dotenv

from .utils import (
    guardian_agent_review as stub_guardian_agent_review,
    stub_answer_impact,
    stub_compress,
    verify_similarity,
)


load_dotenv()


def real_mode_enabled() -> bool:
    return os.getenv("USE_REAL_OPENAI") == "1" and bool(os.getenv("OPENAI_API_KEY"))


def _client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def check_openai_connection() -> dict:
    if not real_mode_enabled():
        return {
            "ok": False,
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "error_type": "RealModeDisabled",
            "message": "Set USE_REAL_OPENAI=1 and OPENAI_API_KEY to enable real mode.",
        }

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    try:
        response = _client().responses.create(
            model=model,
            instructions="Reply with exactly: ok",
            input="Connectivity test",
            max_output_tokens=16,
        )
        return {
            "ok": response.output_text.strip().lower() == "ok",
            "configured": True,
            "model": model,
            "response": response.output_text.strip(),
        }
    except OpenAIError as exc:
        return {
            "ok": False,
            "configured": True,
            "model": model,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }


def compress_prompt(prompt: str) -> str:
    if not real_mode_enabled():
        return stub_compress(prompt)

    try:
        response = _client().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=(
                "Compress the user prompt to use fewer tokens while preserving every "
                "instruction, constraint, role, and output format requirement. Return only "
                "the compressed prompt."
            ),
            input=prompt,
        )
        return response.output_text.strip()
    except OpenAIError as exc:
        fallback = stub_compress(prompt)
        return f"{fallback}\n\n[OpenAI fallback: {exc.__class__.__name__}]"


def verify_equivalence(original: str, compressed: str) -> dict:
    if not real_mode_enabled():
        return verify_similarity(original, compressed)

    try:
        response = _client().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=(
                "You judge whether a compressed prompt is functionally equivalent to the "
                "original. Return strict JSON with keys: equivalent boolean, confidence "
                "integer 0-100, differences array of strings."
            ),
            input=f"Original prompt:\n{original}\n\nCompressed prompt:\n{compressed}",
        )
    except OpenAIError as exc:
        data = verify_similarity(original, compressed)
        data["differences"].append(f"OpenAI verification fallback: {exc.__class__.__name__}")
        return data

    try:
        data = json.loads(response.output_text)
    except json.JSONDecodeError:
        data = verify_similarity(original, compressed)
        data["differences"].append("Real verifier returned non-JSON; used fallback parser.")
    return {
        "equivalent": bool(data.get("equivalent", False)),
        "confidence": int(data.get("confidence", 0)),
        "differences": list(data.get("differences", [])),
    }


def compare_answer_impact(original: str, compressed: str) -> dict:
    if not real_mode_enabled():
        return {**stub_answer_impact(original, compressed), "mode": "stub"}

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    instructions = (
        "You compare whether two prompts would cause an LLM to produce materially "
        "the same answer. Return strict JSON with keys: same_answer_likely boolean, "
        "score integer 0-100, original_preview string, compressed_preview string, "
        "risks array of strings, added_behavior array of strings."
    )
    try:
        response = _client().responses.create(
            model=model,
            instructions=instructions,
            input=f"Original prompt:\n{original}\n\nCompressed prompt:\n{compressed}",
        )
        data = json.loads(response.output_text)
        return {
            "same_answer_likely": bool(data.get("same_answer_likely", False)),
            "score": int(data.get("score", 0)),
            "original_preview": str(data.get("original_preview", "")),
            "compressed_preview": str(data.get("compressed_preview", "")),
            "risks": list(data.get("risks", [])),
            "added_behavior": list(data.get("added_behavior", [])),
            "mode": "real-openai",
        }
    except (OpenAIError, json.JSONDecodeError) as exc:
        data = stub_answer_impact(original, compressed)
        data["mode"] = "openai-fallback"
        data["risks"].append(f"OpenAI answer-impact fallback: {exc.__class__.__name__}")
        return data


def run_guardian_agent(prompt: str, context: str = "") -> dict:
    if not real_mode_enabled():
        data = stub_guardian_agent_review(prompt, context)
        data["mode"] = "stub-agent"
        return data

    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    instructions = (
        "You are Prompt Guardian Agent, an autonomous agent that reviews an LLM "
        "prompt and optional accumulated agent context. Decide whether to allow it, "
        "optimize it, warn the user, or block it. Look for prompt verbosity, repeated "
        "instructions, missing constraints after compression, and duplicated context. "
        "Return strict JSON with keys: agent_name string, decision string one of "
        "allow/optimize/warn/block, risk_level string one of low/medium/high, "
        "actions array of short snake_case strings, reasoning_summary string, "
        "optimized_prompt string, duplicate_context_blocks array of strings."
    )
    try:
        response = _client().responses.create(
            model=model,
            instructions=instructions,
            input=f"Prompt:\n{prompt}\n\nAccumulated context:\n{context or '(none)'}",
        )
        data = json.loads(response.output_text)
        fallback = stub_guardian_agent_review(prompt, context)
        optimized_prompt = str(data.get("optimized_prompt") or fallback["optimized_prompt"])
        verification = verify_equivalence(prompt, optimized_prompt)
        answer_impact = compare_answer_impact(prompt, optimized_prompt)
        return {
            "agent_name": str(data.get("agent_name", "Prompt Guardian Agent")),
            "decision": str(data.get("decision", "optimize")),
            "risk_level": str(data.get("risk_level", "low")),
            "actions": list(data.get("actions", fallback["actions"])),
            "reasoning_summary": str(data.get("reasoning_summary", fallback["reasoning_summary"])),
            "optimized_prompt": optimized_prompt,
            "metrics": fallback["metrics"],
            "verification": verification,
            "answer_impact": answer_impact,
            "duplicate_context_blocks": list(
                data.get("duplicate_context_blocks", fallback["duplicate_context_blocks"])
            ),
            "mode": "real-openai-agent",
        }
    except (OpenAIError, json.JSONDecodeError) as exc:
        data = stub_guardian_agent_review(prompt, context)
        data["mode"] = "openai-agent-fallback"
        data["reasoning_summary"] += f" OpenAI agent fallback: {exc.__class__.__name__}."
        return data
