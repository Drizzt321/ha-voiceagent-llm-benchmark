#!/usr/bin/env python3
"""HA Voice Benchmark — Orchestration Script.

Cycles through a matrix of models × hardware modes × context sizes × tiers,
managing a remote llama-server via SSH for each configuration and running
inspect eval for each tier. All .eval log files are written to a structured
directory under log_dir — these are the primary output for downstream analysis.

Usage:
    uv run scripts/run_benchmark.py configs/my-run.yaml
    uv run scripts/run_benchmark.py configs/my-run.yaml --dry-run
    uv run scripts/run_benchmark.py configs/my-run.yaml --resume

See configs/benchmark.example.yaml for full config documentation.
"""

import argparse
import json
import logging
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

# Sibling module — both scripts/ files share a package-less import via sys.path
sys.path.insert(0, str(Path(__file__).parent))
# Package import — src/ layout
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ha_voice_bench.prompt import DEFAULT_INSTRUCTIONS
from llama_server import (
    check_server_health,
    check_ssh,
    get_remote_log_tail,
    get_server_info,
    kill_server,
    start_server,
    wait_for_ready,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Logging setup ─────────────────────────────────────────────────────────────
# INFO → stdout (human-readable progress)
# DEBUG → orchestration.log (full detail for debugging)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter("%(message)s"))

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(_console_handler)


def _add_file_handler(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(message)s"))
    logger.addHandler(fh)
    logger.debug("Orchestration log: %s", log_path)


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class ModelConfig:
    hf_repo: str
    name: str
    quant: str
    ctx_sizes: list[int]
    extra_flags: list[str] = field(default_factory=list)


@dataclass
class HWMode:
    label: str
    ngl: int


@dataclass
class RunConfig:
    model: ModelConfig
    hw: HWMode
    ctx_size: int
    tier: str

    @property
    def server_key(self) -> tuple[str, str, int]:
        """Group key for server restart decisions: (model name, hw label, ctx_size)."""
        return (self.model.name, self.hw.label, self.ctx_size)

    @property
    def config_label(self) -> str:
        return f"{self.model.name}/{self.model.quant}/{self.hw.label}/ctx{self.ctx_size}"

    @property
    def log_subdir(self) -> str:
        return f"{self.model.name}-{self.model.quant}-{self.hw.label}-ctx{self.ctx_size}"


@dataclass
class RunResult:
    rc: RunConfig
    status: str  # "completed" | "failed" | "skipped"
    wall_time: float | None = None
    n_samples: int | None = None
    avg_latency: float | None = None
    log_path: str | None = None
    error: str | None = None


# ── Config loading ────────────────────────────────────────────────────────────


def _load_config(path: Path) -> dict:
    with open(path) as f:
        cfg = yaml.safe_load(f)

    required = {"server", "tiers", "hardware_modes", "models"}
    missing = required - set(cfg)
    if missing:
        sys.exit(f"Config error: missing required keys: {', '.join(sorted(missing))}")

    srv = cfg["server"]
    for key in ("host", "ssh_user", "llama_cpp_dir", "port", "startup_timeout"):
        if key not in srv:
            sys.exit(f"Config error: server.{key} is required")

    if not cfg.get("models"):
        sys.exit("Config error: models list is empty")
    if not cfg.get("tiers"):
        sys.exit("Config error: tiers list is empty")
    if not cfg.get("hardware_modes"):
        sys.exit("Config error: hardware_modes list is empty")

    return cfg


def _parse_models(cfg: dict) -> list[ModelConfig]:
    models = []
    for m in cfg["models"]:
        for key in ("hf_repo", "name", "quant", "ctx_sizes"):
            if key not in m:
                sys.exit(f"Config error: model entry missing '{key}': {m}")
        models.append(
            ModelConfig(
                hf_repo=m["hf_repo"],
                name=m["name"],
                quant=m["quant"],
                ctx_sizes=m["ctx_sizes"],
                extra_flags=m.get("extra_flags", []),
            )
        )
    return models


def _parse_hw_modes(cfg: dict) -> list[HWMode]:
    modes = []
    for hw in cfg["hardware_modes"]:
        for key in ("label", "ngl"):
            if key not in hw:
                sys.exit(f"Config error: hardware_modes entry missing '{key}': {hw}")
        modes.append(HWMode(label=hw["label"], ngl=hw["ngl"]))
    return modes


def _build_matrix(
    models: list[ModelConfig],
    hw_modes: list[HWMode],
    tiers: list[str],
) -> list[RunConfig]:
    """Build ordered run matrix: models → hw_modes → ctx_sizes → tiers.

    Ordering minimises server restarts: tiers are the inner loop (free, same server).
    """
    matrix: list[RunConfig] = []
    for model in models:
        for hw in hw_modes:
            for ctx in model.ctx_sizes:
                for tier in tiers:
                    matrix.append(RunConfig(model=model, hw=hw, ctx_size=ctx, tier=tier))
    return matrix


# ── Tier assembly ─────────────────────────────────────────────────────────────


def _assemble_tiers(tiers: list[str], base_dir: str) -> None:
    for tier in tiers:
        logger.info("Assembling tier: %s", tier)
        result = subprocess.run(
            ["uv", "run", "scripts/assemble_tier.py", "--base-dir", base_dir, "--tier", tier],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            sys.exit(f"assemble_tier.py failed for tier '{tier}':\n{result.stderr.strip()}")
        logger.debug(result.stdout.strip())


# ── Count tier samples ─────────────────────────────────────────────────────────


def _count_samples(base_dir: str, tier: str) -> int | None:
    path = _REPO_ROOT / base_dir / f"{tier}-test-cases.ndjson"
    if not path.exists():
        return None
    count = 0
    with open(path) as f:
        for line in f:
            if line.strip():
                count += 1
    return count


# ── Inspect eval ──────────────────────────────────────────────────────────────


def _build_eval_command(
    rc: RunConfig,
    base_dir: str,
    log_dir: str,
    instructions_file: str = "",
    timeout: int = 30,
    attempt_timeout: int = 15,
    max_retries: int = 1,
) -> list[str]:
    cmd = [
        "uv",
        "run",
        "inspect",
        "eval",
        "src/ha_voice_bench/task.py",
        "-T",
        f"test_cases={base_dir}/{rc.tier}-test-cases.ndjson",
        "-T",
        f"inventory={base_dir}/{rc.tier}-ha-entities.yaml",
        "-T",
        f"timeout={timeout}",
        "-T",
        f"attempt_timeout={attempt_timeout}",
        "-T",
        f"max_retries={max_retries}",
        "--model",
        "openai/local",
        "--max-connections",
        "1",
        "--display",
        "plain",
        "--no-fail-on-error",
        "--log-dir",
        f"{log_dir}/{rc.log_subdir}/{rc.tier}",
        "--tags",
        rc.model.name,
        rc.model.quant,
        rc.hw.label,
        "--metadata",
        f"model={rc.model.name}",
        f"quant={rc.model.quant}",
        f"hw={rc.hw.label}",
        f"ctx_size={rc.ctx_size}",
        f"tier={rc.tier}",
    ]
    if instructions_file:
        cmd += ["-T", f"instructions_file={instructions_file}"]
    return cmd


def _find_existing_eval(log_dir: str, rc: RunConfig) -> Path | None:
    """Return path to an existing .eval file for this run config, or None."""
    d = _REPO_ROOT / log_dir / rc.log_subdir / rc.tier
    if not d.exists():
        return None
    evals = sorted(d.glob("*.eval"))
    return evals[0] if evals else None


def _extract_run_stats(eval_path: Path) -> tuple[int | None, float | None]:
    """Extract (n_samples, avg_latency_secs) from a completed .eval file."""
    try:
        with zipfile.ZipFile(eval_path) as zf:
            sample_files = [n for n in zf.namelist() if n.startswith("samples/")]
            times = []
            for sf in sample_files:
                s = json.loads(zf.read(sf))
                t = s.get("total_time")
                if t:
                    times.append(t)
            n = len(sample_files)
            avg = sum(times) / len(times) if times else None
            return n, avg
    except Exception:  # noqa: BLE001
        return None, None


# ── Warmup ────────────────────────────────────────────────────────────────────

_WARMUP_TEST_CASES = _REPO_ROOT / "sample_test_data" / "small-test-cases.ndjson"
_WARMUP_INVENTORY = _REPO_ROOT / "sample_test_data" / "small-ha-entities.yaml"


def _check_server_after_failure(health_url: str) -> str:
    """Check server health after a failure and return 'alive', 'hung', or 'dead'.

    Retry policy:
    - hung  → return immediately (TCP connected but unresponsive; no point retrying)
    - dead  → wait 2s and check once more (handles transient network hiccup)
    - alive → return immediately (failure was not caused by a server crash)
    """
    status, _ = check_server_health(health_url)
    if status == "hung":
        logger.error("  Health check: server hung (TCP connected, no HTTP response)")
        return "hung"
    if status == "dead":
        logger.warning("  Health check: server dead — waiting 2s for retry...")
        time.sleep(2)
        status, _ = check_server_health(health_url)
        if status != "alive":
            logger.error("  Health check: server still dead after retry")
            return "dead"
    logger.debug("  Health check: server alive")
    return "alive"


def _run_warmup(rc: RunConfig, run_dir: Path, samples: int | None) -> bool:
    """Run a short eval against sample_test_data to warm up the server.

    Returns True if warmup succeeded (exit 0), False on timeout or error.
    Results are saved to run_dir/warmup/<server-key>/ but excluded from
    benchmark analysis. Uses --display none — warmup output is noise.
    Paths are resolved from _REPO_ROOT so they work regardless of CWD.
    """
    label = "all samples" if samples is None else f"{samples} sample{'s' if samples != 1 else ''}"
    logger.info("  Warming up (%s)...", label)
    t0 = time.monotonic()

    cmd = [
        "uv", "run", "inspect", "eval",
        "src/ha_voice_bench/task.py",
        "-T", f"test_cases={_WARMUP_TEST_CASES}",
        "-T", f"inventory={_WARMUP_INVENTORY}",
        "--model", "openai/local",
        "--max-connections", "1",
        "--display", "none",
        "--no-fail-on-error",
        "--log-dir", str(run_dir / "warmup" / rc.log_subdir),
    ]
    if samples is not None:
        cmd += ["--limit", str(samples)]

    try:
        result = subprocess.run(cmd, cwd=_REPO_ROOT, stdout=None, stderr=subprocess.PIPE, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        logger.error("  Warmup timed out after 120s — server may have crashed")
        return False

    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        logger.warning("  Warmup finished with errors (%.0fs)", elapsed)
        logger.debug("  Warmup stderr: %s", result.stderr.strip()[-1000:])
        return False

    logger.info("  Warmup done (%.0fs)", elapsed)
    return True


# ── Summary display ───────────────────────────────────────────────────────────


def _print_run_plan(
    matrix: list[RunConfig],
    models: list[ModelConfig],
    hw_modes: list[HWMode],
    tiers: list[str],
    base_dir: str,
    log_dir: str,
    run_dir: Path,
) -> None:
    model_labels = ", ".join(f"{m.name} ({m.quant})" for m in models)
    hw_labels = ", ".join(f"{hw.label} (ngl={hw.ngl})" for hw in hw_modes)
    tier_labels = []
    for t in tiers:
        n = _count_samples(base_dir, t)
        tier_labels.append(f"{t} ({n} cases)" if n else t)

    ctx_sizes = sorted({c for m in models for c in m.ctx_sizes})

    logger.info("=" * 60)
    logger.info("HA Voice Benchmark")
    logger.info("=" * 60)
    logger.info("Models:       %s", model_labels)
    logger.info("HW modes:     %s", hw_labels)
    logger.info("Tiers:        %s", ", ".join(tier_labels))
    logger.info("Ctx sizes:    %s", ", ".join(str(c) for c in ctx_sizes))
    logger.info("Total runs:   %d", len(matrix))
    logger.info("Logs:         %s/", log_dir)
    logger.info("Run dir:      %s/", run_dir)
    logger.info("=" * 60)


def _print_summary(results: list[RunResult], total_wall: float) -> None:
    completed = [r for r in results if r.status == "completed"]
    failed = [r for r in results if r.status == "failed"]
    skipped = [r for r in results if r.status == "skipped"]

    logger.info("")
    logger.info("=" * 60)
    logger.info("Run Complete")
    logger.info("=" * 60)
    h, rem = divmod(int(total_wall), 3600)
    m, s = divmod(rem, 60)
    logger.info("Total wall time: %dh %02dm %02ds", h, m, s)
    logger.info(
        "Configurations: %d completed, %d failed, %d skipped",
        len(completed),
        len(failed),
        len(skipped),
    )
    if failed:
        for r in failed:
            logger.info("  FAILED: %s/%s — %s", r.rc.config_label, r.rc.tier, r.error or "unknown")
    if skipped:
        for r in skipped:
            logger.info("  SKIPPED: %s/%s — %s", r.rc.config_label, r.rc.tier, r.error or "")

    # Per-model timing
    model_times: dict[str, list[float]] = {}
    for r in completed:
        key = f"{r.rc.model.name} ({r.rc.model.quant})"
        model_times.setdefault(key, []).append(r.wall_time or 0)
    if model_times:
        logger.info("")
        logger.info("Per-model timing:")
        for model, times in model_times.items():
            t = sum(times)
            h2, rem2 = divmod(int(t), 3600)
            m2, s2 = divmod(rem2, 60)
            label = f"{h2}h {m2:02d}m" if h2 else f"{m2}m {s2:02d}s"
            logger.info("  %-30s %s across %d run(s)", model, label, len(times))

    # Avg latency per server config (model/hw/ctx)
    config_latencies: dict[str, list[float]] = {}
    for r in completed:
        if r.avg_latency:
            key = f"{r.rc.model.name}/{r.rc.model.quant}/{r.rc.hw.label}/ctx{r.rc.ctx_size}"
            config_latencies.setdefault(key, []).append(r.avg_latency)
    if config_latencies:
        logger.info("")
        logger.info("Avg latency per sample:")
        for cfg_key, lats in sorted(config_latencies.items()):
            avg = sum(lats) / len(lats)
            logger.info("  %-45s %.1fs", cfg_key, avg)

    logger.info("=" * 60)


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "config",
        metavar="CONFIG",
        nargs="?",
        help="Path to benchmark config YAML (required unless --resume is given)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the run plan and exit without starting any servers or evals",
    )
    parser.add_argument(
        "--resume",
        metavar="RUN_DIR",
        help="Resume a previous run: path to its log directory. Config is read from inside it.",
    )
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="Skip the warmup eval that runs after each server start.",
    )
    parser.add_argument(
        "--warmup-samples",
        metavar="N",
        type=int,
        help="Limit warmup to the first N samples (overrides config warmup_samples).",
    )
    args = parser.parse_args()

    if args.resume and args.config:
        sys.exit("Cannot specify both CONFIG and --resume")
    if not args.resume and not args.config:
        sys.exit("Must specify CONFIG or --resume <run-dir>")

    if args.resume:
        run_dir = Path(args.resume).resolve()
        if not run_dir.is_dir():
            sys.exit(f"Resume directory not found: {run_dir}")
        yaml_files = list(run_dir.glob("*.yaml"))
        if not yaml_files:
            sys.exit(f"No config YAML found in resume directory: {run_dir}")
        cfg_path = yaml_files[0]
    else:
        cfg_path = Path(args.config).resolve()  # type: ignore[arg-type]
        if not cfg_path.exists():
            sys.exit(f"Config file not found: {cfg_path}")

    cfg = _load_config(cfg_path)

    srv = cfg["server"]
    host: str = srv["host"]
    ssh_user: str = srv["ssh_user"]
    llama_cpp_dir: str = srv["llama_cpp_dir"]
    port: int = srv["port"]
    startup_timeout: int = srv["startup_timeout"]
    health_url = f"http://{host}:{port}/v1/models"

    tiers: list[str] = cfg["tiers"]
    base_dir: str = cfg.get("base_dir", "test_data")
    log_dir: str = cfg.get("log_dir", "logs")
    assemble: bool = cfg.get("assemble_tiers", True)
    instructions_file: str = cfg.get("instructions_file", "")
    if instructions_file:
        instructions_text = (_REPO_ROOT / instructions_file).read_text()
        instructions_source = instructions_file
    else:
        instructions_text = DEFAULT_INSTRUCTIONS
        instructions_source = "default"
    timeout: int = cfg.get("timeout", 30)
    attempt_timeout: int = cfg.get("attempt_timeout", 15)
    max_retries: int = cfg.get("max_retries", 1)

    # Warmup: enabled by default; sample count from config, overridden by CLI
    warmup_enabled: bool = not args.no_warmup
    warmup_samples: int | None = args.warmup_samples or cfg.get("warmup_samples") or None

    models = _parse_models(cfg)
    hw_modes = _parse_hw_modes(cfg)
    matrix = _build_matrix(models, hw_modes, tiers)

    # Compute run directory: logs/<cfg-stem>/<timestamp>/  (or the resume path)
    if args.resume:
        run_dir = Path(args.resume).resolve()
    else:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        run_dir = _REPO_ROOT / log_dir / cfg_path.stem / timestamp

    try:
        run_dir_rel = run_dir.relative_to(_REPO_ROOT)
    except ValueError:
        run_dir_rel = run_dir

    # Create run dir and attach log file before printing the header so the
    # header appears in orchestration.log as well as stdout. Skipped for
    # dry runs — we don't want to create dirs or files for a no-op.
    if not args.dry_run and not args.resume:
        run_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cfg_path, run_dir / cfg_path.name)
    if not args.dry_run:
        _add_file_handler(run_dir / "orchestration.log")
        logger.debug("Config: %s", cfg_path)
        logger.debug("Run dir: %s", run_dir)
        logger.debug("Matrix: %d runs", len(matrix))

    _print_run_plan(matrix, models, hw_modes, tiers, base_dir, log_dir, run_dir_rel)

    logger.info("Instructions (%s):", instructions_source)
    for line in instructions_text.splitlines():
        logger.info("  %s", line)
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("")
        logger.info("Dry run — no servers started, no evals run.")
        logger.info("Run directory would be: %s", run_dir_rel)
        logger.info("Runs that would execute:")
        for i, rc in enumerate(matrix, 1):
            cmd = _build_eval_command(rc, base_dir, str(run_dir), instructions_file, timeout, attempt_timeout, max_retries)
            logger.info("  [%d/%d] %s / %s", i, len(matrix), rc.config_label, rc.tier)
            logger.debug("  CMD: %s", " ".join(cmd))
        return

    # SSH check before anything else
    logger.info("Checking SSH connectivity to %s@%s...", ssh_user, host)
    try:
        check_ssh(host, ssh_user)
    except RuntimeError as e:
        sys.exit(str(e))
    logger.info("SSH OK")

    # Assemble tiers if requested
    if assemble:
        logger.info("")
        _assemble_tiers(tiers, base_dir)

    # Graceful Ctrl-C: kill remote server before exiting
    def _shutdown(sig: int, frame: object) -> None:  # noqa: ARG001
        logger.info("\nInterrupted — killing server before exit...")
        try:
            kill_server(host, ssh_user, port)
        except Exception:  # noqa: BLE001
            pass
        sys.exit(1)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    results: list[RunResult] = []
    total_start = time.monotonic()
    current_server_key: tuple | None = None
    # Server keys confirmed dead/hung mid-run; remaining tiers are skipped.
    skipped_server_keys: set[tuple] = set()

    for i, rc in enumerate(matrix, 1):
        logger.info("")
        logger.info("[%d/%d] %s / %s", i, len(matrix), rc.config_label, rc.tier)

        # Resume: skip if already done
        if args.resume:
            existing = _find_existing_eval(str(run_dir), rc)
            if existing:
                logger.info("  Skipping — existing log: %s", existing.name)
                n, lat = _extract_run_stats(existing)
                results.append(
                    RunResult(
                        rc=rc,
                        status="skipped",
                        n_samples=n,
                        avg_latency=lat,
                        log_path=str(existing),
                    )
                )
                continue

        # Skip remaining tiers for a server config that was found dead/hung.
        if rc.server_key in skipped_server_keys:
            logger.info("  Skipping — server config was skipped due to crash")
            results.append(RunResult(rc=rc, status="failed", error="Server crash — config skipped"))
            continue

        # Restart server if server config changed
        if rc.server_key != current_server_key:
            logger.info(
                "  Starting server: %s  ngl=%d  ctx=%d",
                rc.model.hf_repo,
                rc.hw.ngl,
                rc.ctx_size,
            )
            logger.debug("  Killing existing server...")
            try:
                kill_server(host, ssh_user, port)
            except Exception as e:  # noqa: BLE001
                logger.warning("  kill_server warning: %s", e)

            try:
                start_server(
                    host=host,
                    ssh_user=ssh_user,
                    llama_cpp_dir=llama_cpp_dir,
                    port=port,
                    hf_repo=rc.model.hf_repo,
                    ngl=rc.hw.ngl,
                    ctx_size=rc.ctx_size,
                    quant=rc.model.quant,
                    extra_flags=rc.model.extra_flags,
                )
            except RuntimeError as e:
                logger.error("  Failed to start server: %s", e)
                # Mark all remaining runs with this server key as failed
                for j in range(i - 1, len(matrix)):
                    if matrix[j].server_key == rc.server_key:
                        results.append(
                            RunResult(
                                rc=matrix[j],
                                status="failed",
                                error=f"Server failed to start: {e}",
                            )
                        )
                current_server_key = None
                continue

            logger.info("  Waiting for server (timeout: %ds)...", startup_timeout)
            t_wait = time.monotonic()
            try:
                wait_for_ready(health_url, timeout=startup_timeout)
                elapsed = time.monotonic() - t_wait
                # Re-query for actual ctx from server info
                info = get_server_info(health_url)
                actual_ctx = None
                if info:
                    for entry in info.get("data", []):
                        actual_ctx = entry.get("meta", {}).get("n_ctx_train")
                logger.info(
                    "  Server ready (%.0fs)%s",
                    elapsed,
                    f"  model ctx_train={actual_ctx}" if actual_ctx else "",
                )
                current_server_key = rc.server_key
            except TimeoutError as e:
                logger.error("  Server timed out: %s", e)
                tail = get_remote_log_tail(host, ssh_user)
                logger.error("  Remote log tail:\n%s", tail)
                for j in range(i - 1, len(matrix)):
                    if matrix[j].server_key == rc.server_key:
                        results.append(
                            RunResult(
                                rc=matrix[j],
                                status="failed",
                                error="Server startup timeout",
                            )
                        )
                current_server_key = None
                continue

            # Warmup (outside the wait_for_ready try so its failure is handled separately)
            if warmup_enabled:
                warmup_ok = _run_warmup(rc, run_dir, warmup_samples)
                if not warmup_ok:
                    server_status = _check_server_after_failure(health_url)
                    if server_status in ("hung", "dead"):
                        tail = get_remote_log_tail(host, ssh_user)
                        logger.error("  Remote log tail:\n%s", tail)
                        logger.error("  Skipping all tiers for this server config")
                        skipped_server_keys.add(rc.server_key)
                        current_server_key = None
                        results.append(RunResult(rc=rc, status="failed", error=f"Server {server_status} after warmup failure"))
                        continue
                    # Server alive despite warmup errors — proceed to eval
                    logger.warning("  Warmup failed but server is alive — proceeding to eval")
        else:
            logger.info("  Server already loaded, reusing")

        # Run inspect eval
        cmd = _build_eval_command(rc, base_dir, str(run_dir), instructions_file, timeout, attempt_timeout, max_retries)
        logger.debug("  CMD: %s", " ".join(cmd))

        n_samples_est = _count_samples(base_dir, rc.tier)
        eval_timeout = max(300, (n_samples_est or 10) * 60)  # at least 5 min, 60s/sample budget

        run_start = time.monotonic()
        try:
            result = subprocess.run(cmd, cwd=_REPO_ROOT, stdout=None, stderr=subprocess.PIPE, text=True, timeout=eval_timeout)
        except subprocess.TimeoutExpired:
            wall_time = time.monotonic() - run_start
            logger.error("  Eval timed out after %ds — server may have crashed", eval_timeout)
            results.append(RunResult(rc=rc, status="failed", error=f"eval timeout after {eval_timeout}s", wall_time=wall_time))
            server_status = _check_server_after_failure(health_url)
            if server_status in ("hung", "dead"):
                tail = get_remote_log_tail(host, ssh_user)
                logger.error("  Remote log tail:\n%s", tail)
                logger.error("  Skipping remaining tiers for this server config")
                skipped_server_keys.add(rc.server_key)
                current_server_key = None
            continue

        wall_time = time.monotonic() - run_start

        logger.debug("  inspect eval exit code: %d", result.returncode)
        if result.stdout:
            logger.debug("  stdout: %s", result.stdout[-2000:])
        if result.stderr:
            logger.debug("  stderr: %s", result.stderr[-2000:])

        # Find the .eval file that was just written
        eval_path = _find_existing_eval(str(run_dir), rc)
        n_samples, avg_latency = (None, None)
        if eval_path:
            n_samples, avg_latency = _extract_run_stats(eval_path)

        status = "completed" if result.returncode == 0 else "failed"
        error = None if result.returncode == 0 else f"inspect eval exit code {result.returncode}"

        if status == "completed":
            logger.info(
                "  Done: %s samples | %.0fs%s",
                n_samples if n_samples is not None else "?",
                wall_time,
                f" | {run_dir_rel}/{rc.log_subdir}/{rc.tier}/" if eval_path else "",
            )
        else:
            logger.error("  FAILED (exit %d): %s", result.returncode, result.stderr.strip()[:200])
            server_status = _check_server_after_failure(health_url)
            if server_status in ("hung", "dead"):
                tail = get_remote_log_tail(host, ssh_user)
                logger.error("  Remote log tail:\n%s", tail)
                logger.error("  Skipping remaining tiers for this server config")
                skipped_server_keys.add(rc.server_key)
                current_server_key = None

        results.append(
            RunResult(
                rc=rc,
                status=status,
                wall_time=wall_time,
                n_samples=n_samples,
                avg_latency=avg_latency,
                log_path=str(eval_path) if eval_path else None,
                error=error,
            )
        )

    # Kill server at end
    logger.info("")
    logger.info("Stopping server...")
    try:
        kill_server(host, ssh_user, port)
    except Exception as e:  # noqa: BLE001
        logger.warning("kill_server (cleanup): %s", e)

    total_wall = time.monotonic() - total_start
    _print_summary(results, total_wall)


if __name__ == "__main__":
    main()
