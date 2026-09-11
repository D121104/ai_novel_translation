from dataclasses import dataclass


@dataclass(frozen=True)
class GlossaryTerm:
    source: str
    target: str
    locked: bool = True


@dataclass(frozen=True)
class AddressingRule:
    speaker: str
    listener: str
    speaker_pronoun: str
    listener_pronoun: str


@dataclass(frozen=True)
class TranslationContext:
    source: str
    glossary: tuple[GlossaryTerm, ...] = ()
    names: tuple[str, ...] = ()
    addressing: tuple[AddressingRule, ...] = ()
    previous: str = ""
    graph_facts: tuple[str, ...] = ()
    memories: tuple[str, ...] = ()

    def to_prompt(self, max_tokens: int = 4000) -> str:
        sections = [f"SOURCE (highest priority):\n{self.source}"]
        blocks = [
            (
                "LOCKED GLOSSARY",
                "\n".join(
                    f"{term.source} => {term.target}" for term in self.glossary if term.locked
                ),
            ),
            ("CANONICAL NAMES", ", ".join(self.names)),
            (
                "ADDRESSING RULES",
                "\n".join(
                    f"{rule.speaker}->{rule.listener}: "
                    f"{rule.speaker_pronoun}/{rule.listener_pronoun}"
                    for rule in self.addressing
                ),
            ),
            ("PREVIOUS CONTEXT", self.previous),
            ("CURRENT GRAPH FACTS", "\n".join(self.graph_facts)),
            ("MEMORY", "\n".join(self.memories)),
        ]
        budget = len(self.source.split())
        for title, content in blocks:
            if content and budget + len(content.split()) <= max_tokens:
                sections.append(f"{title}:\n{content}")
                budget += len(content.split())
        return "\n\n".join(sections)
