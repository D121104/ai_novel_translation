import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationChunk:
    unit_index: int
    source_order: int
    source_text: str
    token_count: int


def _tokens(text: str) -> int:
    return len(re.findall(r"\S+", text))


def chunk_text(
    text: str, *, target_tokens: int = 1200, max_tokens: int = 2000
) -> tuple[TranslationChunk, ...]:
    """Split on paragraphs and sentences without duplicating translation input."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        if _tokens(paragraph) <= max_tokens:
            pieces.append(paragraph)
            continue
        sentences = [
            part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", paragraph) if part.strip()
        ]
        current_sentences: list[str] = []
        count = 0
        for sentence in sentences:
            sentence_count = _tokens(sentence)
            if current_sentences and count + sentence_count > max_tokens:
                pieces.append(" ".join(current_sentences))
                current_sentences, count = [], 0
            current_sentences.append(sentence)
            count += sentence_count
        if current_sentences:
            pieces.append(" ".join(current_sentences))

    chunks: list[str] = []
    current: list[str] = []
    count = 0
    for piece in pieces:
        piece_count = _tokens(piece)
        if current and count >= target_tokens:
            chunks.append("\n\n".join(current))
            current, count = [], 0
        current.append(piece)
        count += piece_count
    if current:
        chunks.append("\n\n".join(current))
    return tuple(
        TranslationChunk(index, index, value, _tokens(value))
        for index, value in enumerate(chunks, 1)
    )
