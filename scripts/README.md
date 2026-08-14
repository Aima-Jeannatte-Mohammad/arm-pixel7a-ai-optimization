# scripts/

## `run_config.py` — Phase B measurement harness

Runs N measurements of **one** configuration against the frozen workload
on the connected device and appends one CSV row per run. It is the
executable form of `docs/02_protocols/MEASUREMENT_PROCEDURE.md`.

Per run it: enforces the readiness gate → launches the binary on-device →
polls `/proc/<PID>` for peak RSS and CPU time → times end-to-end
latency → parses the `BenchmarkInfo` block → writes the row.

**Requires**: `adb` on `PATH`, the device reachable (wireless ADB, USB
disconnected), and binary + `.so` + model + `phase_b_prompt.txt` already
pushed to `/data/local/tmp/`. Python standard library only.

```bash
# stabilization batch (kept in the CSV, excluded from statistics)
python scripts/run_config.py --config baseline --n-runs 5  --run-type warmup --output data/raw/baseline.csv
# valid sample
python scripts/run_config.py --config baseline --n-runs 30 --run-type valid  --output data/raw/baseline.csv
# a specific thread count
python scripts/run_config.py --config threads_4 --threads 4 --n-runs 30 --run-type valid --output data/raw/threads_4.csv
# Lever 2 (cache disabled) at the winning thread count
python scripts/run_config.py --config threads_4_nocache --threads 4 --disable-weight-cache --n-runs 30 --run-type valid --output data/raw/threads_4_nocache.csv
```

| Flag | Notes |
|---|---|
| `--config` | Name written to the CSV and used as the dashboard label |
| `--threads` | `--num_cpu_threads` value. **Omit for baseline** — `0` is not confirmed equivalent to omitting the flag |
| `--cache-dir` | Default `:memory`, the Lever 1 fixed value |
| `--disable-weight-cache` | Lever 2 configuration |
| `--n-runs`, `--run-type`, `--output` | Batch size, `warmup`/`valid` tag, target CSV (header written if new) |

### Behaviour worth knowing before modifying it

- **The binary is launched with `exec`**, so the captured PID is the
  binary's and not an intermediate shell's. Without this, `/proc` polling
  measures the wrong process and reports plausible, wrong resource
  numbers (ISSUE_LOG.md #10).
- **adb-level failures raise `AdbError` and abort immediately** — they are
  never treated as "device not ready". Conflating the two previously
  caused an infinite retry loop that hid the real problem
  (ISSUE_LOG.md #11).
- **A run that fails `BenchmarkInfo` parsing is written as `invalid` with
  a reason**, never dropped.
- **`cpu_pct` is diagnostic, not a profiler.** Percent of one core,
  top-style, sampled at ~1 Hz over wireless adb — each poll is its own
  `adb shell` round trip. It says nothing about *which* cores ran the
  threads.
- **Tunable constants sit at the top of the file**: `THERMAL_OK`,
  `BATTERY_MIN`, `READINESS_POLL_INTERVAL_S`, `READINESS_MAX_WAIT_S`,
  `PROC_POLL_INTERVAL_S`, `INTER_RUN_DELAY_S`, plus the `/data/local/tmp`
  paths and the model filename. Change these when porting to another
  device — and record the change.

Thresholds and sampling rules are defined in
`docs/02_protocols/OPTIMIZATION_PARAMETERS.md`; this script implements
them rather than deciding them.

**What it does not enforce.** The harness runs the batch size you pass on
the command line — it does not evaluate the stabilization criterion, does
not randomize configuration order, does not check the 60 s
inter-configuration recovery interval, and does not verify that the device
stayed off power. Those four remain operator responsibilities, and all four
were missed at least once in this campaign
(`docs/03_experiments_results/OPTIMIZATION_RESULTS.md`, "Realized vs.
specified"). Automating them is the highest-value change to this script.
