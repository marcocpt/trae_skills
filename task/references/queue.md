# 队列目录与发布格式

本协议只定义本地收发件，不是新的 Feature/Bug 状态系统。队列真实文件夹表示派单位置，人的看板由主模型在项目既有入口维护。

## 目录

```text
docs/AI/tasks/
├── pending/<任务ID>/
│   ├── task.json
│   └── prompt.md
├── running/<任务ID>/       # 工具追加 claim.json
├── submitted/<任务ID>/     # 完整交付，未验收
└── closed/<任务ID>/        # 工具追加 review.json
```

初始化：`python3 <skill-dir>/scripts/queue.py --queue <路径> init`。工具仅建目录，不发布或执行任务。不得在多个 app 中分别复制队列；必须指向同一个本地目录。POSIX flock 只保证遵守工具协议的本地进程互斥，不支持多机、网络文件系统、绕过工具的写入者或恶意进程。

## 主模型发布

先在队列的隐藏临时目录写完整任务包，再在没有同名任务时原子移入 pending；同一 ID 在四种位置只能出现一次。发布由主模型串行负责，执行 agent 不自行增加任务。已有外部任务不得直接复制成第二份可领取任务；先确认无人执行，再迁移并让旧入口只指向新入口。

`task.json` 是调度信封；例子中的路径必须替换为本任务真实绝对路径。执行包的产品事实、批准和 Git 动作授权仍由 prompt 引用的既有属主承载。

```json
{
  "task_id": "F33-003",
  "depends_on": [],
  "write_scope": ["/absolute/isolated-candidate/scripts/module.py"],
  "required_outputs": ["REPORT.md", "baseline.json", "validation.json", "changes.patch"]
}
```

- `task_id`：字母或数字开头，后续仅字母、数字、短横线、下划线，最长 96 字符。
- `depends_on`：同一队列里需要主模型 accepted 的任务 ID；缺失、未验收或拒绝均不满足。
- `write_scope`：允许执行方写的实际文件或目录绝对路径，使用规范路径；空数组代表源仓只读。此项用于防冲突，不扩大 prompt 的写权限，也不是沙箱。各任务自己的结果目录不必列入。隔离候选有不同实际路径时可并行；同一源文件的整合顺序仍由主模型负责。
- `required_outputs`：按任务列必要产物，至少 REPORT.md、baseline.json。无需强制每个只读任务产出 patch。task.json/prompt.md 与工具回执不是交付输出。

`prompt.md` 必须给出实际目标、输入来源与指纹/批准依据、验收条件、写范围、依赖、验证方式、输出位置、停止条件及动作授权。不重复定义已有工作流字段；链接必要上游和父任务入口。来源指纹检查由执行方及主模型负责，工具只冻结信封与提示词。

## 执行方交付

在 running 任务目录内最后写 `DONE.json.tmp` 再原子 rename 成 DONE.json：

```json
{
  "task": "F33-003",
  "status": "completed",
  "outputs": {
    "REPORT.md": "实际文件的64位小写SHA256",
    "baseline.json": "实际文件的64位小写SHA256"
  }
}
```

上例只展示形状；所有 required_outputs 及报告引用的队列内产物均须列真实摘要。`status` 只取 completed 或 blocked。blocked 也交完整报告与输入基线，明确缺什么和下一安全动作。不得将未运行验证写成 PASS。

输出路径必须相对任务目录，禁止绝对、`..` 和符号链接。外部大产物通过队列内的 `external-artifacts.json` 记录位置和真实摘要，并把该回执列入 outputs；主模型还须自行复核外部实体，工具不会读取外部路径。工具只检查列出的摘要，不会自动发现报告漏列的引用。

提交时工具写 submission.json 绑定 DONE 指纹，之后移动整个目录到 submitted。不得再改提示词、DONE 或输出；需补交则由主模型保全此包、发布带新 ID 的后续任务。

## 主模型验收与异常恢复

先 verify，再按项目规则审查内容和必要验证。close 的 evidence 必须指向实际验收依据，accepted 不能由弱模型自己填写；本地工具不鉴别真实角色。拒绝也保留 closed 原交付，修正任务用新 ID 指向被拒任务，不能把被拒任务列为已通过的 depends_on。

进程在移动前中断可能留下 pending 中的 claim.json，或 submitted 中的 review.json；工具保守拒绝重复领取或不一致位置，不自动抢占。主模型确认执行者已停、保留回执和产物后人工恢复；不要按时间超时直接回收。清理遵守父项目保留规则，任务文件不能替代唯一证据。验收关闭不代表已提交、合并、发布或主流程整体完成。
