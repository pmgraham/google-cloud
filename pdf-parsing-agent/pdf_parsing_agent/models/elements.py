from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class Position(BaseModel):
    x: float
    y: float
    w: float
    h: float


class Element(BaseModel):
    id: str
    type: str
    content: Optional[Union[str, list]] = None
    page: int
    position: Position
    confidence: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PageResult(BaseModel):
    page_number: int
    width: float
    height: float
    classification: str
    elements: list[Element] = Field(default_factory=list)


class DocumentResult(BaseModel):
    """Wraps output in a top-level 'document' key when serialized."""

    source: str
    total_pages: int
    processing_id: str
    pages: list[PageResult] = Field(default_factory=list)

    def model_dump(self, **kwargs) -> dict:
        return {"document": super().model_dump(**kwargs)}
