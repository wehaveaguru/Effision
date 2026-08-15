from app.pipeline.parse import parse_document
from app.pipeline.segregate import segregate_document

SAMPLE = "data/sample_docs/camber_bolt_specsheet.txt"


def test_parse_offline_reads_txt():
    doc = parse_document(SAMPLE)
    assert doc.file_name == "camber_bolt_specsheet.txt"
    assert "Camber" in doc.raw_text


def test_segregate_offline_heuristic_extracts_known_fields():
    doc = parse_document(SAMPLE)
    result = segregate_document(doc)

    field_names = {f.field_name for f in result.fields}
    assert "diameter_mm" in field_names
    assert "material" in field_names
    assert "supplier" in field_names

    diameter_field = next(f for f in result.fields if f.field_name == "diameter_mm")
    assert diameter_field.field_value == 8.0
    assert 0 < diameter_field.confidence <= 1