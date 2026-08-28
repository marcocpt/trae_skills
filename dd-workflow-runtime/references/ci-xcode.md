> 唯一职责：仅在 Xcode 项目需要**本地诊断**时读取的通用 adapter。不含任何项目名、固定 workspace/project/scheme 或固定 workflow 名。
>
> 它只做本地诊断，不替代必需远端 CI Gate（见 ci.md）。

# Xcode 本地诊断 adapter

用于需要本地编译 / 测试 / 启动 app 以理解失败或收集诊断的场景。它不拥有 CI 决策；CI 决策由 [test-location.md](test-location.md) 与 [ci.md](ci.md) 拥有。

## 0. 优先项目文档 / 项目脚本

若项目 `AGENTS.md`、`project_memory.md` 或项目脚本提供了 workspace/project、scheme、签名或本地命令，**必须**优先使用项目给出的命令与配置，不自行重新探测。

仅当项目未提供命令时，才使用下面的通用发现流程。

## 1. 通用发现（无项目命令时）

### 1.1 workspace / project

```bash
WORKSPACE=$(find . -maxdepth 2 -name "*.xcworkspace" -type d 2>/dev/null | head -1)
PROJECT=$(find . -maxdepth 2 -name "*.xcodeproj" -type d 2>/dev/null | head -1)
```

- 同时存在 `.xcworkspace` 与 `.xcodeproj` 时优先 `.xcworkspace`（CocoaPods/SPM 依赖要求）；
- 多 target 配置时**禁止**用 `head -1` 猜测；若无法唯一解析，ASK / BLOCKED，不自行选择。

### 1.2 scheme 与签名设置

用 `xcodebuild -list` 与 `-showBuildSettings` 发现 scheme 和签名，而不是硬编码：

```bash
xcodebuild -list                       # 列出 scheme 与 target
xcodebuild -showBuildSettings          # 读取签名、team、产物名等设置
```

- 禁止固定 app / scheme / workflow 名；
- 多个 scheme / target 时，依据当前 Phase 涉及的 target 精确选择；无法唯一判断时 ASK / BLOCKED。

## 2. 签名（本地编译必读）

**核心原则**：本地编译 Swift / Xcode 项目时，必须使用与 Xcode 项目配置完全相同的签名（`DEVELOPMENT_TEAM` + `CODE_SIGN_IDENTITY`），禁止走 "Automatically manage signing" 默认行为。

- 从 `-showBuildSettings` 或 pbxproj 读取 `DEVELOPMENT_TEAM` 与 `CODE_SIGN_IDENTITY`；
- 编译命令显式追加 `CODE_SIGN_STYLE=Manual`、`DEVELOPMENT_TEAM`、`CODE_SIGN_IDENTITY`；
- 多 build configuration（Debug/Release/不同 target）值可能不同；按当前 scheme 对应 target 精确提取，禁止 `head -1` 猜多 target 配置；无法唯一解析时 ASK / BLOCKED。

## 3. 产物与启动

探测真实产物名，不假设 AppName == scheme：

```bash
APP_PATH=$(find build/Build/Products/Debug -maxdepth 1 -name '*.app' -type d 2>/dev/null | head -1)
```

## 红线

- 以"项目已配置签名，命令行不必重复"为由跳过证书读取；
- 用 `head -1` 猜多 target 配置；
- 固定 app / scheme / workflow 名；
- 本地诊断通过即宣称远端 CI Gate 已关闭（那由 ci.md 的 exact-SHA 语义决定）；
- 本地测试替代必需远端 CI。
