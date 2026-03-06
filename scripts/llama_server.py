"""Remote llama-server lifecycle control via SSH.

Provides functions to kill, start, and health-check a llama-server process
running on a remote host. All remote operations are performed over SSH using
subprocess — no paramiko or other dependencies required.

Assumes SSH key auth is configured for the target host. If not, run:
    ssh-copy-id {ssh_user}@{host}
"""

import logging
import re
import subprocess
import time
import urllib.error
import urllib.request
from json import JSONDecodeError, loads

logger = logging.getLogger(__name__)


def check_ssh(host: str, ssh_user: str) -> None:
    """Verify SSH connectivity. Raises RuntimeError with setup instructions if it fails."""
    target = f"{ssh_user}@{host}"
    logger.debug("Testing SSH connectivity to %s", target)
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", target, "echo ok"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"SSH connection to {target} failed.\n"
            f"Set up key auth with: ssh-copy-id {target}\n"
            f"SSH error: {result.stderr.strip()}"
        )
    logger.debug("SSH connectivity OK")


def kill_server(host: str, ssh_user: str, port: int = 8080) -> None:
    """Kill any running llama-server process on the remote host.

    Uses pkill -f to match any process with 'llama-server' in its command line.
    Waits briefly for the port to free before returning.
    Safe to call when no server is running — pkill exits non-zero but we ignore it.
    """
    target = f"{ssh_user}@{host}"
    logger.debug("Killing llama-server on %s", target)
    result = subprocess.run(
        ["ssh", target, "pkill -f llama-server || true"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 255:
        # SSH connection dropped — this is normal when pkill terminates a process
        # that was keeping an SSH session alive (e.g. a leftover nohup wrapper).
        logger.debug("kill_server: SSH connection dropped after kill (expected)")
    elif result.returncode != 0:
        logger.warning("kill_server: SSH returned %d: %s", result.returncode, result.stderr.strip())
    else:
        logger.debug("kill_server: process killed (or wasn't running)")

    # Brief pause for port to free
    time.sleep(2)


def start_server(
    host: str,
    ssh_user: str,
    llama_cpp_dir: str,
    port: int,
    hf_repo: str,
    ngl: int,
    ctx_size: int,
    quant: str = "",
    extra_flags: list[str] | None = None,
) -> None:
    """Start llama-server on the remote host in the background via nohup.

    Starts the process and returns immediately — does not wait for the server
    to be ready. Use wait_for_ready() after calling this.

    Server logs are written to /tmp/llama-server.log on the remote host.
    Retrieve with: ssh {user}@{host} 'tail -50 /tmp/llama-server.log'

    Args:
        host: Remote hostname or IP.
        ssh_user: SSH username.
        llama_cpp_dir: Directory on remote host containing bin/llama-server.
        port: Port for the server to listen on.
        hf_repo: HuggingFace model repo (e.g. 'bartowski/Qwen2.5-7B-Instruct-GGUF').
                 llama-server will download the model if not already cached.
        ngl: Number of GPU layers to offload. 99 = all GPU, 0 = CPU only.
        ctx_size: Context window size in tokens.
        quant: Quantization to load (e.g. 'Q4_K_M'). Appended to the -hf repo argument
               as 'repo:quant'. If empty, llama-server defaults to Q4_K_M or the first
               file in the repo.
        extra_flags: Optional list of additional llama-server flags.
    """
    target = f"{ssh_user}@{host}"
    flags = extra_flags or []
    extra = " ".join(flags)
    hf_arg = f"{hf_repo}:{quant}" if quant else hf_repo

    # setsid --fork creates a new session (no controlling terminal) and forks:
    # the parent exits immediately (SSH returns), child runs llama-server.
    # nohup ensures SIGHUP is ignored if the session ever gets a hangup.
    # This replaces the unreliable `nohup ... & disown` pattern: in non-
    # interactive bash (job control disabled) disown is a no-op, and background
    # children still keep SSH pipe FDs open causing the SSH call to hang.
    cmd = (
        f"cd {llama_cpp_dir} && "
        f"setsid --fork nohup bin/llama-server "
        f"-hf {hf_arg} "
        f"--host 0.0.0.0 "
        f"--port {port} "
        f"--jinja "
        f"-ngl {ngl} "
        f"--ctx-size {ctx_size} "
        f"{extra} "
        f"< /dev/null > /tmp/llama-server.log 2>&1"
    )

    logger.debug(
        "Starting llama-server: hf_repo=%s quant=%s ngl=%d ctx_size=%d port=%d",
        hf_repo,
        quant or "(auto)",
        ngl,
        ctx_size,
        port,
    )
    logger.debug("Remote command: %s", cmd)

    result = subprocess.run(
        ["ssh", target, cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to start llama-server on {target}.\n"
            f"SSH error: {result.stderr.strip()}\n"
            f"Check {target}:/tmp/llama-server.log for details."
        )
    logger.debug("start_server: background process launched")


def wait_for_ready(
    health_url: str,
    timeout: int = 300,
    poll_interval: float = 3.0,
) -> dict:
    """Poll the /v1/models endpoint until the server responds with 200.

    Returns the parsed JSON response (contains model info, context size, etc.).
    Raises TimeoutError if the server doesn't respond within timeout seconds.

    Args:
        health_url: Full URL to poll, e.g. 'http://darkllama:8080/v1/models'.
        timeout: Maximum seconds to wait (default 300 — allows for model download time).
        poll_interval: Seconds between polls.
    """
    deadline = time.monotonic() + timeout
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8")
                    data = loads(body)
                    logger.debug("Server ready after %d poll(s): %s", attempt, health_url)
                    return data
        except (urllib.error.URLError, OSError, JSONDecodeError):
            pass
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        logger.debug("Server not ready yet (attempt %d), retrying in %.0fs...", attempt, poll_interval)
        time.sleep(min(poll_interval, remaining))

    raise TimeoutError(
        f"llama-server did not respond at {health_url} within {timeout}s. "
        "Check /tmp/llama-server.log on the remote host."
    )


def get_server_info(health_url: str) -> dict | None:
    """Quick probe: return /v1/models response dict or None if unreachable."""
    try:
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            if resp.status == 200:
                return loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, JSONDecodeError):
        pass
    return None


def check_server_health(health_url: str) -> tuple[str, dict | None]:
    """Probe the server and classify its state.

    Returns:
        ("alive", data)  — server responded 200; data is the parsed JSON.
        ("hung", None)   — TCP connected but no HTTP response within timeout.
        ("dead", None)   — connection refused or otherwise unreachable.

    Distinguishing "hung" from "dead" matters for the retry policy: a hung
    server should be skipped immediately (no retry), while a dead server may
    be transiently unreachable and warrants one retry.
    """
    try:
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            if resp.status == 200:
                return "alive", loads(resp.read().decode("utf-8"))
        return "dead", None
    except urllib.error.URLError as e:
        # socket.timeout is aliased to TimeoutError since Python 3.3
        if isinstance(e.reason, TimeoutError):
            return "hung", None
        return "dead", None
    except TimeoutError:
        return "hung", None
    except (OSError, JSONDecodeError):
        return "dead", None


def get_remote_hw_info(host: str, ssh_user: str, llama_cpp_dir: str) -> dict:
    """Collect hardware information from the remote host.

    Three-layer GPU detection:
      1. llama-server --list-devices (primary — what the inference backend sees)
      2. nvidia-smi (supplemental, CUDA hosts only)
      3. rocm-smi  (supplemental, ROCm/HIP hosts only)

    All fields are best-effort; any that fail are absent from the returned dict.

    Returns a dict with keys:
      os, cpu_model, cpu_cores, ram_gib,
      gpu_devices (list of {backend, index, name, vram_total_mib, vram_free_mib}),
      gpu_backend (str, e.g. "CUDA" / "ROCM"),
      gpu_raw (raw --list-devices stdout),
      nvidia_smi (str, if applicable),
      rocm_smi   (str, if applicable).
    """
    target = f"{ssh_user}@{host}"
    info: dict = {}

    # ── OS / CPU / RAM (single SSH call, 4-line output parsed positionally) ────
    # Avoid nested quoting: each piece outputs one line, parsed by index.
    # Line 0: OS pretty name (or uname fallback)
    # Line 1: CPU model name
    # Line 2: logical core count
    # Line 3: RAM in KiB
    sys_cmd = (
        "grep PRETTY_NAME /etc/os-release 2>/dev/null"
        " | cut -d= -f2 | tr -d '\"' || uname -srm;"
        " grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | sed 's/^ *//';"
        " nproc;"
        " grep '^MemTotal:' /proc/meminfo | awk '{print $2}'"
    )
    try:
        r = subprocess.run(["ssh", target, sys_cmd], capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            lines = r.stdout.splitlines()
            if len(lines) > 0 and lines[0].strip():
                info["os"] = lines[0].strip()
            if len(lines) > 1 and lines[1].strip():
                info["cpu_model"] = lines[1].strip()
            if len(lines) > 2:
                try:
                    info["cpu_cores"] = int(lines[2].strip())
                except ValueError:
                    pass
            if len(lines) > 3:
                try:
                    info["ram_gib"] = round(int(lines[3].strip()) / 1_048_576, 1)
                except ValueError:
                    pass
        else:
            logger.debug("get_remote_hw_info: sys-info SSH error: %s", r.stderr.strip())
    except Exception as e:  # noqa: BLE001
        logger.debug("get_remote_hw_info: sys-info failed: %s", e)

    # ── GPU — llama-server --list-devices (primary) ───────────────────────────
    try:
        r = subprocess.run(
            ["ssh", target, f"{llama_cpp_dir}/bin/llama-server --list-devices 2>&1"],
            capture_output=True, text=True, timeout=30,
        )
        raw = r.stdout.strip()
        info["gpu_raw"] = raw

        gpu_devices: list[dict] = []
        backend: str | None = None

        for line in raw.splitlines():
            # "Available devices:" block lines, e.g.:
            #   CUDA0: NVIDIA GeForce GTX 1080 (8106 MiB, 7996 MiB free)
            #   ROCm0: AMD Radeon RX 7900 XTX (24560 MiB, 24000 MiB free)
            m = re.match(
                r"^\s+([A-Za-z]+?)(\d+):\s+(.+?)\s+\((\d+)\s+MiB,\s*(\d+)\s+MiB\s+free\)",
                line,
            )
            if m:
                b = m.group(1).upper()
                if backend is None:
                    backend = b
                gpu_devices.append({
                    "backend": b,
                    "index": int(m.group(2)),
                    "name": m.group(3).strip(),
                    "vram_total_mib": int(m.group(4)),
                    "vram_free_mib": int(m.group(5)),
                })

        # Fallback: parse ggml init line if Available devices block was empty
        # e.g. "ggml_cuda_init: found 1 ROCm devices:"
        if not gpu_devices:
            for line in raw.splitlines():
                m2 = re.match(r"ggml_\w+_init: found \d+ (\w+) devices:", line)
                if m2:
                    backend = m2.group(1).upper()
            for line in raw.splitlines():
                # "  Device 0: NVIDIA GeForce GTX 1080, compute capability 6.1, VMM: yes"
                m3 = re.match(r"^\s+Device \d+:\s+(.+)", line)
                if m3:
                    gpu_devices.append({"name": m3.group(1).strip(), "backend": backend})

        info["gpu_devices"] = gpu_devices
        info["gpu_backend"] = backend

    except Exception as e:  # noqa: BLE001
        logger.debug("get_remote_hw_info: --list-devices failed: %s", e)
        info.setdefault("gpu_devices", [])
        info.setdefault("gpu_backend", None)

    # ── Vendor-specific supplemental info ────────────────────────────────────
    backend = info.get("gpu_backend")
    if backend == "CUDA":
        try:
            r = subprocess.run(
                ["ssh", target,
                 "nvidia-smi --query-gpu=name,memory.total,driver_version"
                 " --format=csv,noheader 2>/dev/null"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                info["nvidia_smi"] = r.stdout.strip()
        except Exception as e:  # noqa: BLE001
            logger.debug("get_remote_hw_info: nvidia-smi failed: %s", e)
    elif backend in ("ROCM", "HIP"):
        try:
            r = subprocess.run(
                ["ssh", target, "rocm-smi --showproductname 2>/dev/null"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip():
                info["rocm_smi"] = r.stdout.strip()
        except Exception as e:  # noqa: BLE001
            logger.debug("get_remote_hw_info: rocm-smi failed: %s", e)

    return info


def get_remote_log_tail(host: str, ssh_user: str, lines: int = 30) -> str:
    """Fetch the last N lines of /tmp/llama-server.log from the remote host."""
    target = f"{ssh_user}@{host}"
    result = subprocess.run(
        ["ssh", target, f"tail -{lines} /tmp/llama-server.log 2>/dev/null || echo '(log not found)'"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return result.stdout.strip()
