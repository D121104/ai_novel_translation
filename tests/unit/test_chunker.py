from src.chunking.chunker import chunk_text


def test_chunking_is_deterministic_and_monotonic() -> None:
    source = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    first = chunk_text(source, target_tokens=3, max_tokens=10)
    second = chunk_text(source, target_tokens=3, max_tokens=10)
    assert first == second
    assert [chunk.source_order for chunk in first] == list(range(1, len(first) + 1))
    assert "First paragraph." in first[0].source_text


def test_chunking_does_not_duplicate_source() -> None:
    source = "One sentence.\n\nTwo sentence."
    chunks = chunk_text(source, target_tokens=100)
    assert "\n\n".join(chunk.source_text for chunk in chunks) == source
