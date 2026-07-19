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

