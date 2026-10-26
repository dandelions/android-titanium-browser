export SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")

replace() {
    export org=$2 new=$3
    find $1 -type f -exec sed -i 's@'$org'@'$new'@g' {} \;
}

generate_test_keys() {
    rm -f "$SCRIPT_DIR/keys/local.properties" "$SCRIPT_DIR/keys/test.jks"

    cat > "$SCRIPT_DIR/keys/local.properties" <<'EOF'
keyAlias=helium-ci
keyPassword=android
storePassword=android
storeType=PKCS12
EOF

    keytool -genkeypair \
        -storetype PKCS12 \
        -keystore "$SCRIPT_DIR/keys/test.jks" \
        -storepass android \
        -keypass android \
        -alias helium-ci \
        -keyalg RSA \
        -keysize 2048 \
        -validity 10000 \
        -dname "CN=Helium CI,O=Helium,C=US"
}

validate_keys() {
    source "$SCRIPT_DIR/keys/local.properties"
    if [ -n "${storeType:-}" ]; then
        keytool -list -storetype "$storeType" -keystore "$SCRIPT_DIR/keys/test.jks" -storepass "$storePassword" -alias "$keyAlias" >/dev/null
    else
        keytool -list -keystore "$SCRIPT_DIR/keys/test.jks" -storepass "$storePassword" -alias "$keyAlias" >/dev/null
    fi
}

set_keys() {
    mkdir -p "$SCRIPT_DIR/keys"
    if [ -n "${LOCAL_TEST_JKS:-}" ] && [ -n "${STORE_TEST_JKS:-}" ]; then
        printf '%s' "$LOCAL_TEST_JKS" | base64 -d > "$SCRIPT_DIR/keys/local.properties"
        printf '%s' "$STORE_TEST_JKS" | base64 -d > "$SCRIPT_DIR/keys/test.jks"
    elif [ -s "$SCRIPT_DIR/keys/local.properties" ] && [ -s "$SCRIPT_DIR/keys/test.jks" ]; then
        echo "Reusing existing local signing key from $SCRIPT_DIR/keys."
    else
        echo "Signing config was not provided; generating a local test signing key."
        generate_test_keys
    fi
    validate_keys
    unset LOCAL_TEST_JKS
    unset STORE_TEST_JKS
}

sign_apk() {
    if [ -z "${ANDROID_HOME:-}" ] && [ -d "$SCRIPT_DIR/chromium/src/third_party/android_sdk/public" ]; then
        export ANDROID_HOME="$SCRIPT_DIR/chromium/src/third_party/android_sdk/public"
    fi
    if [ -d "$SCRIPT_DIR/chromium/src/third_party/jdk/current/bin" ]; then
        export PATH="$SCRIPT_DIR/chromium/src/third_party/jdk/current/bin:$PATH"
    fi
    export apksigner=$(find "$ANDROID_HOME/build-tools" -name apksigner | sort | tail -n 1)
    export zipalign=$(find "$ANDROID_HOME/build-tools" -name zipalign | sort | tail -n 1)
    source "$SCRIPT_DIR/keys/local.properties"
    local input_apk="$1"
    local output_apk="$2"
    local to_sign="$input_apk"
    local tmp_aligned=""
    local tmp_source=""

    local current_git_branch=""
    current_git_branch="$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

    local is_old_android=0
    if [ "${DISABLE_V3_SIGNING:-0}" = "1" ] || [ "${CAR_COMPAT:-0}" = "1" ] || [ "$current_git_branch" = "old-android" ] || [[ "$input_apk" == *"old-android"* ]] || [[ "$output_apk" == *"old-android"* ]]; then
        is_old_android=1
    fi

    local to_prepare="$input_apk"
    local tmp_prepared=""
    if [ "$is_old_android" = "1" ] && [ -f "$SCRIPT_DIR/patch_apk_manifest.py" ]; then
        tmp_prepared="$(mktemp --suffix=-manifest-patched.apk)"
        cp "$input_apk" "$tmp_prepared"
        python3 "$SCRIPT_DIR/patch_apk_manifest.py" "$tmp_prepared" 24 34 34 || true
        to_prepare="$tmp_prepared"
    fi

    if [ -n "$zipalign" ] && [ -x "$zipalign" ]; then
        tmp_aligned="$(mktemp --suffix=-aligned.apk)"
        "$zipalign" -p -f 4 "$to_prepare" "$tmp_aligned"
        to_sign="$tmp_aligned"
    elif [ "$(realpath "$to_prepare" 2>/dev/null || echo "$to_prepare")" = "$(realpath "$output_apk" 2>/dev/null || echo "$output_apk")" ]; then
        tmp_source="$(mktemp --suffix=-source.apk)"
        cp "$to_prepare" "$tmp_source"
        to_sign="$tmp_source"
    else
        to_sign="$to_prepare"
    fi

    local v3_signing="true"
    local extra_sign_args=()
    if [ "$is_old_android" = "1" ]; then
        v3_signing="false"
        extra_sign_args+=(--min-sdk-version 21)
    elif [ "${ENABLE_V2_SIGNING:-1}" = "1" ]; then
        extra_sign_args+=(--min-sdk-version 21)
    fi

    if [ -n "${storeType:-}" ]; then
        "$apksigner" sign --verbose \
            --ks "$SCRIPT_DIR/keys/test.jks" \
            --ks-type "$storeType" \
            --ks-pass "pass:$storePassword" \
            --key-pass "pass:$keyPassword" \
            --ks-key-alias "$keyAlias" \
            --v1-signing-enabled true \
            --v2-signing-enabled true \
            --v3-signing-enabled "$v3_signing" \
            --v4-signing-enabled false \
            "${extra_sign_args[@]}" \
            --out "$output_apk" \
            "$to_sign" || { rm -f "$tmp_aligned" "$tmp_source" "$tmp_prepared"; exit 1; }
    else
        "$apksigner" sign --verbose \
            --ks "$SCRIPT_DIR/keys/test.jks" \
            --ks-pass "pass:$storePassword" \
            --key-pass "pass:$keyPassword" \
            --ks-key-alias "$keyAlias" \
            --v1-signing-enabled true \
            --v2-signing-enabled true \
            --v3-signing-enabled "$v3_signing" \
            --v4-signing-enabled false \
            "${extra_sign_args[@]}" \
            --out "$output_apk" \
            "$to_sign" || { rm -f "$tmp_aligned" "$tmp_source" "$tmp_prepared"; exit 1; }
    fi
    if [ -n "$tmp_aligned" ]; then
        rm -f "$tmp_aligned"
    fi
    if [ -n "$tmp_source" ]; then
        rm -f "$tmp_source"
    fi
    if [ -n "$tmp_prepared" ]; then
        rm -f "$tmp_prepared"
    fi
    echo "[sign_apk] Signature schemes for $(basename "$output_apk"):"
    "$apksigner" verify --verbose --min-sdk-version 21 "$output_apk" 2>&1 | grep -E "Verifies|Verified using" || true
}

sign_aab() {
    source "$SCRIPT_DIR/keys/local.properties"
    if [ -n "${storeType:-}" ]; then
        jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
            -storetype "$storeType" \
            -keystore "$SCRIPT_DIR/keys/test.jks" \
            -storepass "$storePassword" \
            -keypass "$keyPassword" \
            -signedjar "$2" "$1" "$keyAlias" || exit 1
    else
        jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
            -keystore "$SCRIPT_DIR/keys/test.jks" \
            -storepass "$storePassword" \
            -keypass "$keyPassword" \
            -signedjar "$2" "$1" "$keyAlias" || exit 1
    fi
}

version_lt() {
  [ "$1" != "$2" ] && [ "$(printf '%s\n%s\n' "$1" "$2" | sort -V | head -n1)" = "$1" ]
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ "$#" -ge 1 ]; then
        set_keys
        for target_apk in "$@"; do
            if [ -f "$target_apk" ]; then
                echo "Signing $target_apk..."
                sign_apk "$target_apk" "$target_apk"
            else
                echo "Warning: target file not found: $target_apk" >&2
            fi
        done
    else
        echo "Usage: $0 <apk_file> [apk_file2 ...]"
        echo "Signs the specified APK(s) using repository signing configuration."
    fi
fi
