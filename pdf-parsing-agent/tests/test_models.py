from pdf_parsing_agent.models.elements import Position, Element, PageResult, DocumentResult


def test_position_creation():
    pos = Position(x=72.0, y=50.0, w=468.0, h=24.0)
    assert pos.x == 72.0
    assert pos.w == 468.0


def test_element_creation():
    elem = Element(
        id="elem_001",
        type="header",
        content="Test Header",
        page=1,
        position=Position(x=72.0, y=50.0, w=468.0, h=24.0),
        confidence=0.95,
        metadata={"font": "Helvetica-Bold", "font_size": 18, "reading_order": 1},
    )
    assert elem.type == "header"
    assert elem.content == "Test Header"
    assert elem.confidence == 0.95


def test_element_with_null_content():
    elem = Element(
        id="elem_002",
        type="image",
        content=None,
        page=1,
        position=Position(x=0, y=0, w=100, h=100),
        confidence=1.0,
        metadata={"file_path": "output/img.png"},
    )
    assert elem.content is None


def test_element_with_table_content():
    table_data = [["Region", "Revenue"], ["North", "$1.2M"]]
    elem = Element(
        id="elem_003",
        type="table",
        content=table_data,
        page=1,
        position=Position(x=72, y=200, w=468, h=150),
        confidence=0.91,
        metadata={"rows": 2, "columns": 2, "has_header_row": True},
    )
    assert elem.content == table_data


def test_page_result():
    page = PageResult(
        page_number=1,
        width=612.0,
        height=792.0,
        classification="text_only",
        elements=[],
    )
    assert page.page_number == 1
    assert page.elements == []


def test_document_result():
    doc = DocumentResult(
        source="test.pdf",
        total_pages=1,
        processing_id="abc-123",
        pages=[],
    )
    assert doc.source == "test.pdf"
    assert doc.pages == []


def test_document_result_serialization():
    elem = Element(
        id="elem_001",
        type="header",
        content="Hello",
        page=1,
        position=Position(x=72, y=50, w=468, h=24),
        confidence=0.95,
        metadata={"font": "Helvetica", "reading_order": 1},
    )
    page = PageResult(
        page_number=1,
        width=612.0,
        height=792.0,
        classification="text_only",
        elements=[elem],
    )
    doc = DocumentResult(
        source="test.pdf",
        total_pages=1,
        processing_id="test-uuid",
        pages=[page],
    )
    data = doc.model_dump()
    assert data["document"]["source"] == "test.pdf"
    assert data["document"]["pages"][0]["elements"][0]["type"] == "header"
