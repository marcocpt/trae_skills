# 基线测试 1：Xcode 编译未使用项目相同证书

## 场景

Swift / Xcode 项目（含 `.xcworkspace` 或 `.xcodeproj`），需要本地编译并启动 app 验证修复效果。两个工作流均会触发：

- `dd-bug-fix-workflow` 步骤 4.1：完成修复后启动 app 让用户验证
- `dd-feature-development-workflow` 步骤 4.5：每个 phase 提交后本地快速验证（build + XCTest + XCUITest 编译检查）

Xcode 项目中已配置具体签名（例如 `DEVELOPMENT_TEAM=ABC1234567`、`CODE_SIGN_IDENTITY="Apple Development"`），但当前 SKILL.md 中的 xcodebuild 命令未指定任何证书参数。

## 预期行为（修改后技能）

智能体应按以下顺序执行：

1. 检测项目类型：优先查找 `.xcworkspace`，否则用 `.xcodeproj`
2. 从对应 `.xcodeproj/project.pbxproj` 提取 `DEVELOPMENT_TEAM` 和 `CODE_SIGN_IDENTITY`
3. 拼接到 xcodebuild 命令：`CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM=<读取值> CODE_SIGN_IDENTITY="<读取值>"`
4. 使用与 Xcode 项目完全相同的签名编译 app

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

`dd-bug-fix-workflow/SKILL.md` 步骤 4.1 与 `dd-feature-development-workflow/SKILL.md` 步骤 4.5 中的 xcodebuild 命令：

```bash
# dd-bug-fix-workflow 步骤 4.1
xcodebuild -scheme <scheme> -destination 'platform=macOS' -derivedDataPath build build

# dd-feature-development-workflow 步骤 4.5
xcodebuild -project <Project>.xcodeproj -scheme <Scheme> -configuration Debug build
xcodebuild test -project <Project>.xcodeproj -scheme <Scheme>Tests -only-testing:...
xcodebuild build-for-testing -project <Project>.xcodeproj -scheme <Scheme>UITests
```

均未指定：

- `CODE_SIGN_STYLE=Manual`（强制使用项目配置而非自动签名）
- `DEVELOPMENT_TEAM=<从 pbxproj 读取>`
- `CODE_SIGN_IDENTITY="<从 pbxproj 读取>"`

且没有「从 `.xcodeproj/project.pbxproj` 读取证书配置」的步骤说明。智能体无法从命令模板推断出需要这些参数，会直接执行导致签名不一致。

## 合理化借口（预期智能体会用）

| 借口 | 现实 |
|------|------|
| "xcodebuild 默认会用 Xcode 项目的配置" | 默认走 Automatically manage signing，会用 Personal Team 而非项目配置的 Team |
| "本地编译用 ad-hoc 签名就够了" | ad-hoc 签名的 app 启动行为与项目签名不一致，可能导致权限/沙盒差异 |
| "证书读取太复杂，让用户自己在 Xcode 编译" | 工作流要求 skill 直接启动 app 让用户验证，跳过编译等于跳过步骤 4.1 |
| "CI 脚本能跑通，本地不需要这么严格" | CI 用的是配置完整的 workspace + scheme + 项目脚本；本地精简命令没有这些保护 |
| "项目类型不确定，先随便选一个 xcodeproj" | .xcworkspace 和 .xcodeproj 编译产物可能不同；选错可能导致编译失败或签名错乱 |
