# Android Helium Browser 编译说明

当前源码基于 Chromium `157.0.8103.38`，版本号由 `vanadium/args.gn` 自动读取。

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
chromium/src/out/release/157.0.8103.38-arm64-v8a.apk
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
BUILD_ARM=1 \
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

两边都应显示 `157.0.8103.38`。`hotfix_existing_src.sh` 负责把新的下游补丁应用到已有源码，但不会把旧版 Chromium 升级成 `157.0.8103.38`。版本不一致时必须执行完整构建，让 `build.sh` 重新获取目标 Chromium 标签并应用 Vanadium 补丁。

如果现有源码仍是旧版本，不要继续 Localbuild。清理子模块后直接执行一次完整构建：

```bash
BUILD_PROXY=http://192.168.2.1:37896 \
BUILD_ARM=0 \
BUILD_ARM64=1 \
BUILD_AAB=0 \
NINJA_JOBS=14 \
./build.sh
```

新版 `build.sh` 和 `hotfix_existing_src.sh` 会在子模块提交、Chromium 版本或 DrumBrake 子项目补丁不匹配时提前停止，避免生成版本号不符的 APK。

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

## 7. 启动闪退日志

应用会在 Chromium 初始化前启动日志采集，将启动上下文、Java 异常、native 崩溃和本应用告警写入应用专属外部目录：

```text
/Android/data/app.vanadium.browser/files/logs/helium_boot.log
/Android/data/app.vanadium.browser/files/logs/startup-logcat.txt
/Android/data/app.vanadium.browser/files/logs/application-logcat.txt
/Android/data/app.vanadium.browser/files/logs/warning-error-logcat.txt
/Android/data/app.vanadium.browser/files/logs/crash_log.txt
/Android/data/app.vanadium.browser/files/logs/native-crash.txt
/Android/data/app.vanadium.browser/files/logs/logcat-error.txt
```

`helium_boot.log` 记录启动时间、进程号、进程名和时间过滤器状态。`startup-logcat.txt` 保存应用主进程启动前后的主日志、系统日志与 crash buffer；采集器会重连以应对 logd 断开，并脱离应用进程组，避免应用退出时一起被杀。`application-logcat.txt` 按应用 UID 采集 main、system 和 crash buffer，不设置日志级别过滤，并使用轮转限制文件大小。`warning-error-logcat.txt` 单独记录应用 UID 可读取的 `WARN`/`ERROR` 级日志。`crash_log.txt` 保存未捕获 Java 异常栈，`native-crash.txt` 只保存 tombstone 中命令行为 Helium 包名的 native 崩溃上下文，`logcat-error.txt` 保存采集错误。过滤掉的 `unexpected EOF` 只来自采集器 stderr，不会删除应用日志中的同名文本。

主日志、完整应用日志和告警日志各最多保留 3 个旧文件和 1 个当前文件，每个约 4 MiB。日志采集器只在浏览器主进程启动；渲染、GPU、扩展等子进程仍会写入 `helium_boot.log` 和 `crash_log.txt`，但它们的日志只出现在按 UID 采集的 `application-logcat.txt` 里。多个进程同时读取 logd 会触发大量 `unexpected EOF` 并互相截断 `native-crash.txt`，因此子进程不再启动采集器。`logcat-error.txt` 每次浏览器主进程启动时重建，不保留上一次运行的采集错误。Android 普通应用不能读取完整系统或其他应用日志；隔离 UID 的 Chromium 子进程日志也不一定可读。设备实际安装包名不同的情况下，目录中的包名也会相应变化。

完成完整构建或应用 `hotfix_existing_src.sh` 并增量构建后，复现闪退，再从上述目录取出日志文件。

日志目录按顺序探测，第一个真正可写的目录生效：`Android/data/<包名>/files/logs`、`Android/data/<包名>/files/helium-logs`、`Download/HeliumLogs`、应用内部私有目录 `helium-logs`。每次探测都会真实写入一个临时文件，因此不会出现"目录存在但写不进去、日志全部丢失"的情况。选中的目录会以 `Helium logs at <路径>` 写入 logcat，标签为 `ChromeApplicationImplHooks`；如果所有候选目录都不可写，会打印 `No writable Helium log directory, tried: ...`。车机把 `Android/data` 对文件管理器隐藏时，日志会出现在文件管理器可见的 `Download/HeliumLogs`。

排查子进程问题时，`application-logcat.txt` 中会出现 `Helium trace:` 前缀的跟踪行，依次为 `setupConnection`、`main thread has args`、`loading native library`、`native library loaded`、`child process ready`、`entering child main`。最后出现的那一行就是子进程卡住或退出前到达的位置；若子进程抛出 Java 异常，会额外记录 `Helium trace: child process init failed` 或 `Uncaught exception in child process` 及其堆栈。

进程因致命信号退出时（`SIGABRT`、`SIGSEGV`、`SIGBUS`、`SIGILL`、`SIGFPE`，例如 `F/libc: FORTIFY: fcntl(F_SETFD) passed non-FD_CLOEXEC flag` 这类 fortify 失败），日志里会出现 `HeliumNativeCrash` 标签：先打印信号号、`si_code`、出错地址和进程号，随后是 `#00 0x... libchrome.so+0x...` 形式的原生调用栈。处理器在打印后恢复原处理器并重新抛出信号，所以 tombstone 与重启行为不变。栈里的模块偏移可以直接用同一份构建产物里的 `libchrome.so` 反查函数名，用于定位崩溃点。

排查网页打不开时，先看渲染进程是否被 seccomp 杀掉：日志里出现 `HeliumSigSys: sandbox blocked syscall=226`（aarch64 上 226 是 `mprotect`）后紧跟 `onServiceDisconnected (crash or killed by oom)` 和 `primaryMainFrameRenderProcessGone() ... termination status: 6`，说明渲染进程在建立页面时被沙箱终止。渲染进程启动时还会打印 `Helium sandbox: renderer policy=1 jit_disabled=<true|false> js_flags=<...>`，用于确认实际生效的沙箱策略和 V8 的 jitless 状态。

排查扩展接管主页失效时，日志中会出现 `HeliumNtp` 标签的行。`resolver ntp=<URL> overrideEnabled=<true|false>` 来自 Java 侧的 `UrlConstantResolver`，表示新建标签页/主页按钮解析出的 URL 以及扩展覆盖开关是否打开；`HeliumNtp: pref list missing, enabled overrides=<数量>` 或 `HeliumNtp: pref list entries=<数量>` 来自 C++ 侧，表示 `extensions.chrome_url_overrides` 首选项是否已经写入。扩展已启用但仍显示原生主页时，`pref list missing` 说明覆盖列表没有写入首选项，此时会直接按已启用扩展的清单回退读取覆盖地址。

排查子进程或渲染进程问题时，可以在 `Android/data/<包名>/files/helium-switches.txt` 或 `Download/helium-switches.txt` 中按行写入 Chromium 命令行开关（每行一个，可带 `--` 前缀，`#` 开头为注释），浏览器进程启动时会追加到命令行，子进程继承同一套开关。两个位置都会被读取，`Download` 下的文件便于在 `Android/data` 不可见时使用。文件只在浏览器进程读取，删除或清空后重启即恢复默认行为；读取失败不会阻塞启动。生效的开关会以 `Applied diagnostic switches from <路径>: [...]` 写入 logcat。常用开关包括 `disable-seccomp-filter-sandbox`、`no-sandbox`、`single-process`。

设备有 root 权限时，可在复现前用电脑运行以下命令，单独保存完整设备日志。命令使用 UTC 起始时间过滤旧日志；运行期间复现扩展管理或网址打不开的问题，复现完成后按 `Ctrl+C` 停止采集：

```bash
mkdir -p logs
START_TIME="$(date -u '+%m-%d %H:%M:%S.%3N')"
adb exec-out su -c "logcat -b all -v threadtime -T '$START_TIME'" > logs/logcat-all.txt
```

`logs/logcat-all.txt` 包含 root 可读取的全部 logcat 缓冲区，不限应用 UID 或日志级别；文件会保留在运行命令的电脑当前目录下。

## 8. 基础验证

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
android_default_version_name = "157.0.8103.38"
```
