#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VERSION_ARGS="$SCRIPT_DIR/vanadium/args.gn"
VERSION=$(grep -m1 -o '[0-9]\+\(\.[0-9]\+\)\{3\}' "$VERSION_ARGS" || true)

if [ -z "$VERSION" ]; then
    echo "Unable to read Vanadium version from $VERSION_ARGS" >&2
    exit 1
fi

# Load optional local GitHub CLI credentials without putting a token in this
# tracked script. gh recognizes GH_TOKEN and GITHUB_TOKEN automatically.
RELEASE_ENV_FILE="${RELEASE_ENV_FILE:-$SCRIPT_DIR/.codex/github.env}"
if [ -f "$RELEASE_ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$RELEASE_ENV_FILE"
fi

# Configure default local proxy for git and gh operations in release.sh.
DEFAULT_PROXY_URL="${PROXY_URL:-${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-http://192.168.2.1:37896}}}}}"
if [ -n "$DEFAULT_PROXY_URL" ]; then
    export HTTP_PROXY="${HTTP_PROXY:-$DEFAULT_PROXY_URL}"
    export HTTPS_PROXY="${HTTPS_PROXY:-$DEFAULT_PROXY_URL}"
    export http_proxy="${http_proxy:-$HTTP_PROXY}"
    export https_proxy="${https_proxy:-$HTTPS_PROXY}"
fi

git_repo() {
    if [ -n "$DEFAULT_PROXY_URL" ]; then
        git -c "http.proxy=$HTTP_PROXY" -c "https.proxy=$HTTPS_PROXY" -C "$SCRIPT_DIR" "$@"
    else
        git -C "$SCRIPT_DIR" "$@"
    fi
}

if [ -z "${TAG:-}" ]; then
    git_repo fetch origin '+refs/tags/*:refs/tags/*' >/dev/null 2>&1 || true
    head_tags=$(git_repo tag --points-at HEAD --list "v$VERSION*" | sort -V)
    if [ -n "$head_tags" ]; then
        TAG=$(printf '%s\n' "$head_tags" | tail -n 1)
    else
        TAG="v$VERSION"
    fi
fi
RELEASE_DIR="${RELEASE_DIR:-$SCRIPT_DIR/chromium/src/out/release}"
MOVE_TAG="${MOVE_TAG:-${MOVE:-0}}"

if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI is required. Install gh or run: gh auth login" >&2
    exit 1
fi

if [ ! -d "$RELEASE_DIR" ]; then
    echo "Release directory does not exist: $RELEASE_DIR" >&2
    exit 1
fi

files_list=$(mktemp)
trap 'rm -f "$files_list"' EXIT HUP INT TERM

found=0
add_release_file() {
    candidate="$1"
    [ -f "$candidate" ] || return 0
    if ! grep -Fqx "$candidate" "$files_list" 2>/dev/null; then
        printf '%s\n' "$candidate" >> "$files_list"
        found=1
    fi
}

is_branch_match() {
    file="$1"
    branch="$2"
    base=$(basename "$file")
    case "$branch" in
        main|HEAD)
            case "$base" in
                "$VERSION"-arm64-v8a.apk|"$VERSION"-armeabi-v7a.apk|"$VERSION"-x86_64.apk|"$VERSION"-x86.apk|"$VERSION"-arm64-v8a.aab|"$VERSION"-armeabi-v7a.aab)
                    return 0
                    ;;
                *)
                    return 1
                    ;;
            esac
            ;;
        lemur-style-app-menu|lemur)
            case "$base" in
                "$VERSION"-*lemur*.apk|"$VERSION"-*lemur*.aab|"$VERSION"-*lemon*.apk|"$VERSION"-*lemon*.aab)
                    return 0
                    ;;
                *)
                    return 1
                    ;;
            esac
            ;;
        old-android|old-version|old_android|old_version)
            case "$base" in
                "$VERSION"-*old-android*.apk|"$VERSION"-*old-android*.aab|"$VERSION"-*old-version*.apk|"$VERSION"-*old-version*.aab)
                    return 0
                    ;;
                *)
                    return 1
                    ;;
            esac
            ;;
        *)
            tag="$(printf '%s' "$branch" | tr -c 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
            case "$base" in
                "$VERSION-$tag"-*.apk|"$VERSION-$tag"-*.aab)
                    return 0
                    ;;
                *)
                    return 1
                    ;;
            esac
            ;;
    esac
}

is_abi_match() {
    file="$1"
    base=$(basename "$file")
    case "$base" in
        *.aab)
            [ "${BUILD_AAB:-0}" = "1" ] || return 1
            ;;
    esac
    case "$base" in
        *-armeabi-v7a.apk|*-armeabi-v7a.aab|*-arm.apk|*-arm.aab)
            if [ "${BUILD_ARM:-}" = "0" ]; then
                return 1
            fi
            if [ -z "${BUILD_ARM:-}" ] && [ "${BUILD_ARM64:-}" = "1" ]; then
                return 1
            fi
            ;;
        *-arm64-v8a.apk|*-arm64-v8a.aab|*-arm64.apk|*-arm64.aab)
            if [ "${BUILD_ARM64:-}" = "0" ]; then
                return 1
            fi
            ;;
    esac
    return 0
}

# 1. Positional file arguments take precedence
if [ "$#" -gt 0 ]; then
    for arg in "$@"; do
        if [ -f "$arg" ]; then
            add_release_file "$arg"
        elif [ -f "$RELEASE_DIR/$arg" ]; then
            add_release_file "$RELEASE_DIR/$arg"
        else
            echo "Warning: specified release file not found: $arg" >&2
        fi
    done
# 2. RELEASE_FILES environment variable
elif [ -n "${RELEASE_FILES:-}" ]; then
    for rf in $RELEASE_FILES; do
        if [ -f "$rf" ]; then
            add_release_file "$rf"
        elif [ -f "$RELEASE_DIR/$rf" ]; then
            add_release_file "$RELEASE_DIR/$rf"
        else
            echo "Warning: specified release file not found: $rf" >&2
        fi
    done
# 3. Explicit opt-in to release all version artifacts
elif [ "${RELEASE_ALL:-0}" = "1" ]; then
    for file in "$RELEASE_DIR/$VERSION"-*.apk "$RELEASE_DIR/$VERSION"-*.aab; do
        [ -f "$file" ] || continue
        add_release_file "$file"
    done
# 4. Outputs recorded by build.sh for the latest build (if present)
elif [ -f "$RELEASE_DIR/.last_build_outputs" ] && [ -s "$RELEASE_DIR/.last_build_outputs" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line_trimmed=$(printf '%s' "$line" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
        [ -n "$line_trimmed" ] || continue
        target_f=""
        if [ -f "$RELEASE_DIR/$line_trimmed" ]; then
            target_f="$RELEASE_DIR/$line_trimmed"
        elif [ -f "$line_trimmed" ]; then
            target_f="$line_trimmed"
        fi
        if [ -n "$target_f" ]; then
            add_release_file "$target_f"
        fi
    done < "$RELEASE_DIR/.last_build_outputs"
fi

# 5. Fallback: match by current branch (or RELEASE_BRANCHES) and target ABIs
if [ "$found" -eq 0 ]; then
    if [ -n "${RELEASE_BRANCHES:-}" ]; then
        target_branches="$RELEASE_BRANCHES"
    elif [ -n "${OUTPUT_BRANCH_TAG:-}" ]; then
        target_branches="$OUTPUT_BRANCH_TAG"
    else
        target_branches="$(git_repo rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    fi
    [ -n "$target_branches" ] || target_branches="main"

    for file in "$RELEASE_DIR/$VERSION"-*.apk "$RELEASE_DIR/$VERSION"-*.aab; do
        [ -f "$file" ] || continue
        is_abi_match "$file" || continue
        matched=0
        for br in $target_branches; do
            if is_branch_match "$file" "$br"; then
                matched=1
                break
            fi
        done
        if [ "$matched" -eq 1 ]; then
            add_release_file "$file"
        fi
    done
fi

if [ "$found" -ne 1 ]; then
    echo "No APK/AAB files found to release for version $VERSION in $RELEASE_DIR" >&2
    echo "Specify target files directly or ensure build outputs match current branch/ABIs." >&2
    exit 1
fi

echo "Selected files to release:"
while IFS= read -r f; do
    echo "  - $(basename "$f")"
done < "$files_list"

remote_url=$(git_repo remote get-url origin)
repo=$(printf '%s' "$remote_url" | sed -E 's#^https://([^@]+@)?github.com/##; s#^git@github.com:##; s#\.git$##')
head_commit=$(git_repo rev-parse HEAD)

sha_file="$RELEASE_DIR/$VERSION-SHA256SUMS.txt"
sha_name="$(basename "$sha_file")"

# Download existing checksum file from GitHub release if not present locally
if [ ! -f "$sha_file" ] && command -v gh >/dev/null 2>&1; then
    gh release download "$TAG" --repo "$repo" --pattern "$sha_name" --dir "$RELEASE_DIR" >/dev/null 2>&1 || true
fi

# Calculate checksums for files being released in this run
tmp_new_sha=$(mktemp)
(
    cd "$RELEASE_DIR"
    while IFS= read -r f; do
        bname="$(basename "$f")"
        [ "$bname" != "$sha_name" ] || continue
        sha256sum "$bname" >> "$tmp_new_sha"
    done < "$files_list"
)

# Merge: keep existing checksums of untouched files, update/add current release files
if [ -f "$sha_file" ] && [ -s "$sha_file" ]; then
    tmp_merged=$(mktemp)
    while IFS= read -r line || [ -n "$line" ]; do
        fname=$(printf '%s\n' "$line" | awk '{print $2}')
        [ -n "$fname" ] || continue
        if grep -Fq "  $fname" "$tmp_new_sha" 2>/dev/null; then
            continue
        fi
        printf '%s\n' "$line" >> "$tmp_merged"
    done < "$sha_file"
    cat "$tmp_new_sha" >> "$tmp_merged"
    sort -k 2 -u "$tmp_merged" > "$sha_file"
    rm -f "$tmp_merged"
else
    sort -k 2 -u "$tmp_new_sha" > "$sha_file"
fi
rm -f "$tmp_new_sha"

printf '%s\n' "$sha_file" >> "$files_list"

git_repo fetch origin "refs/tags/$TAG:refs/tags/$TAG" >/dev/null 2>&1 || true
if git_repo rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    tag_commit=$(git_repo rev-list -n 1 "$TAG")
    if [ "$tag_commit" != "$head_commit" ]; then
        if [ "$MOVE_TAG" = "1" ]; then
            git_repo tag -f "$TAG" "$head_commit"
        else
            echo "Tag $TAG already exists at $tag_commit. Set MOVE_TAG=1 to move it to $head_commit." >&2
            exit 1
        fi
    fi
else
    git_repo tag "$TAG" "$head_commit"
fi

if [ "${SKIP_GIT_PUSH:-0}" != "1" ]; then
    if [ "$MOVE_TAG" = "1" ]; then
        git_repo push --force origin "refs/tags/$TAG"
    else
        git_repo push origin "refs/tags/$TAG"
    fi
fi

if gh release view "$TAG" --repo "$repo" >/dev/null 2>&1; then
    gh release edit "$TAG" --repo "$repo" --title "Helium Android $VERSION"
    if [ "${CLEAN_STALE_ASSETS:-0}" = "1" ]; then
        for existing_asset in $(gh release view "$TAG" --repo "$repo" --json assets --jq '.assets[].name' 2>/dev/null || true); do
            case "$existing_asset" in
                *"$VERSION"*)
                    ;;
                *)
                    gh release delete-asset "$TAG" "$existing_asset" --repo "$repo" --yes >/dev/null 2>&1 || true
                    ;;
            esac
        done
    fi
else
    gh release create "$TAG" \
        --repo "$repo" \
        --title "Helium Android $VERSION" \
        --notes "Helium Android build based on Vanadium $VERSION."
fi

while IFS= read -r file; do
    gh release upload "$TAG" "$file" --repo "$repo" --clobber
done < "$files_list"

echo "Published release $TAG to $repo"
