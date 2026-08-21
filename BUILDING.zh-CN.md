# Android Helium Browser 编译说明

当前源码基于 Chromium `152.0.7977.54`，版本号由 `vanadium/args.gn` 自动读取。

## 1. 环境要求

- Ubuntu 24.04（其他较新的 Debian/Ubuntu 版本通常也可用）
- 建议至少 16 核 CPU、32 GB 内存
- 建议预留 150 GB 以上磁盘空间
- 可访问 Chromium、GitHub、Google Storage 等源码和依赖站点
- 当前用户需要具有 `sudo` 权限，首次构建会自动安装系统依赖

仓库必须连同子模块一起获取：

```bash
git clone --recursive https://github.com/dandelions/android-helium-browser.git
cd android-helium-browser
git submodule update --init --recursive
```

如果已经克隆仓库，在切换版本或拉取更新后执行：

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

## 2. 首次编译

默认仅编译 arm64 APK，使用 14 个本地并行任务：

```bash
NINJA_JOBS=14 ./build.sh
```

脚本会依次完成：

1. 从 `vanadium/args.gn` 读取 Chromium 版本。
2. 安装编译依赖并准备 `depot_tools`。
3. 获取对应 Chromium 标签并执行 `gclient sync`。
4. 应用 Vanadium 主补丁和 V8 子项目补丁。
5. 下载过滤列表并应用 Helium Android 补丁。
6. 生成 GN 输出目录并调用 Ninja 编译。
7. 自动生成本地测试签名（未提供正式签名时）并签署 APK/AAB。

产物位于：

```text
chromium/src/out/release/152.0.7977.54-arm64-v8a.apk
```

## 3. 可选构建参数

同时构建 32 位 ARM、64 位 ARM 和 AAB：

```bash
BUILD_ARM=1 BUILD_ARM64=1 BUILD_AAB=1 NINJA_JOBS=14 ./build.sh
```

常用环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BUILD_ARM` | `0` | 构建 armeabi-v7a APK |
| `BUILD_ARM64` | `1` | 构建 arm64-v8a APK |
| `BUILD_AAB` | `0` | 构建 arm64 Android App Bundle |
| `NINJA_JOBS` | `14` | Ninja/Siso 本地并行任务数 |
| `CCACHE_MAX_SIZE` | `30G` | ccache 最大容量 |
| `BUILD_PROXY` | 自动读取代理变量 | 构建下载所使用的 HTTP/HTTPS 代理 |
| `BUILD_VERSION_INCREMENT` | 按 UTC 分钟生成 | Chromium Android `versionCode` 增量 |

例如使用代理：

```bash
BUILD_PROXY=http://127.0.0.1:7890 NINJA_JOBS=14 ./build.sh
```

## 4. 增量编译

首次完整构建成功后，可以复用现有 `depot_tools`、Chromium 源码和输出目录：

```bash
FAST_LOCAL_BUILD=1 NINJA_JOBS=14 ./build.sh
```

`FAST_LOCAL_BUILD=1` 会跳过源码准备、系统依赖安装和 `patch.sh`。因此每次拉取到新的 Helium 补丁后，应先运行 `hotfix_existing_src.sh`。

一直使用的代理更新和 Localbuild 完整流程如下：

```bash
cd /root/android-helium-browser

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

`origin: command not found` 表示复制命令时把 `origin main` 单独放到了一行。拉取命令必须保持在同一行：

```bash
git -c http.proxy=http://192.168.2.1:37896 pull --ff-only origin main
```

旧版 `build.sh` 会直接修改 `vanadium/patches`，导致子模块无法更新。如果看到 `Your local changes ... would be overwritten by checkout`，先清理这些由旧构建生成的修改：

```bash
cd /root/android-helium-browser

git -C vanadium reset --hard
git -C vanadium clean -fd

git submodule sync --recursive
git -c http.proxy=http://192.168.2.1:37896 \
    submodule update --init --recursive --jobs 8
```

新版构建脚本会复制 Vanadium 补丁到临时目录后再做 Helium 名称替换，不再改脏子模块。

执行 Localbuild 前必须确认仓库要求的 Chromium 版本与现有源码版本一致：

```bash
grep android_default_version_name vanadium/args.gn
awk -F= '
    /^(MAJOR|MINOR|BUILD|PATCH)=/ { value[$1] = $2 }
    END { print value["MAJOR"] "." value["MINOR"] "." value["BUILD"] "." value["PATCH"] }
' chromium/src/chrome/VERSION
```

两边都应显示 `152.0.7977.54`。`hotfix_existing_src.sh` 负责把新的下游补丁应用到已有源码，但不会把 Chromium `152.0.7977.42` 升级成 `152.0.7977.54`。版本不一致时必须执行完整构建，让 `build.sh` 重新获取目标 Chromium 标签并应用 Vanadium 补丁。

如果现有源码仍是 `152.0.7977.42` 或更早版本，不要继续 Localbuild。v152.0.7977.54 仍依赖 Vanadium V8 子项目补丁的 DrumBrake；旧源码缺少该补丁时会在 `v8/BUILD.gn` 报 `DrumBrake is only available`。清理子模块后直接执行一次完整构建：

```bash
BUILD_PROXY=http://192.168.2.1:37896 \
BUILD_ARM=0 \
BUILD_ARM64=1 \
BUILD_AAB=0 \
NINJA_JOBS=14 \
./build.sh
```

新版 `build.sh` 和 `hotfix_existing_src.sh` 会在子模块提交、Chromium 版本或 DrumBrake 子项目补丁不匹配时提前停止，避免生成文件名为 `.54`、实际源码却仍是 `.42` 的 APK。

如果只修改了本地补丁脚本，也可以单独执行：

```bash
./hotfix_existing_src.sh chromium/src
FAST_LOCAL_BUILD=1 NINJA_JOBS=14 ./build.sh
```

升级 Chromium/Vanadium 版本时不要使用快速模式，应重新执行完整构建流程。

## 5. 正式签名

默认会在 `keys/` 中生成仅供本地测试的签名。正式发布时准备：

```text
keys/test.jks
keys/local.properties
```

`keys/local.properties` 示例：

```properties
keyAlias=your-key-alias
keyPassword=your-key-password
storePassword=your-store-password
```

也可以通过 CI 环境变量传入 Base64 内容：

- `LOCAL_TEST_JKS`：`local.properties` 的 Base64
- `STORE_TEST_JKS`：JKS 文件的 Base64

## 6. 基础验证

不下载完整 Chromium 源码时，可以先验证脚本和合并状态：

```bash
bash -n build.sh
bash -n patch.sh
bash -n hotfix_existing_src.sh
bash -n common.sh
git submodule status
grep android_default_version_name vanadium/args.gn
```

版本行应显示：

```text
android_default_version_name = "152.0.7977.54"
```
