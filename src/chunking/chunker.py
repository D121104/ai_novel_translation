import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationChunk:
    unit_index: int
    source_order: int
    source_text: str
    token_count: int


def make_story_order(
    chapter_index: int, unit_index: int, *, chapter_stride: int = 1_000_000
) -> int:
    """Build a monotonic novel-wide order from chapter and unit positions."""
    if chapter_index < 0 or unit_index < 0 or chapter_stride <= unit_index:
        raise ValueError("story order inputs are outside the configured range")
    return chapter_index * chapter_stride + unit_index


def _tokens(text: str) -> int:
    cjk = r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
    cjk_count = len(re.findall(cjk, text))
    non_cjk = re.sub(cjk, " ", text)
    return cjk_count + len(re.findall(r"\S+", non_cjk))


def _split_oversized(text: str, max_tokens: int) -> list[str]:
    if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text):
        return [text[index : index + max_tokens] for index in range(0, len(text), max_tokens)]
    words = text.split()
    return [
        " ".join(words[index : index + max_tokens]) for index in range(0, len(words), max_tokens)
    ]


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
            part.strip() for part in re.split(r"(?<=[.!?。！？])\s*", paragraph) if part.strip()
        ]
        current_sentences: list[str] = []
        count = 0
        for sentence in sentences:
            sentence_count = _tokens(sentence)
            if sentence_count > max_tokens:
                if current_sentences:
                    pieces.append(" ".join(current_sentences))
                    current_sentences, count = [], 0
                pieces.extend(_split_oversized(sentence, max_tokens))
                continue
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
