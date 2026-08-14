"""
scripts/run_config.py

Runs N measurement runs of a single Phase B configuration (baseline
auto, or a specific --num_cpu_threads value) against the frozen
phase_b_prompt.txt workload on the connected Android device, enforcing
the readiness gate (thermal status + battery) before every run, and
logging full structured metrics to a CSV per MEASUREMENT_PROCEDURE.md
and OPTIMIZATION_PARAMETERS.md.

Requires: `adb` on PATH, device connected (wireless ADB, USB
disconnected per OPTIMIZATION_PARAMETERS.md), the binary/model/prompt
files already pushed to /data/local/tmp/ (see RUNTIME_SELECTION.md).

Usage examples:
    python scripts/run_config.py --config baseline --n-runs 5 --run-type warmup --output data/raw/baseline.csv
    python scripts/run_config.py --config baseline --n-runs 30 --run-type valid --output data/raw/baseline.csv
    python scripts/run_config.py --config threads_4 --threads 4 --n-runs 30 --run-type valid --output data/raw/threads_4.csv

CPU utilization and peak memory are collected via /proc/<PID>/stat and
/proc/<PID>/status, polled once per second over adb shell. This is
best-effort given wireless-adb round-trip latency (each poll is a
separate adb shell call) -- it is diagnostic,
not a high-precision profiler. CPU utilization is reported as raw
percent of one core (may exceed 100% when multiple threads are
active, up to ~800% on this 8-core device) -- this is the standard
"top"-style convention, not normalized per core.

adb-level failures (e.g. "more than one device/emulator", device
disconnected) raise AdbError immediately and abort the run -- they are
never silently treated as "device not ready", which previously caused
the script to loop indefinitely without making progress or surfacing
the real problem.
"""

import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

BINARY_DIR = "/data/local/tmp"
MODEL = "/data/local/tmp/gemma-4-E2B-it.litertlm"
PROMPT_FILE = "/data/local/tmp/phase_b_prompt.txt"
REMOTE_OUTPUT = "/data/local/tmp/run_output.log"

THERMAL_OK = {"0", "1"}  # NONE, LIGHT (per OPTIMIZATION_PARAMETERS.md)
BATTERY_MIN = 50
READINESS_POLL_INTERVAL_S = 30
READINESS_MAX_WAIT_S = 1800
PROC_POLL_INTERVAL_S = 1.0
INTER_RUN_DELAY_S = 5

FIELDNAMES = [
    "timestamp", "config", "threads", "run_type",
    "thermal_status_start", "battery_pct_start", "thermal_status_end",
    "end_to_end_latency_s", "init_total_ms", "time_to_first_token_s",
    "prefill_tokens", "prefill_speed_tok_s",
    "decode_tokens", "decode_speed_tok_s",
    "peak_rss_kb", "cpu_pct",
    "validity", "exclusion_reason",
]


class AdbError(RuntimeError):
    """Raised when adb itself fails (not a device-readiness condition).
    Examples: multiple devices attached and ambiguous, device offline,
    adb daemon unreachable. Never treated as 'not ready' -- these mean
    the script cannot talk to the device at all and must stop, not
    retry silently."""


def adb_shell(cmd, timeout=60):
    """Run a single adb shell command, return stdout as string.
    Raises AdbError if adb itself fails (nonzero exit, or a stderr
    message indicating an adb-level problem rather than a normal
    command result)."""
    result = subprocess.run(
        ["adb", "shell", cmd], capture_output=True, text=True, timeout=timeout, check=False
    )
    stderr = (result.stderr or "").strip()
    adb_error_markers = (
        "more than one device/emulator",
        "device offline",
        "device not found",
        "no devices/emulators found",
        "error: no devices",
    )
    if result.returncode != 0 and any(marker in stderr.lower() for marker in adb_error_markers):
        raise AdbError(
            f"adb shell failed (adb-level error, not a device-readiness issue): "
            f"{stderr!r} -- check `adb devices` for a duplicate/ambiguous connection "
            f"before retrying."
        )
    return result.stdout


def get_thermal_status():
    out = adb_shell("dumpsys thermalservice")
    m = re.search(r"Thermal Status:\s*(\d+)", out)
    return m.group(1) if m else None


def get_battery_level():
    out = adb_shell("dumpsys battery")
    m = re.search(r"level:\s*(\d+)", out)
    return int(m.group(1)) if m else None


def get_clk_tck():
    out = adb_shell("getconf CLK_TCK 2>/dev/null").strip()
    try:
        return int(out)
    except ValueError:
        return 100  # standard Linux/Android USER_HZ default


def readiness_gate():
    """Block until thermal status and battery both pass. Returns
    (thermal_status, battery_pct) once GREEN LIGHT. Raises TimeoutError
    if the gate does not pass within READINESS_MAX_WAIT_S. Raises
    AdbError immediately (not retried) if adb itself is unreachable or
    ambiguous -- this is a hard stop, not a readiness condition."""
    waited = 0
    while True:
        thermal = get_thermal_status()
        battery = get_battery_level()
        if thermal is None or battery is None:
            raise AdbError(
                f"Could not read device state (thermal={thermal!r}, "
                f"battery={battery!r}) despite adb_shell succeeding -- "
                f"this indicates dumpsys output could not be parsed, not "
                f"a normal 'not ready' state. Check the device manually "
                f"before retrying."
            )
        ok_thermal = thermal in THERMAL_OK
        ok_battery = battery >= BATTERY_MIN
        if ok_thermal and ok_battery:
            return thermal, battery
        print(
            f"  [readiness] NOT READY (thermal={thermal}, battery={battery}%) "
            f"-- waiting {READINESS_POLL_INTERVAL_S}s...",
            file=sys.stderr,
        )
        time.sleep(READINESS_POLL_INTERVAL_S)
        waited += READINESS_POLL_INTERVAL_S
        if waited >= READINESS_MAX_WAIT_S:
            raise TimeoutError("Readiness gate did not pass within max wait time")


def poll_proc(pid):
    """Single combined adb call: checks if PID is alive, and if so
    returns (VmHWM_kb, utime_ticks, stime_ticks). Returns None if the
    process has already exited."""
    cmd = (
        f'if [ -d /proc/{pid} ]; then '
        f'cat /proc/{pid}/status 2>/dev/null | grep VmHWM; '
        f'echo ---; '
        f'cat /proc/{pid}/stat 2>/dev/null; '
        f'else echo GONE; fi'
    )
    out = adb_shell(cmd)
    if out.strip() == "GONE" or "---" not in out:
        return None
    vmhwm_part, stat_part = out.split("---", 1)
    vmhwm_kb = None
    m = re.search(r"VmHWM:\s*(\d+)\s*kB", vmhwm_part)
    if m:
        vmhwm_kb = int(m.group(1))
    utime = stime = None
    stat_line = stat_part.strip()
    if stat_line:
        try:
            after_comm = stat_line.rsplit(")", 1)[1].split()
            utime = int(after_comm[11])  # field 14 of /proc/pid/stat
            stime = int(after_comm[12])  # field 15
        except (IndexError, ValueError):
            pass
    return vmhwm_kb, utime, stime


def parse_benchmark_info(text):
    """Extract structured fields from the BenchmarkInfo block in the
    binary's stdout/stderr log."""
    def find_float(pattern):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    def find_int(pattern):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else None

    return {
        "init_total_ms": find_float(r"Init Total:\s*([\d.]+)\s*ms"),
        "time_to_first_token_s": find_float(r"Time to first token:\s*([\d.]+)\s*s"),
        "prefill_tokens": find_int(r"Prefill Turn 1: Processed (\d+) tokens"),
        "prefill_speed_tok_s": find_float(r"Prefill Speed:\s*([\d.]+)\s*tokens/sec"),
        "decode_tokens": find_int(r"Decode Turn 1: Processed (\d+) tokens"),
        "decode_speed_tok_s": find_float(r"Decode Speed:\s*([\d.]+)\s*tokens/sec"),
    }


def run_one(threads, tick_rate, cache_dir=":memory", disable_weight_cache=False):
    """Launch the binary in the background on-device, poll it until
    completion, and return (metrics_dict, raw_log_text)."""
    threads_flag = f"--num_cpu_threads={threads} " if threads is not None else ""
    cache_flag = f"--cache_dir={cache_dir} " if cache_dir else ""
    dwc_flag = f"--disable_weight_cache={'true' if disable_weight_cache else 'false'} "
    launch_cmd = (
        f"cd {BINARY_DIR} && LD_LIBRARY_PATH={BINARY_DIR} exec "
        f"./litert_lm_advanced_main --backend=cpu --max_output_tokens=400 "
        f"--benchmark=true {cache_flag}{dwc_flag}{threads_flag}--model_path={MODEL} "
        f"--input_prompt_file={PROMPT_FILE} "
        f"> {REMOTE_OUTPUT} 2>&1 & echo $!"
    )

    wall_start = time.time()
    pid_out = adb_shell(launch_cmd).strip()
    pid = pid_out.splitlines()[-1].strip() if pid_out else ""
    if not pid.isdigit():
        raise RuntimeError(f"Failed to obtain PID from device launch, got: {pid_out!r}")

    cpu_start = None
    last_cpu = None
    peak_rss_kb = 0
    last_poll_time = wall_start

    while True:
        reading = poll_proc(pid)
        now = time.time()
        if reading is None:
            break  # process has exited
        vmhwm_kb, utime, stime = reading
        if vmhwm_kb:
            peak_rss_kb = max(peak_rss_kb, vmhwm_kb)
        if utime is not None and stime is not None:
            if cpu_start is None:
                cpu_start = (utime, stime)
            last_cpu = (utime, stime)
            last_poll_time = now
        time.sleep(PROC_POLL_INTERVAL_S)

    wall_end = time.time()
    end_to_end_s = wall_end - wall_start

    cpu_pct = None
    if cpu_start is not None and last_cpu is not None and last_poll_time > wall_start:
        delta_ticks = (last_cpu[0] - cpu_start[0]) + (last_cpu[1] - cpu_start[1])
        delta_cpu_s = delta_ticks / tick_rate
        delta_wall_s = last_poll_time - wall_start
        if delta_wall_s > 0:
            cpu_pct = round(100.0 * delta_cpu_s / delta_wall_s, 1)

    thermal_end = get_thermal_status()
    log_text = adb_shell(f"cat {REMOTE_OUTPUT}")

    metrics = parse_benchmark_info(log_text)
    metrics.update({
        "end_to_end_latency_s": round(end_to_end_s, 3),
        "peak_rss_kb": peak_rss_kb or None,
        "cpu_pct": cpu_pct,
        "thermal_status_end": thermal_end,
    })
    return metrics, log_text


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", required=True,
                         help="Configuration name, e.g. baseline, threads_4")
    parser.add_argument("--threads", type=int, default=None,
                         help="--num_cpu_threads value; omit for baseline/auto")
    parser.add_argument("--cache-dir", default=":memory",
                         help="--cache_dir value (default: :memory, per OPTIMIZATION_PARAMETERS.md Lever 1)")
    parser.add_argument("--disable-weight-cache", action="store_true",
                         help="Pass --disable_weight_cache=true (Lever 2 configuration)")
    parser.add_argument("--n-runs", type=int, required=True,
                         help="Number of runs to perform in this invocation")
    parser.add_argument("--output", required=True,
                         help="CSV path to append rows to (created with header if new)")
    parser.add_argument("--run-type", default="valid", choices=["warmup", "valid"],
                         help="Tag for this batch (warmup rows are excluded from stats)")
    args = parser.parse_args()

    try:
        tick_rate = get_clk_tck()
    except AdbError as exc:
        print(f"\nFATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not output_path.exists()

    with open(output_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        for i in range(1, args.n_runs + 1):
            print(f"\n=== {args.config} | run {i}/{args.n_runs} ({args.run_type}) ===")
            try:
                thermal_start, battery_start = readiness_gate()
            except AdbError as exc:
                print(f"\nFATAL: {exc}", file=sys.stderr)
                print(f"Aborting after {i - 1}/{args.n_runs} completed run(s). "
                      f"Fix the adb connection and re-run for the remaining runs.",
                      file=sys.stderr)
                sys.exit(1)

            print(f"  [readiness] GREEN LIGHT (thermal={thermal_start}, battery={battery_start}%)")

            validity = "valid"
            exclusion_reason = ""
            try:
                metrics, _log_text = run_one(
                    args.threads, tick_rate,
                    cache_dir=args.cache_dir,
                    disable_weight_cache=args.disable_weight_cache,
                )
                if metrics.get("decode_tokens") is None:
                    validity = "invalid"
                    exclusion_reason = "failed_to_parse_benchmark_info"
            except AdbError as exc:
                print(f"\nFATAL: {exc}", file=sys.stderr)
                print(f"Aborting after {i - 1}/{args.n_runs} completed run(s). "
                      f"Fix the adb connection and re-run for the remaining runs.",
                      file=sys.stderr)
                sys.exit(1)
            except Exception as exc:  # noqa: BLE001 -- log and continue campaign
                metrics = {}
                validity = "invalid"
                exclusion_reason = f"exception: {exc}"

            row = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "config": args.config,
                "threads": args.threads if args.threads is not None else "auto",
                "run_type": args.run_type,
                "thermal_status_start": thermal_start,
                "battery_pct_start": battery_start,
                "validity": validity,
                "exclusion_reason": exclusion_reason,
                **metrics,
            }
            writer.writerow(row)
            f.flush()

            print(
                f"  latency={row.get('end_to_end_latency_s')}s  "
                f"decode={row.get('decode_speed_tok_s')} tok/s  "
                f"peak_rss={row.get('peak_rss_kb')} kB  "
                f"cpu={row.get('cpu_pct')}%  "
                f"validity={validity}"
            )

            time.sleep(INTER_RUN_DELAY_S)

    print(f"\nDone. {args.n_runs} run(s) appended to {output_path}")


if __name__ == "__main__":
    main()