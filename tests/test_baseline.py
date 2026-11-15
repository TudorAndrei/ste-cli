import json

import pytest

from ste import baseline


def test_counted_fingerprints_and_stale_scope():
    accepted = baseline.Set()
    accepted.add("a.md", "STE-4.2", "isn't")
    accepted.add("a.md", "STE-4.2", "isn't")
    accepted.add("b.md", "STE-5.1", "one  two\nthree")
    assert accepted.take("a.md", "STE-4.2", "isn't")
    assert accepted.stale({"a.md"}) == 1
    assert accepted.take("a.md", "STE-4.2", "isn't")
    assert not accepted.take("a.md", "STE-4.2", "isn't")
    assert accepted.stale({"a.md"}) == 0
    assert accepted.take("b.md", "STE-5.1", "one two three")


def test_load_legacy_entries_and_errors(tmp_path):
    path = tmp_path / "baseline.json"
    assert not baseline.load(path).take("a.md", "STE-8.1", ";")
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "entries": [
                    {"file": "./docs/../a.md", "rule_id": "STE-8.1", "text": ";", "count": 0}
                ],
            }
        )
    )
    assert baseline.load(path).take("a.md", "STE-8.1", ";")
    path.write_text("{")
    with pytest.raises(ValueError):
        baseline.load(path)


def test_save_merges_files_outside_run_and_removes_deleted(tmp_path):
    for name in ("a.md", "b.md"):
        (tmp_path / name).touch()
    path = tmp_path / "baseline.json"
    baseline.save(
        path,
        [
            baseline.Result("a.md", [("STE-4.2", "isn't")]),
            baseline.Result("b.md", [("STE-8.1", ";")]),
            baseline.Result("gone.md", [("STE-8.1", ";")]),
        ],
        "t1",
    )
    results = [baseline.Result("a.md", [("STE-3.6", "was sent")])]
    merge = baseline.plan(path, results)
    assert (merge.kept, merge.removed) == (1, 1)
    baseline.save(path, results, "t2")
    assert json.loads(path.read_text()) == {
        "version": 1,
        "created": "t2",
        "entries": [
            {"file": "a.md", "rule_id": "STE-3.6", "text": "was sent", "count": 1},
            {"file": "b.md", "rule_id": "STE-8.1", "text": ";", "count": 1},
        ],
    }
