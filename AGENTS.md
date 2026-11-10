# Repository Agent Instructions

## Delivery

- After completing each user-requested repository change, run the relevant validation, stage only files changed for that request, create a descriptive commit, and push it to `origin main`.
- Do not commit, revert, or otherwise modify unrelated user changes.
- In the final response for a repository change, include the commit hash and the appropriate build commands below.

## Branch Isolation: main / lemur vs old-android (old-version)

`main` and `lemur*` are the modern baseline; `old-android` / `old-version` carry the Android 9 (API 28)
car head-unit adaptation. Keep them strictly separated:

- A fix or feature for `old-android` / `old-version` stays on that branch. Do not port it to `main` or `lemur`.
- A change made for `main` or `lemur` must not be merged, cherry-picked, or copied into `old-android` /
  `old-version` unless the user explicitly asks for that merge.
- Never resolve an `old-android` build failure by pulling in `lemur`/`main` code paths. Fix the
  `old-android` side instead (branch-gated patching), and the other way round.
- Downstream patching must stay branch-gated: scripts decide via the current git branch, `OLD_ANDROID`,
  `OLD_VERSION`, or `CAR_COMPAT`; verify a patch only runs on its intended branch before changing it.

## Build With Local Proxy

Run all commands from the repository root. The configured local proxy is `http://192.168.2.1:37896`.

### Full Build

Use a full build for a fresh checkout, after Chromium/Vanadium version changes, or whenever `chromium/src/chrome/VERSION` does not match the Chromium version required by `vanadium/args.gn`.

```bash
git -c http.proxy=http://192.168.2.1:37896 pull --ff-only origin main
git submodule sync --recursive
git -c http.proxy=http://192.168.2.1:37896 \
    submodule update --init --recursive --jobs 8

BUILD_PROXY=http://192.168.2.1:37896 \
BUILD_ARM=0 \
BUILD_ARM64=1 \
BUILD_AAB=0 \
NINJA_JOBS=14 \
./build.sh
```

### Incremental Local Build

Use this only after a successful full build and only when the checked-out Chromium version matches `vanadium/args.gn`. `FAST_LOCAL_BUILD=1` skips source preparation and `patch.sh`, so always apply new downstream changes with `hotfix_existing_src.sh` first.

```bash
git -c http.proxy=http://192.168.2.1:37896 pull --ff-only origin main
git submodule sync --recursive
git -c http.proxy=http://192.168.2.1:37896 \
    submodule update --init --recursive --jobs 8

./hotfix_existing_src.sh chromium/src

FAST_LOCAL_BUILD=1 \
BUILD_PROXY=http://192.168.2.1:37896 \
BUILD_ARM=0 \
BUILD_ARM64=1 \
BUILD_AAB=0 \
NINJA_JOBS=14 \
./build.sh
```

### Version Check

Before an incremental build, compare the required and checked-out Chromium versions:

```bash
grep android_default_version_name vanadium/args.gn
awk -F= '
    /^(MAJOR|MINOR|BUILD|PATCH)=/ { value[$1] = $2 }
    END { print value["MAJOR"] "." value["MINOR"] "." value["BUILD"] "." value["PATCH"] }
' chromium/src/chrome/VERSION
```

If the versions differ, do not use `FAST_LOCAL_BUILD=1`; run the full build instead.

## Remote Build Machine

The configured Chromium build machine is reachable at `192.168.2.30`.

- Repository: `/root/android-helium-browser`
- Build branch: `main`
- Chromium source used for this work: `157.0.8103.38`
- Chromium source directory: `/root/android-helium-browser/chromium/src`
- Network proxy: `http://192.168.2.1:37896`
- Build architecture: ARM64 only by default (`BUILD_ARM=0`, `BUILD_ARM64=1`)
- Local SSH alias: `helium-build` (configured in `~/.ssh/config`, not in this repository)

The local SSH private key is stored at `~/.ssh/android_helium_build`. Its public key is installed on the build machine. Verify access with `ssh helium-build 'hostname'`; do not copy either key into the repository.

Use the following from this repository root to update the build machine's `main` checkout and prepare its source:

```bash
ssh helium-build 'cd /root/android-helium-browser && git -c http.proxy=http://192.168.2.1:37896 pull --ff-only origin main && git submodule sync --recursive && git -c http.proxy=http://192.168.2.1:37896 submodule update --init --recursive --jobs 8'
```

To run the ARM64 full build remotely:

```bash
ssh helium-build 'cd /root/android-helium-browser && BUILD_PROXY=http://192.168.2.1:37896 BUILD_ARM=0 BUILD_ARM64=1 BUILD_AAB=0 NINJA_JOBS=14 ./build.sh'
```

Use a full build for a fresh checkout, after a Chromium/Vanadium version change, or whenever the source version differs from `vanadium/args.gn`. For a downstream-only update after a successful full build and a matching Chromium version, run:

```bash
ssh helium-build 'cd /root/android-helium-browser && ./hotfix_existing_src.sh chromium/src && FAST_LOCAL_BUILD=1 BUILD_PROXY=http://192.168.2.1:37896 BUILD_ARM=0 BUILD_ARM64=1 BUILD_AAB=0 NINJA_JOBS=14 ./build.sh'
```
