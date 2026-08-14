# Device Characterization

> **Scope**: what the reference hardware is, and which measurement
> signals are reachable on it without root. Every value here is a
> reading from the device (`getprop`, `/proc`, `dumpsys`), never a
> specification lookup or a datasheet figure — a spec sheet describes a
> product line, and the numbers in this project are scoped to one physical
> unit.

All results in this project are scoped to this single physical device.

## Reference device

| Property | Value | Source |
|---|---|---|
| Model | Google Pixel 7 | `ro.product.model` |
| Manufacturer | Google | `getprop` |
| Codename | `panther` | `ro.hardware` |
| SoC | Google Tensor G2 (`gs201`) | `ro.board.platform` |
| Android version | 16 | `ro.build.version.release` |
| Android SDK | 36 | `ro.build.version.sdk` |

## CPU topology

8 cores, heterogeneous 2+2+4, from `/proc/cpuinfo`:

| Cores | CPU part | Variant | Cluster |
|---|---|---|---|
| 0-3 | 0xd05 | 0x2 | Cortex-A55 (little) |
| 4-5 | 0xd41 | 0x1 | Cortex-A78 (mid) |
| 6-7 | 0xd44 | 0x1 | Cortex-X1 (big) |

This layout is what the thread-count grid (1 / 2 / 4 / 8) is derived
from: 2 matches the X1 cluster, 4 matches A78+X1, 8 matches all cores.
See OPTIMIZATION_PARAMETERS.md.

**Interpretation boundary**: CPU part and variant values identify silicon
revision, not the public "A55/A78/X1" naming. The mapping above is
inferred from documented Tensor G2 topology, not decoded from the raw
values — stated as interpretation, not as raw measurement.

**Feature flags** (identical on all 8 cores): `fp asimd evtstrm aes pmull
sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop
asimddp`.

No `i8mm`, no SVE. This is the Armv8.2-A baseline with extensions up to
Armv8.4-A dot product, and it is the direct reason the i8mm/KleidiAI
lever was rejected rather than benchmarked — see
../01_research/OPTIMIZATION_PRE_SCREENING.md.

## Memory

From `/proc/meminfo`:

- Total: 7,643,344 kB (~7.3 GB)
- Available at time of check: 2,111,556 kB (~2 GB) — varies with system
  load, not a fixed baseline. This headroom is why the E2B model variant
  was chosen over larger ones (see MODEL_SELECTION_PROTOCOL.md)
- Swap: 3,821,668 kB (zram-based; `Zram: 884836 kB` active at check
  time)

**On `MemAvailable` vs. measured peak RSS.** Phase B measures peak RSS of
2,130-2,236 MB in every thread-count configuration, and 4,017 MB with the
weight cache disabled — both above the ~2 GB `MemAvailable` reading here.
That is not a contradiction: `MemAvailable` is an instantaneous kernel
estimate of what a new allocation could claim without swapping, while
`VmHWM` is a high-water mark that counts mapped file pages the process has
touched, including the memory-mapped 2.59 GB model. Between them the kernel
reclaims page cache and zram absorbs pressure. No run OOM'd. The practical
consequence is that `MemAvailable` is a poor sizing signal for a
memory-mapped model, and the E2B choice is better justified by total RAM
(~7.3 GB) than by the available figure.

## Thermal signal

Temperature is read **only** as Android's aggregate thermal status
(`PowerManager.getCurrentThermalStatus()`, exposed by
`dumpsys thermalservice`), never as raw °C. Android's own documentation
frames this as a deliberate platform design choice: status codes indicate
throttling risk more reliably than raw values, which vary by sensor and
device.

Confirmed accessible without root:

- `Thermal Status: 0` (THERMAL_STATUS_NONE) at check time
- `ThermalHAL AIDL 3` connected (`HAL Ready: true`)
- Per-sensor values (BIG, MID, LITTLE, TPU, G3D, battery, skin) with
  individual throttling tables are also exposed. These are **not** used:
  the readiness gate consumes only the aggregate `Thermal Status`
  integer. `getThermalHeadroom()` is likewise not used
- No root, no `thermal_zoneX/temp` sysfs access

## Battery signal

From `dumpsys battery`, confirmed queryable without root: `level` /
`scale`, `status`, `Charging state`, `AC powered`, `technology` (Li-ion).

`status` and `Charging state` are **different signals** and can appear to
contradict each other — a near-full battery can report "not charging"
while still plugged in (ISSUE_LOG.md #12). The readiness gate uses
`level` only; power connection is handled as a session-level
precondition (device on battery, wireless ADB) rather than a per-run
check. Both decisions are frozen in OPTIMIZATION_PARAMETERS.md.

## Status of these readings

This characterization was performed over `adb shell` during project
setup, on a USB-connected, AC-powered device. That is **not** the state
required for measurement runs — measurement runs on battery over
wireless ADB. The purpose here is narrower: to confirm that the topology
is what it is claimed to be, and that both readiness signals are
reliably queryable without root or a custom app.
