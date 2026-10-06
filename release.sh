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
MOVE_TAG="${MOVE_TAG:-0}"

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
for file in "$RELEASE_DIR/$VERSION"-*.apk "$RELEASE_DIR/$VERSION"-*.aab; do
    if [ -f "$file" ]; then
        printf '%s\n' "$file" >> "$files_list"
        found=1
    fi
done

if [ "$found" -ne 1 ]; then
    echo "No APK/AAB files found for version $VERSION in $RELEASE_DIR" >&2
    exit 1
fi

sha_file="$RELEASE_DIR/$VERSION-SHA256SUMS.txt"
(
    cd "$RELEASE_DIR"
    : > "$sha_file"
    while IFS= read -r file; do
        sha256sum "$(basename "$file")" >> "$sha_file"
    done < "$files_list"
)
printf '%s\n' "$sha_file" >> "$files_list"

remote_url=$(git_repo remote get-url origin)
repo=$(printf '%s' "$remote_url" | sed -E 's#^https://([^@]+@)?github.com/##; s#^git@github.com:##; s#\.git$##')
head_commit=$(git_repo rev-parse HEAD)

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

if [ "$MOVE_TAG" = "1" ]; then
    git_repo push --force origin "refs/tags/$TAG"
else
    git_repo push origin "refs/tags/$TAG"
fi

if gh release view "$TAG" --repo "$repo" >/dev/null 2>&1; then
    gh release edit "$TAG" --repo "$repo" --title "Helium Android $VERSION"
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
