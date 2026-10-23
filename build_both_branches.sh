#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$SCRIPT_DIR"

DEFAULT_PROXY="${BUILD_PROXY:-${https_proxy:-${http_proxy:-${HTTPS_PROXY:-${HTTP_PROXY:-http://192.168.2.1:37896}}}}}"
CAR_COMPAT="${CAR_COMPAT:-0}"
BUILD_OLD_ANDROID="${BUILD_OLD_ANDROID:-1}"
BUILD_ARM="${BUILD_ARM:-1}"
BUILD_ARM64="${BUILD_ARM64:-1}"
BUILD_AAB="${BUILD_AAB:-0}"
NINJA_JOBS="${NINJA_JOBS:-14}"
AUTO_PULL="${AUTO_PULL:-1}"
USER_FAST_LOCAL_BUILD="${FAST_LOCAL_BUILD:-}"
AUTO_RELEASE="${AUTO_RELEASE:-1}"
SKIP_IF_EXISTS="${SKIP_IF_EXISTS:-1}"
FORCE_REBUILD="${FORCE_REBUILD:-0}"
ENABLE_V2_SIGNING="${ENABLE_V2_SIGNING:-1}"

# 导出代理环境变量，供后续 git / gh / curl 等工具使用
export HTTP_PROXY="$DEFAULT_PROXY"
export HTTPS_PROXY="$DEFAULT_PROXY"
export http_proxy="$DEFAULT_PROXY"
export https_proxy="$DEFAULT_PROXY"
export all_proxy="$DEFAULT_PROXY"
export ALL_PROXY="$DEFAULT_PROXY"

# 解析需要编译的目标分支列表
# 优先级：
# 1. 命令行参数（如：./build_both_branches.sh old-android 或 ./build_both_branches.sh main old-android）
# 2. 环境变量 BUILD_BRANCHES（如：BUILD_BRANCHES="old-android"）
# 3. 默认分支：main 与 lemur-style-app-menu；若 BUILD_OLD_ANDROID=1（或 CAR_COMPAT=1），则追加 old-android 分支
TARGET_BRANCHES=()
if [ "$#" -gt 0 ]; then
    TARGET_BRANCHES=("$@")
elif [ -n "${BUILD_BRANCHES:-}" ]; then
    IFS=', ' read -r -a TARGET_BRANCHES <<< "$BUILD_BRANCHES"
else
    TARGET_BRANCHES=("main" "lemur-style-app-menu")
    if [ "$BUILD_OLD_ANDROID" = "1" ]; then
        TARGET_BRANCHES+=("old-android")
    fi
fi

BRANCHES=()
for b in "${TARGET_BRANCHES[@]}"; do
    b_trimmed="$(echo "$b" | xargs)"
    # 兼容下划线输入 old_android 自动映射为规范分支名 old-android
    if [ "$b_trimmed" = "old_android" ]; then
        b_trimmed="old-android"
    fi
    if [ -n "$b_trimmed" ]; then
        BRANCHES+=("$b_trimmed")
    fi
done

if [ "${#BRANCHES[@]}" -eq 0 ]; then
    echo "ERROR: No branches specified to build." >&2
    exit 1
fi

VERSION_ARGS="$SCRIPT_DIR/vanadium/args.gn"
VERSION=$(grep -m1 -o '[0-9]\+\(\.[0-9]\+\)\{3\}' "$VERSION_ARGS" || true)

if [ -z "$VERSION" ]; then
    echo "ERROR: Unable to read Chromium version from $VERSION_ARGS" >&2
    exit 1
fi

read_chromium_version() {
    awk -F= '
        /^(MAJOR|MINOR|BUILD|PATCH)=/ { value[$1] = $2 }
        END {
            print value["MAJOR"] "." value["MINOR"] "." value["BUILD"] "." value["PATCH"]
        }
    ' "$1"
}

# 自动判断本地 Chromium 源码环境是否就绪以支持 FAST_LOCAL_BUILD=1
can_use_fast_local_build() {
    local depot_tools_dir="$SCRIPT_DIR/depot_tools"
    local chromium_src_dir="$SCRIPT_DIR/chromium/src"
    local version_file="$chromium_src_dir/chrome/VERSION"

    if [ ! -d "$depot_tools_dir" ] || [ ! -x "$depot_tools_dir/autoninja" ]; then
        return 1
    fi

    if [ ! -d "$chromium_src_dir/.git" ]; then
        return 1
    fi

    if [ ! -f "$version_file" ]; then
        return 1
    fi

    local local_ver
    local_ver="$(read_chromium_version "$version_file" 2>/dev/null || true)"
    local target_ver
    target_ver="$(grep -m1 -o '[0-9]\+\(\.[0-9]\+\)\{3\}' "$VERSION_ARGS" 2>/dev/null || true)"
    target_ver="${target_ver:-$VERSION}"
    if [ "$local_ver" != "$target_ver" ]; then
        return 1
    fi

    return 0
}

get_effective_fast_local_build() {
    if [ "$USER_FAST_LOCAL_BUILD" = "1" ]; then
        if ! can_use_fast_local_build; then
            echo "0"
            return 0
        fi
        echo "1"
        return 0
    elif [ -n "$USER_FAST_LOCAL_BUILD" ]; then
        echo "$USER_FAST_LOCAL_BUILD"
        return 0
    fi

    if can_use_fast_local_build; then
        echo "1"
    else
        echo "0"
    fi
}

get_branch_prefix() {
    local branch="$1"
    if [ "$branch" = "main" ]; then
        echo "$VERSION"
    else
        local branch_tag
        branch_tag="$(printf '%s' "$branch" | tr -c 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
        echo "${VERSION}-${branch_tag}"
    fi
}

check_branch_artifacts() {
    local branch="$1"
    local prefix
    prefix="$(get_branch_prefix "$branch")"
    local release_dir="$SCRIPT_DIR/chromium/src/out/release"

    if [ "$BUILD_ARM" = "1" ] && [ ! -s "$release_dir/${prefix}-armeabi-v7a.apk" ]; then
        return 1
    fi
    if [ "$BUILD_ARM64" = "1" ] && [ ! -s "$release_dir/${prefix}-arm64-v8a.apk" ]; then
        return 1
    fi
    if [ "$BUILD_AAB" = "1" ] && [ ! -s "$release_dir/${prefix}-arm64-v8a.aab" ]; then
        return 1
    fi

    # 仅针对 old-android 分支检查既有产物是否确实具备 V2 签名；若缺失则强制触发重新构建签名
    if [ "$branch" = "old-android" ]; then
        local apksigner_bin
        apksigner_bin=$(find "$SCRIPT_DIR/chromium/src/third_party/android_sdk" -name apksigner 2>/dev/null | sort | tail -n 1 || true)
        if [ -n "$apksigner_bin" ] && [ -x "$apksigner_bin" ]; then
            if [ "$BUILD_ARM64" = "1" ] && [ -s "$release_dir/${prefix}-arm64-v8a.apk" ]; then
                if ! "$apksigner_bin" verify --verbose "$release_dir/${prefix}-arm64-v8a.apk" 2>&1 | grep -q "Verified using v2 scheme (APK Signature Scheme v2): true"; then
                    echo "Notice: Existing ${prefix}-arm64-v8a.apk is missing V2 signature. Invalidating cache to trigger signing."
                    return 1
                fi
            fi
            if [ "$BUILD_ARM" = "1" ] && [ -s "$release_dir/${prefix}-armeabi-v7a.apk" ]; then
                if ! "$apksigner_bin" verify --verbose "$release_dir/${prefix}-armeabi-v7a.apk" 2>&1 | grep -q "Verified using v2 scheme (APK Signature Scheme v2): true"; then
                    echo "Notice: Existing ${prefix}-armeabi-v7a.apk is missing V2 signature. Invalidating cache to trigger signing."
                    return 1
                fi
            fi
        fi
    fi

    return 0
}

is_branch_up_to_date() {
    local branch="$1"
    local stamp_file="$SCRIPT_DIR/chromium/src/out/release/.built_commit_${branch}"

    if [ "$FORCE_REBUILD" = "1" ]; then
        return 1
    fi

    if [ "$SKIP_IF_EXISTS" != "1" ]; then
        return 1
    fi

    if ! check_branch_artifacts "$branch"; then
        return 1
    fi

    # 2. 检查记录的 commit stamp 文件是否存在
    if [ ! -f "$stamp_file" ]; then
        return 1
    fi

    # 3. 获取目标分支当前最新的 commit
    local current_head
    current_head="$(git rev-parse "refs/heads/$branch" 2>/dev/null || true)"
    if [ -z "$current_head" ]; then
        return 1
    fi

    # 4. 对比已编译记录的 commit 是否与目标分支最新 commit 一致
    local built_head
    built_head="$(cat "$stamp_file" 2>/dev/null || true)"
    if [ "$built_head" = "$current_head" ]; then
        return 0
    fi

    return 1
}

switch_branch() {
    local target_branch="$1"
    local current_branch
    current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [ "$current_branch" != "$target_branch" ]; then
        if [ -n "$(git status --porcelain -uno --ignore-submodules=dirty)" ]; then
            echo "WARNING: Working tree has uncommitted modifications before switching to '$target_branch':" >&2
            git status --short --ignore-submodules=dirty >&2
        fi
        git checkout "$target_branch"
    fi

    # 切换分支后，自动重置并对齐当前分支所要求的 submodule commit，防止跨分支构建时子模块游离或版本滞后
    if [ -d "$SCRIPT_DIR/vanadium" ]; then
        if [ -n "$(git -C "$SCRIPT_DIR/vanadium" status --porcelain 2>/dev/null || true)" ]; then
            git -C "$SCRIPT_DIR/vanadium" reset --hard >/dev/null 2>&1 || true
            git -C "$SCRIPT_DIR/vanadium" clean -fd >/dev/null 2>&1 || true
        fi
        local expected_v_commit actual_v_commit
        expected_v_commit="$(git ls-tree HEAD vanadium 2>/dev/null | awk '{print $3}' || true)"
        actual_v_commit="$(git -C "$SCRIPT_DIR/vanadium" rev-parse HEAD 2>/dev/null || true)"
        if [ -n "$expected_v_commit" ] && [ "$actual_v_commit" != "$expected_v_commit" ]; then
            echo "Aligning vanadium submodule to commit required by '$target_branch' ($expected_v_commit)..."
            git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" submodule update --init --recursive vanadium
        fi
    fi
}

sync_git_from_remote() {
    echo "=========================================================="
    echo " [Git Sync] Checking and pulling latest updates from GitHub..."
    echo "=========================================================="

    if [ -n "$(git status --porcelain -uno --ignore-submodules=dirty 2>/dev/null || true)" ]; then
        echo "WARNING: Working tree has uncommitted changes. Skipping git sync to protect local files." >&2
        return 0
    fi

    local self_script="${BASH_SOURCE[0]}"
    local hash_before=""
    if [ -f "$self_script" ]; then
        hash_before="$(sha256sum "$self_script" 2>/dev/null | awk '{print $1}' || true)"
    fi

    echo "Fetching remote references from origin (proxy: $DEFAULT_PROXY)..."
    if ! git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" fetch origin '+refs/heads/*:refs/remotes/origin/*' --tags --force --prune; then
        echo "WARNING: git fetch encountered an issue. Proceeding with available local and remote references..." >&2
    fi

    for br in "${BRANCHES[@]}"; do
        if git show-ref --verify --quiet "refs/remotes/origin/$br"; then
            echo "Syncing branch '$br' with 'origin/$br'..."
            if git show-ref --verify --quiet "refs/heads/$br"; then
                switch_branch "$br"
                git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" merge --ff-only "origin/$br" || {
                    echo "Notice: Non-fast-forward merge for '$br'. Attempting pull..." >&2
                    git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" pull --no-tags origin "$br" || true
                }
            else
                git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" branch --track "$br" "origin/$br"
            fi
        else
            echo "Notice: Remote branch 'origin/$br' not found. Using local '$br' branch."
        fi
    done

    # 确保 vanadium 子模块处于干净且同步的状态
    if [ -d "$SCRIPT_DIR/vanadium" ]; then
        if [ -n "$(git -C "$SCRIPT_DIR/vanadium" status --porcelain 2>/dev/null || true)" ]; then
            echo "Resetting uncommitted changes in vanadium submodule..."
            git -C "$SCRIPT_DIR/vanadium" reset --hard >/dev/null 2>&1 || true
            git -C "$SCRIPT_DIR/vanadium" clean -fd >/dev/null 2>&1 || true
        fi
    fi
    # 同步完成后切回第一个目标分支（通常为 main），确保后续构建从预期分支开始
    if [ "${#BRANCHES[@]}" -gt 0 ]; then
        switch_branch "${BRANCHES[0]}"
    fi
    echo "Syncing git submodules..."
    git -c "http.proxy=$DEFAULT_PROXY" -c "https.proxy=$DEFAULT_PROXY" submodule update --init --recursive

    # 若拉取更新了当前脚本自身，重新加载并执行最新版本
    local hash_after=""
    if [ -f "$self_script" ]; then
        hash_after="$(sha256sum "$self_script" 2>/dev/null | awk '{print $1}' || true)"
    fi

    if [ -n "$hash_before" ] && [ -n "$hash_after" ] && [ "$hash_before" != "$hash_after" ]; then
        echo "=========================================================="
        echo " Notice: $(basename "$self_script") was updated from GitHub."
        echo " Re-executing script to run the updated version..."
        echo "=========================================================="
        AUTO_PULL=0 exec "$self_script" "$@"
    fi
}

build_branch() {
    local branch="$1"
    local step_num="$2"
    local total_steps="${3:-${#BRANCHES[@]}}"

    echo "=========================================================="
    echo " [$step_num/$total_steps] Checking '$branch' branch..."
    echo "=========================================================="

    if is_branch_up_to_date "$branch"; then
        local prefix
        prefix="$(get_branch_prefix "$branch")"
        echo "Artifacts for '$branch' already exist and branch is up to date:"
        ls -lh "$SCRIPT_DIR/chromium/src/out/release/${prefix}"* 2>/dev/null || true
        echo "Skipping build for '$branch'."
        return 0
    fi

    local prefix
    prefix="$(get_branch_prefix "$branch")"
    local release_dir="$SCRIPT_DIR/chromium/src/out/release"
    local stamp_file="$release_dir/.built_commit_${branch}"

    # 即将针对新 commit 构建：清理该分支在 out/release 中的旧产物与 stamp
    rm -f "$stamp_file"
    rm -f "$release_dir/${prefix}"* 2>/dev/null || true

    switch_branch "$branch"

    local effective_fast_local
    effective_fast_local="$(get_effective_fast_local_build)"

    if [ -n "$USER_FAST_LOCAL_BUILD" ]; then
        if [ "$USER_FAST_LOCAL_BUILD" = "1" ] && [ "$effective_fast_local" = "0" ]; then
            echo "Notice: FAST_LOCAL_BUILD=1 was requested, but local Chromium source tree is not ready or does not match repository target ($VERSION)."
            echo "Falling back to FAST_LOCAL_BUILD=0 for full upgrade/sync on this branch."
        else
            echo "User specified FAST_LOCAL_BUILD=$effective_fast_local"
        fi
    else
        if [ "$effective_fast_local" = "1" ]; then
            echo "Auto-detected: Chromium source tree and depot_tools are ready. Enabling FAST_LOCAL_BUILD=1 (fast incremental build)."
        else
            echo "Auto-detected: Chromium source tree or depot_tools not ready. Using FAST_LOCAL_BUILD=0 (full source preparation)."
        fi
    fi

    # 仅针对 old-android 分支自动启用 CAR_COMPAT=1 与 DISABLE_V3_SIGNING=1；main 与 lemur-style-app-menu 保持原样开启 V3
    local branch_car_compat="${CAR_COMPAT:-0}"
    local branch_disable_v3="${DISABLE_V3_SIGNING:-0}"
    if [ "$branch" = "old-android" ]; then
        branch_car_compat="1"
        branch_disable_v3="1"
    fi

    CAR_COMPAT="$branch_car_compat" \
    DISABLE_V3_SIGNING="$branch_disable_v3" \
    FAST_LOCAL_BUILD="$effective_fast_local" \
    BUILD_PROXY="$DEFAULT_PROXY" \
    http_proxy="$DEFAULT_PROXY" \
    https_proxy="$DEFAULT_PROXY" \
    HTTP_PROXY="$DEFAULT_PROXY" \
    HTTPS_PROXY="$DEFAULT_PROXY" \
    BUILD_ARM="$BUILD_ARM" \
    BUILD_ARM64="$BUILD_ARM64" \
    BUILD_AAB="$BUILD_AAB" \
    NINJA_JOBS="$NINJA_JOBS" \
    "$SCRIPT_DIR/build.sh"

    local current_head
    current_head="$(git rev-parse HEAD)"
    mkdir -p "$SCRIPT_DIR/chromium/src/out/release"
    printf '%s\n' "$current_head" > "$SCRIPT_DIR/chromium/src/out/release/.built_commit_${branch}"
}

echo "=== Build Configuration ==="
echo "BUILD_PROXY       : $DEFAULT_PROXY"
echo "AUTO_PULL         : $AUTO_PULL"
echo "BUILD_ARM         : $BUILD_ARM"
echo "BUILD_ARM64       : $BUILD_ARM64"
echo "BUILD_AAB         : $BUILD_AAB"
echo "BUILD_OLD_ANDROID : $BUILD_OLD_ANDROID"
echo "ENABLE_V2_SIGNING : $ENABLE_V2_SIGNING"
echo "BRANCHES          : ${BRANCHES[*]}"
echo "AUTO_RELEASE      : $AUTO_RELEASE"
echo "==========================="
echo ""

if [ "$AUTO_PULL" = "1" ]; then
    sync_git_from_remote
    echo ""
fi

total_branches="${#BRANCHES[@]}"
for i in "${!BRANCHES[@]}"; do
    branch="${BRANCHES[$i]}"
    step_num=$((i + 1))
    if [ "$i" -gt 0 ]; then
        echo ""
    fi
    build_branch "$branch" "$step_num" "$total_branches"
done

echo ""
echo "=========================================================="
echo " SUCCESS: Build process finished!"
echo " Branches: ${BRANCHES[*]}"
echo " Output files in chromium/src/out/release/:"
echo "=========================================================="
ls -lh "$SCRIPT_DIR/chromium/src/out/release"/*.apk 2>/dev/null || true

local_apksigner=$(find "$SCRIPT_DIR/chromium/src/third_party/android_sdk" -name apksigner 2>/dev/null | sort | tail -n 1 || true)
if [ -n "$local_apksigner" ] && [ -x "$local_apksigner" ]; then
    echo ""
    echo "=========================================================="
    echo " Signature Scheme Verification:"
    echo "=========================================================="
    for apk_file in "$SCRIPT_DIR/chromium/src/out/release"/*.apk; do
        if [ -f "$apk_file" ]; then
            echo "--- $(basename "$apk_file") ---"
            "$local_apksigner" verify --verbose "$apk_file" 2>&1 | grep -E "Verifies|Verified using" || true
        fi
    done
fi

if [ "$AUTO_RELEASE" = "1" ]; then
    echo ""
    echo "=========================================================="
    echo " [Auto Release] Publishing artifacts with MOVE=1 release.sh..."
    echo "=========================================================="
    PROXY_URL="$DEFAULT_PROXY" \
    BUILD_PROXY="$DEFAULT_PROXY" \
    http_proxy="$DEFAULT_PROXY" \
    https_proxy="$DEFAULT_PROXY" \
    HTTP_PROXY="$DEFAULT_PROXY" \
    HTTPS_PROXY="$DEFAULT_PROXY" \
    MOVE=1 \
    RELEASE_BRANCHES="${BRANCHES[*]}" \
    "$SCRIPT_DIR/release.sh"
fi
