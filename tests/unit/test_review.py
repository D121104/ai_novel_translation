import pytest
from pydantic import ValidationError

from apps.api.schemas import ReviewAction


def test_review_action_is_validated() -> None:
    action = ReviewAction(action="confirm", object_type="entity", object_id="e1")
    assert action.action == "confirm"
    with pytest.raises(ValidationError):
        ReviewAction(action="delete", object_type="entity", object_id="e1")
