from src.summaries.models import StorySummary, SummaryLevel, visible_summaries


def summary(summary_id: str, end: int) -> StorySummary:
    return StorySummary(
        summary_id=summary_id,
        level=SummaryLevel.CHAPTER,
        narrative=f"Summary {summary_id}",
        start_order=end,
        end_order=end,
    )


def test_summary_retrieval_excludes_future_and_is_bounded() -> None:
    summaries = [summary(str(index), index) for index in range(1, 101)]
    result = visible_summaries(summaries, as_of_order=50, limit=3)
    assert [item.end_order for item in result] == [50, 49, 48]


def test_summary_contains_narrative_and_structured_facts() -> None:
    item = summary("chapter-1", 1)
    assert item.narrative
    assert item.facts == []
