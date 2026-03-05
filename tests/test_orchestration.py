"""Tests for benchmark orchestration: config parsing, matrix building, command generation."""

import sys
from pathlib import Path

import pytest
import yaml

# Add scripts/ to path so we can import run_benchmark without it being a package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_benchmark import (
    HWMode,
    ModelConfig,
    RunConfig,
    _REPO_ROOT,
    _WARMUP_INVENTORY,
    _WARMUP_TEST_CASES,
    _build_eval_command,
    _build_matrix,
    _load_config,
    _parse_hw_modes,
    _parse_models,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def example_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "configs" / "benchmark.example.yaml"


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    cfg = {
        "server": {
            "host": "testhost",
            "ssh_user": "testuser",
            "llama_cpp_dir": "/opt/llama.cpp",
            "port": 8080,
            "startup_timeout": 60,
        },
        "tiers": ["small", "medium"],
        "hardware_modes": [
            {"label": "gpu", "ngl": 99},
            {"label": "cpu", "ngl": 0},
        ],
        "models": [
            {
                "hf_repo": "bartowski/Qwen2.5-7B-Instruct-GGUF",
                "name": "qwen2.5-7b",
                "quant": "Q4_K_M",
                "ctx_sizes": [8192, 32768],
            },
            {
                "hf_repo": "bartowski/Qwen2.5-3B-Instruct-GGUF",
                "name": "qwen2.5-3b",
                "quant": "Q4_K_M",
                "ctx_sizes": [8192],
            },
        ],
    }
    p = tmp_path / "test.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


# ── Config loading ─────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_loads_minimal_config(self, minimal_config: Path) -> None:
        cfg = _load_config(minimal_config)
        assert cfg["server"]["host"] == "testhost"
        assert cfg["tiers"] == ["small", "medium"]

    def test_example_config_is_valid_yaml(self, example_config_path: Path) -> None:
        cfg = _load_config(example_config_path)
        assert "server" in cfg
        assert "models" in cfg
        assert "tiers" in cfg
        assert "hardware_modes" in cfg

    def test_example_config_server_fields(self, example_config_path: Path) -> None:
        cfg = _load_config(example_config_path)
        srv = cfg["server"]
        assert "host" in srv
        assert "ssh_user" in srv
        assert "llama_cpp_dir" in srv
        assert "port" in srv
        assert "startup_timeout" in srv

    def test_missing_required_key_exits(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump({"server": {}, "tiers": [], "models": []}))
        with pytest.raises(SystemExit):
            _load_config(p)


# ── Model parsing ──────────────────────────────────────────────────────────────


class TestParseModels:
    def test_parses_models(self, minimal_config: Path) -> None:
        cfg = _load_config(minimal_config)
        models = _parse_models(cfg)
        assert len(models) == 2
        assert models[0].name == "qwen2.5-7b"
        assert models[0].quant == "Q4_K_M"
        assert models[0].ctx_sizes == [8192, 32768]
        assert models[0].extra_flags == []

    def test_extra_flags_optional(self, tmp_path: Path) -> None:
        cfg = {
            "server": {"host": "h", "ssh_user": "u", "llama_cpp_dir": "/d", "port": 8080, "startup_timeout": 60},
            "tiers": ["small"],
            "hardware_modes": [{"label": "gpu", "ngl": 99}],
            "models": [
                {
                    "hf_repo": "test/model",
                    "name": "testmodel",
                    "quant": "Q4",
                    "ctx_sizes": [4096],
                    "extra_flags": ["--some-flag", "value"],
                }
            ],
        }
        p = tmp_path / "cfg.yaml"
        p.write_text(yaml.safe_dump(cfg))
        loaded = _load_config(p)
        models = _parse_models(loaded)
        assert models[0].extra_flags == ["--some-flag", "value"]


# ── HW mode parsing ───────────────────────────────────────────────────────────


class TestParseHWModes:
    def test_parses_hw_modes(self, minimal_config: Path) -> None:
        cfg = _load_config(minimal_config)
        modes = _parse_hw_modes(cfg)
        assert len(modes) == 2
        assert modes[0].label == "gpu"
        assert modes[0].ngl == 99
        assert modes[1].label == "cpu"
        assert modes[1].ngl == 0


# ── Matrix building ───────────────────────────────────────────────────────────


class TestBuildMatrix:
    def test_matrix_size(self, minimal_config: Path) -> None:
        cfg = _load_config(minimal_config)
        models = _parse_models(cfg)
        hw_modes = _parse_hw_modes(cfg)
        tiers = cfg["tiers"]
        matrix = _build_matrix(models, hw_modes, tiers)
        # 2 models × 2 hw × (2 ctx + 1 ctx) × 2 tiers = ...
        # model0: 2 ctx_sizes × 2 hw × 2 tiers = 8
        # model1: 1 ctx_size × 2 hw × 2 tiers = 4
        assert len(matrix) == 12

    def test_matrix_ordering(self, minimal_config: Path) -> None:
        """Model is the outer loop — all hw/ctx/tier combos for a model run together."""
        cfg = _load_config(minimal_config)
        models = _parse_models(cfg)
        hw_modes = _parse_hw_modes(cfg)
        tiers = cfg["tiers"]
        matrix = _build_matrix(models, hw_modes, tiers)
        # All configs for model0 should come before model1
        model_names = [rc.model.name for rc in matrix]
        last_model0 = max(i for i, n in enumerate(model_names) if n == "qwen2.5-7b")
        first_model1 = min(i for i, n in enumerate(model_names) if n == "qwen2.5-3b")
        assert last_model0 < first_model1

    def test_server_key_groups(self) -> None:
        """Tiers within same model/hw/ctx share server_key — no restart needed."""
        models = [ModelConfig("repo", "m1", "Q4", [8192])]
        hw = [HWMode("gpu", 99)]
        tiers = ["small", "medium", "large"]
        matrix = _build_matrix(models, hw, tiers)
        keys = [rc.server_key for rc in matrix]
        assert len(set(keys)) == 1  # all same server config
        assert len(matrix) == 3  # one per tier

    def test_run_config_labels(self) -> None:
        models = [ModelConfig("repo/name", "mymodel", "Q8", [4096])]
        hw = [HWMode("gpu", 99)]
        matrix = _build_matrix(models, hw, ["small"])
        rc = matrix[0]
        assert rc.config_label == "mymodel/Q8/gpu/ctx4096"
        assert rc.log_subdir == "mymodel-Q8-gpu-ctx4096"


# ── Command builder ───────────────────────────────────────────────────────────


class TestBuildEvalCommand:
    def _make_rc(self) -> RunConfig:
        model = ModelConfig("bartowski/Qwen2.5-7B-Instruct-GGUF", "qwen2.5-7b", "Q4_K_M", [8192])
        hw = HWMode("gpu", 99)
        return RunConfig(model=model, hw=hw, ctx_size=8192, tier="small")

    def test_contains_required_flags(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs")
        joined = " ".join(cmd)
        assert "--max-connections 1" in joined
        assert "--display plain" in joined
        assert "--no-fail-on-error" in joined

    def test_timeout_params_passed_as_task_args(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs", timeout=30, attempt_timeout=15, max_retries=1)
        joined = " ".join(cmd)
        assert "timeout=30" in joined
        assert "attempt_timeout=15" in joined
        assert "max_retries=1" in joined

    def test_correct_test_cases_path(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs")
        assert "test_cases=test_data/small-test-cases.ndjson" in " ".join(cmd)

    def test_correct_inventory_path(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs")
        assert "inventory=test_data/small-ha-entities.yaml" in " ".join(cmd)

    def test_correct_log_dir(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs")
        assert "--log-dir" in cmd
        log_dir_idx = cmd.index("--log-dir")
        assert "qwen2.5-7b-Q4_K_M-gpu-ctx8192/small" in cmd[log_dir_idx + 1]

    def test_metadata_includes_hw_and_tier(self) -> None:
        rc = self._make_rc()
        cmd = _build_eval_command(rc, "test_data", "logs")
        joined = " ".join(cmd)
        assert "hw=gpu" in joined
        assert "tier=small" in joined
        assert "ctx_size=8192" in joined


# ── Warmup ─────────────────────────────────────────────────────────────────────


class TestWarmup:
    def test_warmup_paths_are_under_repo_root(self) -> None:
        assert _WARMUP_TEST_CASES.is_relative_to(_REPO_ROOT)
        assert _WARMUP_INVENTORY.is_relative_to(_REPO_ROOT)

    def test_warmup_files_exist(self) -> None:
        assert _WARMUP_TEST_CASES.exists(), f"Missing: {_WARMUP_TEST_CASES}"
        assert _WARMUP_INVENTORY.exists(), f"Missing: {_WARMUP_INVENTORY}"

    def test_warmup_paths_not_cwd_relative(self) -> None:
        """Paths must be absolute so warmup works regardless of CWD."""
        assert _WARMUP_TEST_CASES.is_absolute()
        assert _WARMUP_INVENTORY.is_absolute()
