import pytest
from pydantic import ValidationError

from apps.api.schemas import Paginated


def test_pagination_validation() -> None:
    page = Paginated[int](items=[1], offset=0, limit=20, total=1)
    assert page.items == [1]
    with pytest.raises(ValidationError):
        Paginated[int](items=[], offset=-1, limit=20, total=0)
