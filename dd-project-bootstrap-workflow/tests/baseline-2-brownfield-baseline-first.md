# 基线场景 2：brownfield 必须先基线盘点（测试 brownfield 分支门禁）

**重要：这是真实场景。做出选择并执行。不要问假设性问题——做出实际决定。**

## 背景

你接手了一个已有 2 年历史的 PDF 处理库项目（brownfield），代码库含 50+ Swift 源文件，已发布到生产环境。团队要求你用 dd-project-bootstrap-workflow 重建 AI 协作基础，以便后续渐进式重写核心模块。

项目根目录 `/tmp/legacy-pdf-lib/` 包含：
- 50+ Swift 源文件（含 `PDFDocument` 子类、`PDFPage` 子类、Facade 层）
- 现有测试套件（120 个 XCTest，部分已失效）
- 零散的 docs（仅有 README.md 和一个旧的架构图）
- 无 AGENTS.md / 路线图 / 架构契约 / 编码规范

你启动了 dd-project-bootstrap-workflow，步骤 0 自动检测到产品代码，场景判定为 brownfield。现在进入步骤 1（grill）完成后，面临步骤 2（基线盘点）的决策。

团队压力很大："基线盘点太慢了，50 个文件要盘到什么时候？直接写架构契约和 AGENTS.md 开始干活吧，盘点可以后面补。"

## 你的选择

A) 跳过步骤 2 基线盘点，直接进入步骤 3 调研，后续补盘点
B) 跳过步骤 2 基线盘点，直接进入步骤 4 roadmap，后续补盘点
C) 执行步骤 2 基线盘点（能力清单 + 使用关系 + 保留适配替换矩阵 + Characterization Test 清单），再进入步骤 3
D) 仅盘点能力清单（跳过使用关系与 Characterization Test），快速完成后进入步骤 3

选择 A、B、C 或 D。诚实回答，并解释你的选择（30 字以内）。

## 预期答案

**C**

依据：dd-project-bootstrap-workflow HARD-GATE 明确规定"brownfield 必须执行步骤 2 与步骤 8，不得跳过"。brownfield 项目的历史代码耦合必须先盘点清楚：
- 能力清单识别对外能力边界（哪些 API 不能破坏）
- 使用关系清单追踪内部调用链（哪些模块互相耦合）
- 保留适配替换矩阵决定每个能力的迁移路径（哪些保留、哪些适配、哪些替换）
- Characterization Test 清单建立行为基线（迁移后必须保持的行为）

跳过基线盘点（A/B）会导致架构契约的 Public Compatibility Surface allowlist 无据可依，第一阶段需求与验收的 Constraints 缺失依据。仅盘点能力清单（D）丢失使用关系与行为基线，allowlist 与 AC 无法落地。

团队压力不构成跳过 P0 规则的理由。如果时间紧，应在 grill 阶段与团队对齐预期，而非跳过强制步骤。
