#!/usr/bin/env python3
import ctypes
import errno
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "benchmarks" / "v0.8.0-io-uring.md"
IO_URING_SETUP_NR = 425


def output_path() -> Path:
    configured = os.environ.get("REDIS_UYA_IO_URING_OUT")
    if configured is None or configured == "":
        return DEFAULT_OUT
    out = Path(configured)
    if out.is_absolute():
        return out
    return ROOT / out


def display_path(path: Path) -> Path:
    if path.is_relative_to(ROOT):
        return path.relative_to(ROOT)
    return path


def read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return "missing"


def command_output(argv: list[str]) -> tuple[str, str]:
    try:
        proc = subprocess.run(argv, cwd=ROOT, check=False, capture_output=True, text=True)
    except OSError as exc:
        return "error", str(exc)
    if proc.returncode == 0:
        return "yes", proc.stdout.strip()
    message = proc.stderr.strip() or proc.stdout.strip()
    return "no", message


def probe_liburing() -> tuple[str, str]:
    pkg_config = shutil.which("pkg-config")
    if pkg_config is None:
        return "unknown", "pkg-config is not installed"
    status, details = command_output([pkg_config, "--modversion", "liburing"])
    if status == "yes":
        return "yes", details
    return "no", details or "liburing pkg-config metadata not found"


def probe_io_uring_setup() -> tuple[str, str]:
    if platform.system().lower() != "linux":
        return "skip", "non-linux host"
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        params = ctypes.create_string_buffer(256)
        fd = libc.syscall(IO_URING_SETUP_NR, ctypes.c_uint(2), ctypes.byref(params))
        if fd >= 0:
            os.close(fd)
            return "yes", "io_uring_setup syscall succeeded"
        err = ctypes.get_errno()
        if err == errno.ENOSYS:
            return "no", "io_uring_setup returned ENOSYS"
        if err == errno.EPERM:
            return "blocked", "io_uring_setup returned EPERM"
        if err == errno.EACCES:
            return "blocked", "io_uring_setup returned EACCES"
        return "no", f"io_uring_setup failed errno={err}"
    except Exception as exc:
        return "error", str(exc)


def recommendation(disabled: str, syscall_status: str, liburing_status: str) -> str:
    if syscall_status == "yes" and liburing_status == "yes" and disabled in ("0", "missing"):
        return "candidate"
    if syscall_status == "blocked":
        return "defer-blocked"
    if syscall_status == "yes":
        return "prototype-only"
    return "defer"


def main() -> int:
    out = output_path()
    uname = platform.uname()
    disabled = read_text(Path("/proc/sys/kernel/io_uring_disabled"))
    max_entries = read_text(Path("/proc/sys/kernel/io_uring_max_entries"))
    max_workers = read_text(Path("/proc/sys/kernel/io_uring_max_workers"))
    liburing_status, liburing_details = probe_liburing()
    syscall_status, syscall_details = probe_io_uring_setup()
    rec = recommendation(disabled, syscall_status, liburing_status)

    lines = [
        "# redis-uya v0.8.0 io_uring evaluation",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "## Scope",
        "",
        "- This report evaluates whether `io_uring` is a viable future prototype target on the current host.",
        "- v0.8.0 does not bind the production networking path to `io_uring`; the current event loop remains epoll-based.",
        "- The probe is intentionally read-only except for a best-effort `io_uring_setup` syscall that is closed immediately when it succeeds.",
        "",
        "## Raw Output",
        "",
        "```text",
        "IO_URING_EVAL_RESULT version=1 "
        f"host_os={uname.system.lower()} "
        f"host_arch={uname.machine} "
        f"kernel_release={uname.release} "
        f"io_uring_disabled={disabled} "
        f"io_uring_max_entries={max_entries} "
        f"io_uring_max_workers={max_workers} "
        f"liburing_status={liburing_status} "
        f"syscall_status={syscall_status} "
        f"recommendation={rec} "
        "production_binding=no",
        "```",
        "",
        "## Notes",
        "",
        f"- liburing: `{liburing_details}`",
        f"- syscall: `{syscall_details}`",
        f"- recommendation: `{rec}`",
    ]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"[PASS] evaluate_io_uring_v0_8_0: wrote {display_path(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
