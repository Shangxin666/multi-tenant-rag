import pytest
from pydantic import ValidationError

from app.modules.knowledge_bases.schemas import KnowledgeBaseCreate


def test_name_trim_preserves_case() -> None:
    data = KnowledgeBaseCreate(name="  Support  ")
    assert data.name == "Support"
    assert data.description is None


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_invalid_name(name: str) -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(name=name)


def test_description_limit() -> None:
    with pytest.raises(ValidationError):
        KnowledgeBaseCreate(name="Support", description="x" * 5001)
