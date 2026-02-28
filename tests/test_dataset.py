"""Tests for the Dataset loader."""

import json
import pytest
from pathlib import Path

from ha_voice_bench.dataset import load_ha_test_cases

REPO_ROOT = Path(__file__).parent.parent
SAMPLE_DATA = REPO_ROOT / "sample_test_data"


class TestLoadBasic:
    """Basic loading and structure tests."""

    def test_load_returns_samples(self):
        dataset = load_ha_test_cases(SAMPLE_DATA / "sample_test_cases.ndjson")
        samples = list(dataset)
        assert len(samples) > 0

    def test_sample_has_required_fields(self):
        dataset = load_ha_test_cases(SAMPLE_DATA / "sample_test_cases.ndjson")
        s = list(dataset)[0]
        assert s.id is not None
        assert s.input
        assert s.target
        assert "inventory_tier" in s.metadata
        assert "inventory_file" in s.metadata
        assert "expected_response_type" in s.metadata

    def test_correlation_id_preserved(self):
        dataset = load_ha_test_cases(SAMPLE_DATA / "sample_test_cases.ndjson")
        ids = [s.id for s in dataset]
        assert any("HassTurnOn" in id_ for id_ in ids)

    def test_target_is_valid_json_array(self):
        dataset = load_ha_test_cases(SAMPLE_DATA / "sample_test_cases.ndjson")
        for sample in dataset:
            parsed = json.loads(sample.target)
            assert isinstance(parsed, list)

    def test_metadata_prefixed(self):
        """Nested metadata keys get 'meta/' prefix."""
        dataset = load_ha_test_cases(SAMPLE_DATA / "sample_test_cases.ndjson")
        for sample in dataset:
            meta_keys = [k for k in sample.metadata if k.startswith("meta/")]
            assert len(meta_keys) > 0


class TestFiltering:
    """Tier filtering tests."""

    def test_filter_by_tier(self):
        dataset = load_ha_test_cases(
            SAMPLE_DATA / "sample_test_cases.ndjson",
            inventory_tier="small",
        )
        for sample in dataset:
            assert sample.metadata["inventory_tier"] == "small"

    def test_filter_nonexistent_tier_raises(self):
        with pytest.raises(ValueError, match="No test cases"):
            load_ha_test_cases(
                SAMPLE_DATA / "sample_test_cases.ndjson",
                inventory_tier="nonexistent",
            )


class TestErrorHandling:
    """Error condition tests."""

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_ha_test_cases("/nonexistent/path.ndjson")

    def test_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.ndjson"
        bad_file.write_text("not valid json\n")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_ha_test_cases(bad_file)

    def test_missing_fields_raises(self, tmp_path):
        bad_file = tmp_path / "missing.ndjson"
        bad_file.write_text(json.dumps({"id": "test", "utterance": "hello"}) + "\n")
        with pytest.raises(ValueError, match="Missing fields"):
            load_ha_test_cases(bad_file)

    def test_empty_file_raises(self, tmp_path):
        empty_file = tmp_path / "empty.ndjson"
        empty_file.write_text("\n\n")
        with pytest.raises(ValueError, match="No test cases"):
            load_ha_test_cases(empty_file)
