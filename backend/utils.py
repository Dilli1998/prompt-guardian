import re
from difflib import SequenceMatcher


INPUT_COST_PER_1K = 0.005
OUTPUT_COST_PER_1K = 0.015


FILLER_PATTERNS = [
    r"\bplease\b",
    r"\bkindly\b",
    r"\bi would like you to\b",
    r"\bcan you\b",
    r"\bcould you\b",
    r"\bmake sure to\b",
]


def count_tokens(text: str) -> int:
    """Approximate tokenizer for demo mode. Good enough for directional savings."""
    if not text:
        return 0
    words = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
    return max(1, int(len(words) * 1.25))


def estimate_cost(input_tokens: int, output_tokens: int = 0) -> float:
    return (input_tokens / 1000 * INPUT_COST_PER_1K) + (
        output_tokens / 1000 * OUTPUT_COST_PER_1K
    )


def rule_based_clean(prompt: str) -> str:
    text = prompt.strip()
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    cleaned_lines = []
    previous = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        # Dedupe at sentence level within the line too, not just whole-line
        # duplicates -- catches copy-paste repeats packed into one paragraph.
        sentences = re.split(r"(?<=[.!?])\s+", line)
        seen_sentences = set()
        deduped_sentences = []
        for sentence in sentences:
            key = sentence.strip().lower()
            if key and key in seen_sentences:
                continue
            if key:
                seen_sentences.add(key)
            deduped_sentences.append(sentence)
        line = " ".join(deduped_sentences).strip()

        if line.lower() != previous:
            cleaned_lines.append(line)
        previous = line.lower()

    return "\n".join(cleaned_lines).strip()


def stub_compress(prompt: str) -> str:
    text = rule_based_clean(prompt)
    replacements = {
        "You are an expert": "Act as an expert",
        "step by step": "stepwise",
        "in a detailed manner": "clearly",
        "provide a comprehensive": "provide a concise",
        "very important": "important",
        "do not forget to": "ensure you",
    }
    for old, new in replacements.items():
        text = re.sub(re.escape(old), new, text, flags=re.IGNORECASE)

    sentences = re.split(r"(?<=[.!?])\s+", text)
    compacted = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence = re.sub(r"\b(in order to)\b", "to", sentence, flags=re.IGNORECASE)
        sentence = re.sub(r"\b(that are|that is)\b", "that", sentence, flags=re.IGNORECASE)
        compacted.append(sentence)

    return " ".join(compacted).strip() or text


def verify_similarity(original: str, compressed: str) -> dict:
    ratio = SequenceMatcher(None, original.lower(), compressed.lower()).ratio()
    original_keywords = set(re.findall(r"\b[a-zA-Z]{5,}\b", original.lower()))
    compressed_keywords = set(re.findall(r"\b[a-zA-Z]{5,}\b", compressed.lower()))
    missing = sorted(original_keywords - compressed_keywords)[:8]
    keyword_score = 1.0
    if original_keywords:
        keyword_score = len(original_keywords & compressed_keywords) / len(original_keywords)
    confidence = int(max(55, min(98, (ratio * 0.35 + keyword_score * 0.65) * 100)))
    return {
        "equivalent": confidence >= 72,
        "confidence": confidence,
        "differences": [
            f"Potentially dropped keyword: {word}" for word in missing
        ],
    }


def response_signature(prompt: str) -> dict:
    text = prompt.lower()
    traits = []
    if any(word in text for word in ["plan", "steps", "stepwise", "step by step"]):
        traits.append("step-by-step plan")
    if any(word in text for word in ["json", "schema", "structured"]):
        traits.append("structured output")
    if any(word in text for word in ["concise", "brief", "short"]):
        traits.append("concise answer")
    if any(word in text for word in ["detailed", "comprehensive", "explain"]):
        traits.append("detailed explanation")
    if any(word in text for word in ["backend", "api", "endpoint", "fastapi"]):
        traits.append("backend/API coverage")
    if any(word in text for word in ["frontend", "ui", "javascript", "browser"]):
        traits.append("frontend/UI coverage")
    if any(word in text for word in ["readme", "docs", "documentation"]):
        traits.append("documentation coverage")
    if any(word in text for word in ["pitch", "demo", "hackathon"]):
        traits.append("demo/pitch coverage")
    return {
        "traits": traits or ["general answer"],
        "preview": "Expected answer includes: " + ", ".join(traits or ["general answer"]),
    }


def stub_answer_impact(original: str, compressed: str) -> dict:
    original_signature = response_signature(original)
    compressed_signature = response_signature(compressed)
    original_traits = set(original_signature["traits"])
    compressed_traits = set(compressed_signature["traits"])
    missing = sorted(original_traits - compressed_traits)
    added = sorted(compressed_traits - original_traits)
    overlap = len(original_traits & compressed_traits)
    total = max(1, len(original_traits | compressed_traits))
    score = int((overlap / total) * 100)
    return {
        "same_answer_likely": score >= 75,
        "score": score,
        "original_preview": original_signature["preview"],
        "compressed_preview": compressed_signature["preview"],
        "risks": [f"Compressed prompt may omit: {item}" for item in missing],
        "added_behavior": added,
    }


def guardian_agent_review(prompt: str, context: str = "") -> dict:
    cleaned = rule_based_clean(prompt)
    compressed = stub_compress(cleaned)
    metrics = savings_summary(prompt, compressed)
    verification = verify_similarity(prompt, compressed)
    answer_impact = stub_answer_impact(prompt, compressed)

    context_blocks = [block.strip() for block in re.split(r"\n{2,}", context) if block.strip()]
    seen_blocks = set()
    duplicate_blocks = []
    for block in context_blocks:
        key = block.lower()
        if key in seen_blocks:
            duplicate_blocks.append(block)
        seen_blocks.add(key)

    actions = []
    if metrics["saved_tokens"] > 0:
        actions.append("compress_prompt")
    if duplicate_blocks:
        actions.append("compact_context")
    if verification["confidence"] < 75 or not answer_impact["same_answer_likely"]:
        actions.append("warn_reviewer")
    if not actions:
        actions.append("allow")

    if "warn_reviewer" in actions:
        decision = "warn"
        risk_level = "medium"
    elif "compact_context" in actions or "compress_prompt" in actions:
        decision = "optimize"
        risk_level = "low"
    else:
        decision = "allow"
        risk_level = "low"

    return {
        "agent_name": "Prompt Guardian Agent",
        "decision": decision,
        "risk_level": risk_level,
        "actions": actions,
        "reasoning_summary": (
            f"Found {metrics['saved_tokens']} prompt tokens available for savings, "
            f"{len(duplicate_blocks)} duplicate context blocks, "
            f"{verification['confidence']}% meaning confidence, and "
            f"{answer_impact['score']}% answer-impact score."
        ),
        "optimized_prompt": compressed,
        "metrics": metrics,
        "verification": verification,
        "answer_impact": answer_impact,
        "duplicate_context_blocks": duplicate_blocks,
    }


def savings_summary(original: str, compressed: str) -> dict:
    original_tokens = count_tokens(original)
    compressed_tokens = count_tokens(compressed)
    saved_tokens = max(0, original_tokens - compressed_tokens)
    original_cost = estimate_cost(original_tokens)
    compressed_cost = estimate_cost(compressed_tokens)
    return {
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "saved_tokens": saved_tokens,
        "savings_percent": round((saved_tokens / original_tokens * 100) if original_tokens else 0, 1),
        "original_cost": round(original_cost, 6),
        "compressed_cost": round(compressed_cost, 6),
        "cost_saved": round(max(0, original_cost - compressed_cost), 6),
    }
