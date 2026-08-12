# Device Characterization

## Reference device

- Model: Google Pixel 7 (confirmed via `adb shell getprop ro.product.model`
- Manufacturer: Google
- Codename: panther (`ro.hardware`)
- SoC: Google Tensor G2 (`ro.board.platform` = `gs201`)
- Android version: 16 (`ro.build.version.release`)
- Android SDK level: 36 (`ro.build.version.sdk`)

## CPU topology (accessible via `/proc/cpuinfo`)

8 cores confirmed, in a heterogeneous 2+2+4 configuration, matching
the publicly documented Tensor G2 layout:

| Cores | CPU part | Variant | Cluster (public naming) |
|---|---|---|---|
| 0-3 | 0xd05 | 0x2 | Cortex-A55 (little) |
| 4-5 | 0xd41 | 0x1 | Cortex-A78 (mid) |
| 6-7 | 0xd44 | 0x1 | Cortex-X1 (big) |

All cores report identical feature flags: `fp asimd evtstrm aes pmull
sha1 sha2 crc32 atomics fphp asimdhp cpuid asimdrdm lrcpc dcpop
asimddp`. No I8MM or SVE flags present — consistent with the Armv8.2-A
baseline (extensions up to Armv8.4-A dot product / asimddp) documented
in OPTIMIZATION_PRE_SCREENING.md's i8mm rejection.

Note: CPU part/variant values identify silicon revision, not which
public "A55/A78/X1" label applies — that mapping is inferred from
known Tensor G2 documentation (2+2+4, cores 0-3 little / 4-5 mid / 6-7
big), not decoded from the raw values alone. Stated here as
interpretation, not raw measurement, per the observation/interpretation
distinction required elsewhere in this project.

## Memory (accessible via `/proc/meminfo`)

- Total: 7,643,344 kB (~7.3 GB)
- Available at time of check: 2,111,556 kB (~2 GB) — variable,
  depends on concurrent system load; not a fixed baseline.
- Swap total: 3,821,668 kB (zram-based, `Zram: 884836 kB` active at
  time of check)

## Thermal Measurement Approach

Device temperature is measured exclusively via Android's thermal
status API (`PowerManager.getCurrentThermalStatus()`), not via a raw
°C reading, per the sourced rationale in the master prompt (§41):
Android's own documentation states this is a deliberate platform
design choice — status codes are more indicative of throttling risk
than raw values, which vary by sensor and device.

Confirmed accessible via `adb shell dumpsys thermalservice`:
- `Thermal Status: 0` (THERMAL_STATUS_NONE) observed at check time.
- `ThermalHAL AIDL 3` confirmed connected (`HAL Ready: true`).
- Multiple named sensors exposed (BIG, MID, LITTLE, TPU, G3D, battery,
  skin, etc.) with individual hot-throttling threshold tables — these
  are HAL-internal diagnostic values, not the project's readiness-gate
  signal. The readiness gate (per §41) uses ONLY the aggregate
  `Thermal Status` integer, not these per-sensor values.
- No root access used; no `thermal_zoneX/temp` sysfs paths accessed —
  consistent with the project's accessibility constraint (§3).
- Optional secondary signal (`getThermalHeadroom()`, §41) not yet
  tested at the shell level as of this writing; to be confirmed when
  building the readiness-check script.

## Battery / Charging state (accessible via `adb shell dumpsys battery`)

- `level` / `scale`: 100/100 (100%) at time of check
- `status`: 5 (BATTERY_STATUS_FULL)
- `Charging state`: 1 (charging) — device was connected to AC power
  (`AC powered: true`) at time of check, expected during USB-tethered
  development; must be explicitly controlled for during the actual
  measurement campaign (§43 readiness thresholds — charging state
  policy to be fixed before the campaign, not left to whatever state
  the device happens to be in during setup).
- `technology`: Li-ion

## Experimental state

This characterization was performed via `adb shell` commands during
project setup (see ISSUE_LOG.md, ARM_OPTIMIZATION runtime verification
sessions), on a USB-connected, AC-powered device. This is NOT the
readiness state required for actual measurement runs — it only
confirms that the three readiness-gate signals (thermal status,
battery level, charging state) are all reliably queryable via `adb`
without root access or a custom app.