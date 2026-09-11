from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationReport:
    entity_accuracy: float
    relation_f1: float
    recall_at_k: float
    terminology_consistency: float
    hallucination_rate: float
    omission_rate: float
    chars_per_second: float
    cost_per_million_chars: float


def accuracy(predicted: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    return sum(left == right for left, right in zip(predicted, expected, strict=False)) / len(
        expected
    )


def f1(predicted: set[str], expected: set[str]) -> float:
    if not predicted and not expected:
        return 1.0
    true_positive = len(predicted & expected)
    precision = true_positive / len(predicted) if predicted else 0.0
    recall = true_positive / len(expected) if expected else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    return len(set(retrieved[:k]) & relevant) / len(relevant) if relevant else 1.0


def terminology_consistency(outputs: list[str], term: str, expected: str) -> float:
    occurrences = [output for output in outputs if term in output]
    return (
        sum(expected in output for output in occurrences) / len(occurrences) if occurrences else 1.0
    )


def error_rate(found: set[str], expected: set[str], *, hallucination: bool) -> float:
    if hallucination:
        return len(found - expected) / max(len(expected), 1)
    return len(expected - found) / max(len(expected), 1)


def build_report(
    *,
    predicted_entities: list[str],
    expected_entities: list[str],
    predicted_relations: set[str],
    expected_relations: set[str],
    retrieved: list[str],
    relevant: set[str],
    k: int,
    outputs: list[str],
    term: str,
    translation: str,
    expected_terms: set[str],
    elapsed_seconds: float,
    chars: int,
    cost: float,
) -> EvaluationReport:
    found_terms = {item for item in expected_terms if item in translation}
    return EvaluationReport(
        accuracy(predicted_entities, expected_entities),
        f1(predicted_relations, expected_relations),
        recall_at_k(retrieved, relevant, k),
        terminology_consistency(outputs, term, next(iter(expected_terms), "")),
        error_rate(found_terms, expected_terms, hallucination=True),
        error_rate(found_terms, expected_terms, hallucination=False),
        chars / elapsed_seconds if elapsed_seconds else 0.0,
        cost / chars * 1_000_000 if chars else 0.0,
    )
