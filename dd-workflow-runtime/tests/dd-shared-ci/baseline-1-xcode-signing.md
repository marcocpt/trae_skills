# 基线测试 1：Xcode 编译未使用项目相同证书

## 场景

Swift / Xcode 项目（含 `.xcworkspace` 或 `.xcodeproj`），需要本地编译并启动 app 验证修复效果。`dd-bug-fix-workflow` 与 `dd-feature-development-workflow` 均可能在本地诊断时触发。

Xcode 项目中已配置具体签名（例如 `DEVELOPMENT_TEAM=ABC1234567`、`CODE_SIGN_IDENTITY="Apple Development"`），但本地 xcodebuild 命令未指定任何证书参数。

## 预期行为（修改后技能）

智能体按 [ci-xcode.md](../../references/ci-xcode.md) 通用 adapter 执行：

1. 优先使用项目 `AGENTS.md` / 项目脚本给出的命令与签名配置；
2. 项目未给命令时，检测项目类型：优先 `.xcworkspace`，否则 `.xcodeproj`；
3. 从 `xcodebuild -showBuildSettings` 或对应 `.xcodeproj/project.pbxproj` 提取 `DEVELOPMENT_TEAM` 和 `CODE_SIGN_IDENTITY`；
4. 多 target / 多 build configuration 无法唯一解析时 ASK / BLOCKED，禁止 `head -1` 猜测；
5. 拼接到 xcodebuild 命令：`CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM=<读取值> CODE_SIGN_IDENTITY="<读取值>"`；
6. 使用与 Xcode 项目完全相同的签名编译 app。

## 当前基线行为（修改前预期失败）

1. ❌ 智能体直接套用 SKILL.md 中的命令模板：`xcodebuild -scheme <scheme> -destination 'platform=macOS' -derivedDataPath build build`
2. ❌ xcodebuild 走 "Automatically manage signing"，可能：
   - 选到 Personal Team（与项目配置的 Team 不一致）
   - 选到不同 `CODE_SIGN_IDENTITY`（如 "Apple Development" vs "Mac Developer"）
   - 触发 `provToolError`、`no provisioning profile`、`code signing is required` 等错误
3. ❌ 启动 app 时报错：`killed: 9`、`unable to boot`、权限被拒
4. ❌ 或编译成功但签名与 Xcode 中已安装的版本冲突，导致启动旧版本 / 闪退 / 沙盒异常
5. ❌ 用户被迫手动到 Xcode 中重新编译，工作流被打断

## 压力因素

- 项目同时存在 `.xcworkspace` 和 `.xcodeproj`，智能体不确定用哪个
- pbxproj 中 `DEVELOPMENT_TEAM` 和 `CODE_SIGN_IDENTITY` 出现在多个 build configuration（Debug/Release/不同 target），值可能不一致
- CI 脚本（`test-macos.sh`）走的是 `Macim.xcworkspace + MacimApp scheme` 的完整测试链路，能成功；但本地 skill 中的精简 build 命令没有这种 CI 环境配置，更容易触发签名问题
- 用户在桌面工作，期望本地 build 与 Xcode 中行为一致，不接受"换了证书"

## 根因

本地 xcodebuild 命令未指定签名参数，且没有「从项目/`-showBuildSettings` 读取证书配置」的统一 adapter。共享 CI 合同曾硬编码项目名与 scheme（如 `Macim.xcworkspace` / `MacimApp`），本地精简命令无法复用其签名保护，导致签名不一致。现由通用 `ci-xcode.md` adapter 统一处理，且不得固定 app/scheme 名。

修复需指定：

- `CODE_SIGN_STYLE=Manual`（强制使用项目配置而非自动签名）
- `DEVELOPMENT_TEAM=<从项目设置读取>`
- `CODE_SIGN_IDENTITY="<从项目设置读取>"`

## 合理化借口（预期智能体会用）

| 借口 | 现实 |
|------|------|
| "xcodebuild 默认会用 Xcode 项目的配置" | 默认走 Automatically manage signing，会用 Personal Team 而非项目配置的 Team |
| "本地编译用 ad-hoc 签名就够了" | ad-hoc 签名的 app 启动行为与项目签名不一致，可能导致权限/沙盒差异 |
| "证书读取太复杂，让用户自己在 Xcode 编译" | 工作流要求 skill 直接启动 app 让用户验证，跳过编译等于跳过步骤 4.1 |
| "CI 脚本能跑通，本地不需要这么严格" | CI 用的是配置完整的 workspace + scheme + 项目脚本；本地精简命令没有这些保护 |
| "项目类型不确定，先随便选一个 xcodeproj" | .xcworkspace 和 .xcodeproj 编译产物可能不同；选错可能导致编译失败或签名错乱 |
