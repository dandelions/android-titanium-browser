# Repository Agent Instructions

## Delivery

- After completing each user-requested repository change, run the relevant validation, stage only files changed for that request, create a descriptive commit, and push it to `origin main`.
- Do not commit, revert, or otherwise modify unrelated user changes.
- In the final response for a repository change, include the commit hash and the appropriate build commands below.

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
