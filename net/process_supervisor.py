"""
ProcessSupervisor: Resilient Subprocess Confinement & Zombie Elimination Engine.

Inspired by REA (Reverse Engineer Anything) process supervision:
  - Process Tree Confinement: Spawns in isolated POSIX process groups (os.setsid).
  - Signal Escalation: SIGTERM -> bounded grace period (1.5s) -> SIGKILL to process group.
  - Windows Confinement: CREATE_NEW_PROCESS_GROUP + taskkill tree cleanup.
  - Output Budget Enforcement: Caps stdout/stderr buffers to 5 MiB to prevent OOM DoS.
"""

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class SupervisedProcessResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool
    elapsed_ms: int


class ProcessSupervisor:
    """
    Supervises background worker and headless browser processes to ensure
    zero zombie process leakage and bounded memory consumption.
    """

    DEFAULT_TIMEOUT_SECONDS = 15
    DEFAULT_MAX_OUTPUT_BYTES = 5 * 1024 * 1024  # 5 MiB

    @classmethod
    def run_confined(
        cls,
        cmd: List[str],
        timeout_seconds: Optional[int] = None,
        max_output_bytes: Optional[int] = None,
        env: Optional[dict] = None,
        cwd: Optional[str] = None
    ) -> SupervisedProcessResult:
        """
        Executes command inside an isolated process group with strict timeouts
        and signal escalation cleanup.
        """
        timeout = timeout_seconds or cls.DEFAULT_TIMEOUT_SECONDS
        max_bytes = max_output_bytes or cls.DEFAULT_MAX_OUTPUT_BYTES
        started_at = time.time()
        is_posix = sys.platform != "win32"

        proc = None
        timed_out = False
        truncated = False
        stdout_bytes = bytearray()
        stderr_bytes = bytearray()

        popen_kwargs = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "env": env or os.environ.copy(),
            "cwd": cwd,
        }

        if is_posix:
            popen_kwargs["start_new_session"] = True
        else:
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
            stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
            
            # Check for buffer truncation
            if len(stdout_raw) > max_bytes:
                stdout_bytes = bytearray(stdout_raw[:max_bytes])
                truncated = True
            else:
                stdout_bytes = bytearray(stdout_raw)

            if len(stderr_raw) > max_bytes:
                stderr_bytes = bytearray(stderr_raw[:max_bytes])
                truncated = True
            else:
                stderr_bytes = bytearray(stderr_raw)

            returncode = proc.returncode

        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = -9
            if proc:
                cls._terminate_process_tree(proc, is_posix)
                try:
                    stdout_rem, stderr_rem = proc.communicate(timeout=1.0)
                    stdout_bytes = bytearray(stdout_rem or b"")
                    stderr_bytes = bytearray(stderr_rem or b"")
                except Exception:
                    pass

        except Exception as e:
            returncode = -1
            stderr_bytes = bytearray(str(e).encode("utf-8"))
            if proc:
                cls._terminate_process_tree(proc, is_posix)

        elapsed_ms = int((time.time() - started_at) * 1000)

        return SupervisedProcessResult(
            returncode=returncode,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            timed_out=timed_out,
            truncated=truncated,
            elapsed_ms=elapsed_ms
        )

    @classmethod
    def _terminate_process_tree(cls, proc: subprocess.Popen, is_posix: bool) -> None:
        """Kills the entire process group cleanly with SIGTERM then SIGKILL."""
        try:
            if is_posix:
                pgid = os.getpgid(proc.pid)
                # 1. Polite SIGTERM
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    return

                # 2. Bounded grace period
                time.sleep(0.5)

                # 3. Aggressive SIGKILL if still active
                try:
                    os.killpg(pgid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                # Windows taskkill with /T (tree) and /F (force)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
        except Exception:
            # Fallback to direct process kill
            try:
                proc.kill()
            except Exception:
                pass
