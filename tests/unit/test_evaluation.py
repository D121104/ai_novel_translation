from src.evaluation.metrics import accuracy, error_rate, f1, recall_at_k


def test_evaluation_metrics() -> None:
    assert accuracy(["a", "b"], ["a", "b"]) == 1.0
    assert f1({"a"}, {"a", "b"}) == 2 / 3
    assert recall_at_k(["future", "past"], {"past"}, 2) == 1.0
    assert error_rate({"a", "x"}, {"a"}, hallucination=True) == 1.0
