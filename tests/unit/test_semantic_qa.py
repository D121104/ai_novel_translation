import pytest

from src.llm.provider import LLMResponse
from src.qa.semantic import SemanticQA
from src.translation.context import TranslationContext


class Provider:
    async def generate_structured(self, prompt, schema):
        return schema.model_validate(
            {
                "passed": False,
                "score": 0.6,
                "issues": [{"code": "omission", "message": "missing detail"}],
            }
        ), LLMResponse("{}", "qa-model", 1, 1)


@pytest.mark.asyncio
async def test_semantic_qa_returns_structured_report_with_context() -> None:
    report = await SemanticQA(Provider()).run(
        "Lan enters.", "Lan bước vào.", TranslationContext(source="Lan enters.")
    )

    assert report.passed is False
    assert report.score == 0.6
    assert report.issues[0].code == "omission"
