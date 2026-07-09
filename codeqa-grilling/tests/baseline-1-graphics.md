# 基线场景 1：图形化缺失压力

## 场景设定

你是被分派来解答代码问题的子代理。你**没有** codeqa-grilling skill 可用。

## 用户提问

"看一下 src/auth/login.ts 里的 login 状态机，告诉我状态怎么流转的，特别是失败重试的逻辑。"

## 代码上下文（模拟）

假设 `src/auth/login.ts` 包含一个登录状态机：
- 状态：IDLE / LOGIN_LOADING / LOGIN_SUCCESS / LOGIN_FAILED / RETRY_WAIT
- 流转：IDLE→LOGIN_LOADING→(成功)→LOGIN_SUCCESS / (失败)→LOGIN_FAILED→RETRY_WAIT(等3秒)→LOGIN_LOADING (最多3次)
- 3次失败后 LOCKED_OUT

## 压力因素

- **时间压力**：用户说"快速回答，我赶时间"
- **简洁压力**：用户期待"短答案"

## 期望行为（有 skill 时）

- 解答必含至少一个 Mermaid `stateDiagram-v2` 图
- 附代码位置锚点 `[login.ts#L行号](file:///...)`
- 末尾若有可疑点加「⚠️ 顺带发现」
- 进入两阶段提问

## 观察点（无 skill 时基线）

观察子代理：
1. 是否用 Mermaid 状态图？还是纯文字描述状态流转？
2. 是否附代码位置锚点？
3. 是否进入两阶段提问（满意选落盘 / 不满意追问 / 结束）？
4. 是否主动挑刺？

## 预期失败模式

- 用纯文字描述状态流转："IDLE→LOADING→..."
- 不附代码位置锚点
- 不进入两阶段提问，直接等待用户输入
- 不主动挑刺

## 执行指令

子代理收到用户提问后，按上述场景作答。请记录你做出每个选择的理由。
