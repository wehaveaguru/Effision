from app.pipeline.retrieve import reciprocal_rank_fusion


def test_rrf_favors_docs_ranked_high_in_both_lists():
    fts = ["a", "b", "c"]
    vec = ["b", "a", "c"]
    scores = reciprocal_rank_fusion([fts, vec])
    # 'a' and 'b' both appear in the top two of each list, 'c' is last in both
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["c"]


def test_rrf_doc_only_in_one_list_still_scored():
    fts = ["a", "b"]
    vec = ["c"]
    scores = reciprocal_rank_fusion([fts, vec])
    assert set(scores.keys()) == {"a", "b", "c"}
    assert scores["c"] > 0


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([[], []]) == {}