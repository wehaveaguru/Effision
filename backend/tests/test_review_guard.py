from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ParsedDocument, SegregatedField, SegregationResult
from app.pipeline.graph_model import write_segregation_result, write_source_document

client = TestClient(app)


def _seed_one_proposed_edge():
    doc = ParsedDocument(file_name="test.txt", file_type="txt", raw_text="Diameter: 8mm")
    doc_id = write_source_document(doc)
    result = SegregationResult(
        file_name="test.txt",
        product_label="Test Bolt",
        fields=[
            SegregatedField(
                field_name="diameter_mm", field_value=8.0, node_type_hint="Attribute", confidence=0.9
            )
        ],
    )
    written = write_segregation_result(result, doc_id)
    return written["edges"][0]


def test_pipeline_never_writes_approved():
    edge = _seed_one_proposed_edge()
    assert edge["status"] == "proposed"


def test_approved_graph_excludes_freshly_written_edges():
    _seed_one_proposed_edge()
    res = client.get("/graph")  # default status=approved
    assert res.json()["edges"] == []


def test_review_endpoint_can_approve():
    edge = _seed_one_proposed_edge()
    res = client.post(f"/edges/{edge['id']}/review", json={"decision": "approved", "reviewed_by": "alice"})
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    # now it should show up in the default (approved) graph view
    graph_res = client.get("/graph")
    assert len(graph_res.json()["edges"]) == 1


def test_review_endpoint_can_reject():
    edge = _seed_one_proposed_edge()
    res = client.post(f"/edges/{edge['id']}/review", json={"decision": "rejected"})
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"


def test_review_unknown_edge_404s():
    res = client.post("/edges/does-not-exist/review", json={"decision": "approved"})
    assert res.status_code == 404


def test_review_queue_lists_proposed_edges():
    _seed_one_proposed_edge()
    res = client.get("/edges/queue")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["edge"]["status"] == "proposed"
    assert body[0]["source_document"]["file_name"] == "test.txt"