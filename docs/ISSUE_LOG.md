# Issue Log

Annex document tracking technical issues encountered during setup and
execution, and how each was resolved. Not part of the core protocol
documentation (see README.md for the full required document list) —
this is supplementary evidence of methodical process.

| # | Phase | Issue | Root cause | Resolution |
|---|---|---|---|---|
| 1 | Repo setup | `python -m venv .venv` failed with `KeyboardInterrupt` | Process interrupted during `ensurepip` step (likely accidental Ctrl+C or antivirus scan delay mistaken for a hang) | Removed the partial `.venv` folder and re-ran the command without interrupting it |
| 2 | Repo setup | `.gitignore` contained literal PowerShell here-string syntax (`@"..."@`) instead of its intended content | Copy-pasting a multi-line PowerShell here-string block into an already-open interactive terminal does not execute it as a command | Deleted the file and recreated it directly in the VS Code editor instead of via terminal here-string |
| 3 | Repo setup | GitHub blocked merging the first PR with "Review required" despite solo development | Default branch protection rule ("Require a pull request before merging") auto-enabled "Require approvals," which cannot be satisfied by the PR author on their own PR | Disabled "Require approvals" in the branch protection rule; enabled "Require status checks to pass" (CI) instead, which fits solo development |
| 4 | Runtime selection | Branch protection rule showed "Not enforced" even after configuration | GitHub does not enforce branch protection rules on **private** repositories on the free plan | Changed repository visibility to public (also appropriate for a submission meant to be reusable by other developers) |
| 5 | Runtime selection | `pip`-installed `litert-lm` CLI has no way to target the connected Pixel 7 | The CLI installed via `pip` runs inference locally on the host machine only; Android execution requires a separately built, device-targeted binary | Switched to building `litert_lm_main` from source via Bazel with `--config=android_arm64`, using WSL2 + Android NDK r28b |
| 6 | Runtime deployment | `CANNOT LINK EXECUTABLE`: `libGemmaModelConstraintProvider.so` not found | The natively-built `litert_lm_main` binary depends on a shared library not produced by its own Bazel build target — it is a prebuilt dependency referenced via `//prebuilt/android_arm64:...` in the BUILD file, not compiled from source by the `litert_lm_main` build | Located the file in the cloned repo's `prebuilt/android_arm64/` directory, confirmed it was a real binary (not a Git LFS pointer), copied it alongside the main binary and pushed both to the device |
| 7 | Runtime deployment | `CANNOT LINK EXECUTABLE` persisted even after pushing the missing `.so` to the same device directory as the binary | Android's dynamic linker does not automatically search an executable's own directory for shared libraries on `/data/local/tmp/` | Explicitly set `LD_LIBRARY_PATH=/data/local/tmp` on every invocation of the binary via `adb shell` |

Add new rows chronologically as issues arise during the remaining
phases (model download, campaign execution, dashboard build, etc.).