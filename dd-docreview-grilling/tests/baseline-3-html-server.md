# 基线测试 3：HTML server 启动 + 完成后 ASK

## 场景

用户审核一份架构设计文档，文档描述了 7 个微服务的交互关系。

用户提问："这个微服务架构的整体调用关系是怎样的？"

同时，审核流程全部完成后（含批量修复），用户需要被询问下一步。

## 预期行为（修改后技能）

### HTML server 部分
1. 架构图 5+ 节点且关系复杂 → AI **直接启动 HTML server**（不询问用户）
2. 调 `brainstorming/scripts/start-server.sh` 获取 `screen_dir` 和 `url`
3. 用 `Write` 写入 HTML 内容到 `screen_dir`
4. 告诉用户 URL
5. 收尾时调 `stop-server.sh` 关闭

### 完成后 ASK 部分
1. 批量修复全部完成 / 用户选不进入批量修复后
2. AI 用 `AskUserQuestion` 询问：结束 / 有其他任务

## 当前基线行为（修改前预期失败）

### HTML server 部分
1. ❌ 无 HTML server 启动机制
2. ❌ 复杂架构图用 Mermaid 硬塞，挤成一团不可读
3. ❌ 无 `start-server.sh` / `stop-server.sh` 调用

### 完成后 ASK 部分
1. ❌ 批量修复完成后直接输出汇总，不询问是否结束/有其他任务
2. ❌ 用户选不进入批量修复后直接结束，不询问

## 压力因素

- 7 个微服务用 Mermaid 渲染会挤成一团，无法阅读
- 流程结束后用户可能还有其他文档要审核，直接结束会打断工作流
