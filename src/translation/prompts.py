from src.translation.context import TranslationContext


class PromptBuilder:
    """Build the canonical translation prompt for every runtime path."""

    def build(self, context: TranslationContext) -> str:
        return (
            "Translate into natural Vietnamese. Preserve meaning, completeness, and formatting.\n"
            "Do not add facts not present in the source.\n\n"
            f"{context.to_prompt()}"
        )
