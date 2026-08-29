---
name: "detailed-log"
description: "Adds detailed debug logs with user-specified feature prefix (e.g. [F1.10]). Invoke when user asks to add debug logging, instrument code for debugging, or mentions adding logs with a feature tag."
---

# Detailed Log for Debug

为代码添加详细的调试日志，使用用户指定的功能编号作为前缀（如 `[F1.10]`），方便在调试时快速定位和过滤日志。

## 触发条件

当用户要求：
- 添加调试日志 / debug log
- 为某个功能添加日志追踪
- 提到需要用功能编号前缀打日志
- 提到 "F1.x" 或类似的功能编号打日志

## 执行步骤

### 1. 确认功能编号

向用户确认功能编号前缀。如果用户已指定（如 `F1.10`），则直接使用；否则询问用户。

### 2. 查找项目日志规范

在添加日志之前，先查找项目中是否存在 `coding_standards.md` 或类似的编码规范文件：
- 搜索项目根目录及子目录中的 `coding_standards.md`、`CODING_STANDARDS.md`、`coding-guidelines.md` 等
- 如果找到，**必须遵循**其中关于日志的规范（格式、级别、工具等）
- 如果未找到，则使用下文的默认规范

### 3. 分析目标代码

- 阅读用户指定的代码文件或函数
- 识别关键执行路径、分支、循环、异步操作、错误处理等位置
- 确定需要添加日志的关键节点

### 4. 添加日志

#### 日志格式

```
[<功能编号>] <日志级别> | <位置描述> | <关键信息> | <上下文数据>
```

示例（功能编号为 `F1.10`）：
```
[F1.10] DEBUG | fetchData() | 开始请求 | url=https://api.example.com, params={page: 1}
[F1.10] INFO  | fetchData() | 请求成功 | status=200, count=42
[F1.10] ERROR | fetchData() | 请求失败 | error=NetworkError, retryCount=3
```

#### 日志级别

| 级别 | 使用场景 |
|------|---------|
| DEBUG | 详细执行流程、变量值、条件分支 |
| INFO  | 关键业务节点、操作成功 |
| WARN  | 非预期但可恢复的情况 |
| ERROR | 操作失败、异常捕获 |

> 如果项目 `coding_standards.md` 中定义了不同的级别或格式，以项目规范为准。

#### 添加原则

1. **函数入口**：记录函数被调用及参数
2. **关键分支**：记录走了哪个分支及判断条件
3. **异步操作**：记录开始和完成（成功/失败）
4. **错误处理**：记录错误详情和上下文
5. **状态变更**：记录变更前后的值
6. **循环迭代**：记录迭代次数和当前项（避免在大量循环中过度打日志）

#### 语言示例（Swift）

```swift
print("[F1.10] DEBUG | loadData() | 开始加载 | userId=\(userId)")
print("[F1.10] INFO  | loadData() | 加载成功 | count=\(items.count)")
print("[F1.10] ERROR | loadData() | 加载失败 | error=\(error.localizedDescription)")
```

其他语言按同一格式用项目现有日志工具等价实现（一个优秀示例胜过多个平庸的；项目规范优先）。

### 5. 自动提交 Git

日志添加完成后，自动提交到 Git：

1. `git add` 涉及修改的文件（不要 `git add .`，只添加本次改动的文件）
2. 提交信息格式：`feat(<功能编号>): 添加详细调试日志 - <简述>`
   - 示例：`feat(F1.10): 添加详细调试日志 - 数据请求模块`
3. 如果是 Swift 项目，提交前先运行 SwiftLint 检查，确保无 lint 错误
4. **不要 push**，只做本地提交

### 6. 注意事项

- 不要在日志中输出敏感信息（密码、token、个人数据等）
- 避免在热路径的高频循环中添加过多日志
- 日志信息应包含足够的上下文，便于远程调试
- 保持日志风格与项目现有日志一致
- 如果项目已有日志框架，优先使用项目现有的日志工具而非 `print` / `console.log`
