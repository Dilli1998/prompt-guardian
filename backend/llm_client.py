import json
import os

from openai import OpenAI
from openai import OpenAIError
from dotenv import load_dotenv

from .utils import stub_compress, verify_similarity


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
