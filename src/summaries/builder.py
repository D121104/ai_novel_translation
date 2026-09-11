from src.llm.provider import LLMProvider
from src.summaries.models import StorySummary, SummaryLevel, SummaryProposal


class SummaryBuilder:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def build(
        self,
        summary_id: str,
        level: str,
        source_text: str,
        *,
        start_order: int,
        end_order: int,
    ) -> StorySummary:
        prompt = (
            f"Create a {level} story summary. Preserve narrative causality and list "
            "only explicit structured facts.\n"
            f"story range: {start_order}-{end_order}\nsource:\n{source_text}"
        )
        # The provider validates the proposal; metadata is controlled by the caller.
        proposal, _ = await self._provider.generate_structured(prompt, SummaryProposal)
        return StorySummary(
            summary_id=summary_id,
            level=SummaryLevel(level),
            narrative=proposal.narrative,
            facts=proposal.facts,
            start_order=start_order,
            end_order=end_order,
        )
