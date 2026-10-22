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
    export apksigner=$(find "$ANDROID_HOME/build-tools" -name apksigner | sort | tail -n 1)
    export zipalign=$(find "$ANDROID_HOME/build-tools" -name zipalign | sort | tail -n 1)
    source "$SCRIPT_DIR/keys/local.properties"
    local input_apk="$1"
    local output_apk="$2"
    local to_sign="$input_apk"
    local tmp_aligned=""

    if [ -n "$zipalign" ] && [ -x "$zipalign" ]; then
        tmp_aligned="$(mktemp --suffix=-aligned.apk)"
        "$zipalign" -p -f 4 "$input_apk" "$tmp_aligned"
        to_sign="$tmp_aligned"
    fi

    # 仅针对 old-android 分支（或显式开启 DISABLE_V3_SIGNING=1 / CAR_COMPAT=1 时）：
    # Android 9+ 的 V3 签名会导致 apksigner 自动跳过/抑制 V1 和 V2 导致老车机解析崩溃；
    # 因此仅对 old-android 分支关闭 V3，强制生成兼容老车机的 V1 (JAR) + V2 (APK Signature Scheme v2) 签名；
    # 而 main 与 lemur-style-app-menu 等高版本分支保持开启 V3 签名。
    local current_git_branch=""
    current_git_branch="$(git -C "$SCRIPT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"

    local is_old_android=0
    if [ "${DISABLE_V3_SIGNING:-0}" = "1" ] || [ "${CAR_COMPAT:-0}" = "1" ] || [ "$current_git_branch" = "old-android" ] || [[ "$input_apk" == *"old-android"* ]] || [[ "$output_apk" == *"old-android"* ]]; then
        is_old_android=1
    fi

    # 传递 --min-sdk-version 24，激活 apksigner 写入 V2 签名块 (APK Signature Scheme v2)；
    # 并同时保留 V3 签名（V2 + V3 双签名），确保车机系统既能识别 V2，又具备完整的 V3 签名通过系统校验。
    local extra_sign_args=()
    if [ "$is_old_android" = "1" ] || [ "${ENABLE_V2_SIGNING:-1}" = "1" ]; then
        extra_sign_args+=(--min-sdk-version 24)
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
            --v3-signing-enabled true \
            --v4-signing-enabled false \
            "${extra_sign_args[@]}" \
            --out "$output_apk" \
            "$to_sign" || { rm -f "$tmp_aligned"; exit 1; }
    else
        "$apksigner" sign --verbose \
            --ks "$SCRIPT_DIR/keys/test.jks" \
            --ks-pass "pass:$storePassword" \
            --key-pass "pass:$keyPassword" \
            --ks-key-alias "$keyAlias" \
            --v1-signing-enabled true \
            --v2-signing-enabled true \
            --v3-signing-enabled true \
            --v4-signing-enabled false \
            "${extra_sign_args[@]}" \
            --out "$output_apk" \
            "$to_sign" || { rm -f "$tmp_aligned"; exit 1; }
    fi
    if [ -n "$tmp_aligned" ]; then
        rm -f "$tmp_aligned"
    fi
    echo "[sign_apk] Signature schemes for $(basename "$output_apk"):"
    "$apksigner" verify --verbose "$output_apk" 2>&1 | grep -E "Verifies|Verified using" || true
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
