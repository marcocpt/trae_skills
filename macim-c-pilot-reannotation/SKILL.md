---
name: macim-c-pilot-reannotation
description: 当需要在 Macim C 档试水视觉区域标注数据集中**新标未进行的屏批次**（"选取未进行的屏批次并行标注"、"你也同步处理"、claim_range 领段 + submit_screen 提交）或**重标/修订某一屏或多屏**的框几何（"按规范改某屏"、"重标 N"、"框不紧致"、"单屏修订"），或需要判定某个框是否偏松/偏紧、定位一张工作台截图属于哪一屏时使用。覆盖：像素级墨迹外接框测量、深色/混合主题分区分色阈值、框外扩窗口测负留白、兄弟屏半成品副本识别（幽灵框/note 错位/漏标行）、截图认屏、工作台草稿冲突检查、envelope+audit 构建、validate_a 与 screen_patch 落地、租约/批次门禁、多屏并行子代理分派（含父代理字段级核验与 Electron OOM 防护）。
---

# Macim C 档试水：视觉区域标注重标

## 何时用

- owner 说「按规范改某屏」「重标 N」「这几屏框不紧致」
- 需要判定某框是否偏松/偏紧，或定位一张工作台截图属于哪一屏
- 需要落地单屏/多屏修订（envelope + audit + screen_patch）

## 关键路径（每次先确认，路径可能变）

| 名称 | 路径 |
|---|---|
| A 数据仓 | `~/.cache/macim-review-p1/c-pilot-a-data`（无远端，**禁 push**） |
| 工作台 | `~/Working/Keyboard/macim-model-training-worktrees/feature/F3.3-visual-region-split/scratch/c-pilot-workbench-v2` |
| 源图 | 工作台 `capture_manifest.json` 的 `records[].file_name`（**符号链接**；`sha256` 不是文件名） |
| 规范 | A 仓 `ANNOTATION_GUIDE.md`（sha256 是 envelope 硬约束）+ 训练仓 `docs/visual_region_annotation_spec.md` v0.16 |
| 补丁路径 | A 仓 `README.md` §「单屏修订（补丁路径）」 |
| 工具 | `~/.cache/macim-review-p1/batch2/tools/{validate_a.py,screen_patch.py}` |
| python | `~/.workbuddy-ai/binaries/python/envs/default/bin/python` |

## 第一步永远是「先测，别急着改」

### 1. 紧致判定标尺

全仓 339 屏 / 11326 个 text 框实测：**四边留白众数全是 0px**（85–89%），逐屏「平均顶留白」中位数 0.03px。
⇒ 目标 = **目标可见内容的精确墨迹外接框**（整数像素，无人工外扩）。

### 2. 测量方法（照做，别自创）

```python
# ① 底色用「边框环」中位数（不要用整框中位数：大框/混合底会错）
ring = concat(img[y0:y1, x0:x0+3], img[y0:y1, x1-3:x1], img[y0:y0+3, x0:x1], img[y1-3:y1, x0:x1])
bg = median(ring)
# ② 墨迹 = |gray − bg| > thr（浅底 25~45；深底同样用相对阈值；低对比文字需降到 ~10）
# ③ 只保留与框相交的连通域（排除指针/分隔线/相邻内容）
```

### 3. ⚠️ 三个致命陷阱（踩过，必看）

1. **只看框内测不出「框切掉字形」**：墨迹超出框时，框内测量饱和到 0，看起来「紧致」。
   要测负留白，必须用**框外扩窗口（pad≈18）+ 只保留与框相交的连通域**。
   （屏 131 状态栏 9 框切掉字形上部 6–14px，用框内判据完全看不出来。）
2. **深色主题屏用全局灰度阈值完全失效**：深底 g≈40 时 `g<170` 把整块算成墨迹 ⇒ 留白恒 0 的假象。
   必须「边框环估底色 + 相对底色阈值」；**混合主题（浅标题栏 + 深内容区）要分区分色**。
3. **自动结果只当初稿**：每个改动过的框都要**放大裁图目视复核**；查漏用「全图连通域扣框集合外扩 2px」，
   残余必须逐条解释（分隔线/指针/装饰/面板边框）。

### 3b. ⚠️ 三类实测踩过的「自动测量」错误（owner 2026-10-06 在屏 73 现场纠正）

| 症状 | 实测案例（屏 73，GT 序号） | 根因 | 对策 |
|---|---|---|---|
| **过覆盖：吃进邻居** | `#74` Git 分支图标，自动测得 `[2433,1414,2486,1433]`(w53)，**与邻居文字框 `#71 [2470,1413,2540,1437]` 重叠 16px**；owner 收紧为 `[2433,1414,2462,1431]`(w29) | 连通域把相邻文字笔画并进了图标 | 改完做**两两框重叠检查**：明显交叠（尤其 `non_text`×`text`）逐个裁决「是两个对象还是一个」；图标框只框 glyph |
| **过覆盖：吃进行内留白/第二行** | `#69` 主题说明文字，自动测得 `[546,1376,899,1409]`(353×33)；owner 收紧为 `[568,1376,880,1392]`(312×16) | 行内左右留白与下方内容被并进连通域 | 文本行**只框可见字形**，左右各留 ≤2px；**高度必须≈行内字形高**，明显更高就是吃进了别的行 |
| **欠覆盖：右端少框** | `#33` URI Handling 导航文字，自动测得 `[80,386,215,408]`，右端**比墨迹少 5–9px**；owner 补到 `[80,386,224,408]` | 末尾低对比/细笔画被阈值漏掉 | 阈值别一刀切（低对比文字降到 ~10）；**右端必须用外扩窗口复核**，确认没有漏掉的尾部字形 |

**改完必做的三项自检**：
1. 每框用**外扩窗口（pad 3–18）+ 只保留与框相交的连通域**算负留白 ⇒ 不应有 <−1px。
2. **两两框重叠检查**：明显交叠的逐个复核。
3. **同行文本高度自检**：同一行的多个 text 框高度应接近；某个明显更高 ⇒ 吃进了别的内容。

### 3c. ⚠️ 信封可能是「兄弟屏的半成品副本」（2026-10-07 屏 307 实证）

某屏的已提交信封**不是独立标注**，而是拿同窗口模板的兄弟屏框表改出来的半成品。实测屏 307 = 屏 298 的副本，症状三类：

| 症状 | 检测方法 | 307 实测 |
|---|---|---|
| **幽灵框**：bbox 压在空白背景上 | 逐框跑「框内墨迹」测量，四边全无墨迹（`NO INK`）⇒ 该框不存在 | 9 个（b008/b019 等） |
| **note 指向本屏不存在的行** | 把该屏 note 与**兄弟屏的 note 列表**求交 | b015/b019/b022/b023/b028/b032/b034 的 note 逐条命中 298 的 File Encoding / Unicode (UTF-8) / File System Watcher 等 |
| **对象集合缺行** | 数「结构性重复单元」个数 | 侧栏应 9 行 ×（图标+文字）+ 按钮 2 = 20 框，原信封只有 11 |
| **note 与坐标错位** | 同一坐标在兄弟屏里是什么对象 | b012/b013 在 Core 行坐标上，note 却写 Editor |

⇒ 命中任一症状即**不要按「只缩紧」处理**，按全面重标：删幽灵框、补齐漏标、逐框重测。
（幽灵框的 note 未必是垃圾——它可能完好描述着**兄弟屏**的对象，所以「note 合理」不能当作框有效的证据。）

**几何口径标定（两条独立证据，缺一不可）**：

1. **兄弟屏对拍**：同一窗口模板的两张截图，同位置元素**逐像素相同** ⇒ 在同一坐标上对两张图跑同一测量，结果必须一致（不一致 = 测量脚本有问题）。
2. **紧致基准屏**：找同批里已确认像素级紧的屏（本轮 **294**：chrome 框 `[95,30,110,44]` / `[112,32,153,44]`），用它反推**阈值口径**——307 上 thr=20 的实测值与 294 已提交值完全一致 ⇒ 证明 thr=20 即本批口径。
   同批里 292 是反例（整体松 2–4px），别拿它当基准。

**阈值必须高于「淡行底色带」**：Atom 设置页每个设置项行在 y 上有一条 Δ≈12 的整幅淡带（行容器边框）。thr=8 会把行高从 12px 虚增到 15px、把整幅 638px 宽的淡带算成墨迹。先用行剖面（`rows.py` 式）量出该 Δ，再把阈值定在它之上（本轮 thr=20）。

**「左/上多 1px」是膨胀不是平移**：本轮 51 个保留框 Δ 均值 L **+0.84** / T **+0.92** / R **+0.04** / B **+0.04**，σ 0.4–0.9。R/B 准确、L/T 系统性 +1 ⇒ 逐框收紧正确；若四边同常数且 σ≈0 才是整体平移（错）。

**三个几何测量陷阱（本轮踩到）**：

1. **「窗口=框本身」永远测不出越界**——必须外扩。但外扩窗口 + 连通域**会过覆盖**：邻行笔画与目标连成同一连通域时把框撑大（实测 b014 `[281,84,919,97]` → `[281,83,920,98]`）。对策：**两段式窗口**（pad 2 → 6 → 9），仅当测得范围**触到窗口边界**时才加宽；否则接受 pad 2 结果。
2. **实心控件相对自身填充没有「墨迹」**：紧致度审计对已勾选复选框/彩色填充给出「四边 0 留白」的**假阳性**（环底色被填充污染成 ~143）。必须改成**对框外底色**测填充范围。反之，**1px 边框的空心复选框**要用较松阈值（thr≈14）才读得到完整 15×15 轮廓。
3. **鼠标指针会被算进相邻图标框**：白色手型指针常压侧栏/菜单行；全仓惯例是**指针不入 GT**（先例屏 89/94/205/216/298…）。本轮 URI Handling 图标用宽窗口测得 `[17,146,34,162]`（吃进指针下缘），收窄窗口后真值才是 `[17,152,32,162]`。**凡框附近有指针，必须用不含指针的窗口复测**。

### 3d. 漏标对象的系统查法（不只是重测已有框）

重标时必须独立做一次**未覆盖墨迹检查**：全图连通域扣「框集合外扩 2px」，残余逐条解释。但**粗块中位底色（如 40×40 分块）在明暗交界处会失效**，会把整个标题栏+标签栏报成「未覆盖」（假阳性）。对策：先按已知结构分区（标题栏/标签栏/侧栏/内容区/状态栏），每区单独估底色后再取残余。

结构性漏标的快速判据：**同批兄弟屏有、本屏没有的「重复单元」**。本轮 307 缺 9 个侧栏条目框 + 1 个滚动条 thumb，而 292/294/295/299/309/315/316 都有滚动条框。

### 4. 认屏：只能靠框几何

- 整幅 FFT NCC 匹配**不可用**（截图带虚线框、源图没有，NCC 仅 0.2–0.5）。
- 同内容源图**可能对应多屏**（屏 85 与 181 左上 560×360 逐像素相同）——不能靠「图长得一样」认屏。
- 做法：① 彩色框线定倍率（用可辨识图标，如 Atom 绿图标 59×55 ↔ 源 20×19 ⇒ 2.92×）；
  ② 线性拟合精修原点（用「墨迹 ↔ 框底」多点拟合，残差 <1px）；③ 映射回源坐标与各屏 JSON 逐框比对。

## 第二步：落地前必查工作台草稿

**`drafts-visual-v1/draft-NNNN.json` 优先于候选**（`loadManifest` 先 `restoreCurrentScreenDraftIfPossible()`
再 `materializeCandidatesOnCurrentScreen()`）。若存在且是 owner 真实改动
（`annotationStatus=已裁定` + `reviewedByOwner:true` + `sourceKind=human_new`）：

- `screen_patch` **不会清它**。判据 `draft_is_pure_materialization` 要求**三条全中**才清：
  ① 坐标逐框等于旧信封 ② 全部 `annotationStatus=提议` ③ `reviewedByOwner` 非真。
  缺一即判「owner 真实改动」而**故意不动**（防误删 owner 工作）⇒ 工作台载入仍显示草稿 ⇒ **落地等于空转**。
- ⇒ **停下来查清草稿是什么，再问 owner**；不要盲落地，也不要盲删。

### 先判定草稿「是什么」——不要用精确元组比对

**❌ 错**：直接比两组 bbox 元组是否相等。1–2px 舍入差会让**全部**框判成「独有」
（实测：75 框草稿 vs 75 框信封，精确比对得出「草稿独有 65 / 信封独有 65」的假象）。
**✅ 对**：**中心点最近邻 1:1 配对 + 距离分布**。

```python
ca = A[:, [0,2]].mean(1)[:,None]; cb = B[:, [0,2]].mean(1)[:,None]
ya = A[:, [1,3]].mean(1)[:,None]; yb = B[:, [1,3]].mean(1)[:,None]
d = np.hypot(ca-cb.T, ya-yb.T); j = d.argmin(1)
# 看 median / P90 / max，以及 visualKind 一致数
```

判读：中位 **<1px** ⇒ 同一套标注（只是舍入差）；中位 **>3px** ⇒ 真的不同版本。

### 处置（工作台没有「放弃草稿」UI）

`RegionGTDraftStore` 只有 `loadDraft` / `saveDraft`，**没有删除接口** ⇒ 只能文件层：

1. **备份**：`cp -p <草稿> <backup>/draft-NNNN.json.pre-manual-<TS>`，比对 sha256（`cp -p` 保留 mtime）
2. **移走**：`mv <草稿> <backup>/...`（**用 mv 不用 rm**）
   - ⚠️ **移走前先确认工作台没停在目标屏**（`ps aux | grep [M]acim` 看 app 是否在跑；
     再看目标草稿的 mtime 是否是最近几分钟——是则说明正在编辑），否则 app 会把草稿写回来
3. 工作台选中该屏 → 点「载入工作区」→ 应看到修订后的框
4. 抽查框数/坐标是否等于 A 仓 envelope；**重点复核草稿与修订版的分歧框**（按 GT 序号）
5. 复核后「确认发布」

**回滚**：`git -C <A> revert <commit>` + 恢复 `annotation_proposals.split.json.pre-revision-NNNN` + 恢复草稿备份。

## 两种作业模式（先问清 owner 要哪种）

| | **A. 全面重标** | **B. 只缩紧** |
|---|---|---|
| 对象集合 | 可增/删/拆/并 | **一律不动**（只改 `bbox`） |
| `visual_kind`/`note`/`origin`/`source_refs`/`box_id` | 可改 | **逐框原样** |
| 典型指令 | 「按规范改某屏」「重标 N」 | 「已发布的只缩紧，其他不要动」 |

B 模式下若发现疑似漏标/错并框，**只写进报告，不改**。

## ⚠️ 汇报口径：**一律用「GT 序号」**（owner 2026-10-06 指定，硬规则）

**owner 只能在 GT 工作台里核对，所以向 owner 报任何框，必须用「GT 里能看到的序号」，不许用 A 仓 `box_id` 或自造编号。**

**GT 序号 = `region.identifier`**（源码级确认）：
- 侧栏 Region 行可见文本 = `"\(row.identifier)"`，**已裁定的行前面加 `✅ `**
  （`RegionGTSidePanelView.regionRow`：`let title = row.isAdjudicated ? "✅ \(row.identifier)" : "\(row.identifier)"`）
- 画布角标 = `Text("\(region.identifier)")`（`RegionGTCanvasView`，受命令条「编号」开关控制，默认隐藏）
- **起算 = 0**。物化自候选时 `identifier` 直接继承候选 `id`
  （`RegionGTCandidateTarget.identifier` 注释：「候选 `id`（同图唯一）——继承为 Region 的机器标签 id」）
- ⇒ **无草稿的屏：GT 序号 = 候选 `targets[].id`**，而候选 id = `convert_screen` 按
  `(bbox[1], bbox[0], bbox[3], bbox[2], box_id)` 排序后的索引

### 怎么算出「载入后会看到的 GT 序号」

```python
idx = {b['box_id']: i for i, b in enumerate(
        sorted(new_env['boxes'], key=lambda b: (b['bbox'][1], b['bbox'][0], b['bbox'][3], b['bbox'][2], b['box_id'])))}
# idx[box_id] 就是该框载入 GT 后显示在画布/侧栏上的序号
```

### 有草稿的屏：GT 序号会变

画布显示的是**当前草稿的 `identifier`**。草稿移走、重新载入候选后，序号会**整体错位**
（屏 73 实测：草稿 #71 ↔ 载入后 #74、草稿 #2 ↔ 载入后 #8）。
⇒ 报这类屏时必须**同时给「草稿期 GT 序号」和「载入后 GT 序号」**，并附 bbox 兜底。

### 其他两套编号（**不要拿去汇报**，仅供内部工具链）

| 编号 | 用途 | 起算 |
|---|---|---|
| A 仓 `box_id`（`sNNNN-bNNN`） | A 仓 envelope / audit 内部标识，数组顺序 ≠ 候选排序 | 1 起 |
| 候选 `targets[].id` | 机器 schema；**恰好等于无草稿时的 GT 序号** | 0 起 |

## ⚠️ 「已发布 / 提议」在 GT 里是**两个层级**，别搞混（2026-10-06 实测）

| 层级 | 判定源 | 怎么变成「提议/未发布」 |
|---|---|---|
| **Region 级**（画布线型、侧栏 ✅） | **内存**里的 `region.semantics.annotationStatus` | 铺入候选时 `RegionGTMaterializationBaseline.materializedCandidate` **固定 `annotationStatus: .proposed`** ⇒ **载入后每个框本来就是「提议」**（画布虚线、侧栏无 ✅） |
| **屏 级**（屏列表「已发布」chip / 发布控件） | `isEffectivelyPublished` = `hasPublished`（正式产物磁盘事实）**且** `!screensWithProposedRegion.contains(screenID)`；而 `screensWithProposedRegion` 来自**扫磁盘草稿文件**（`RegionGTDraftStore+ProposedScan.draftHasProposedRegion`） | **草稿文件里存在 `annotationStatus == "提议"` 的 region** 才为「未发布」 |

**致命细节**：`draftHasProposedRegion` 在**草稿文件不存在时直接 `return false`**（第 29–33 行）
⇒ **「无草稿」= 「不含提议」= 屏显示「已发布」**。

**推论（patch 路径的坑）**：
- `screen_patch` 落地只改 **A 仓 envelope + live 候选**，**不会**写草稿。
- 如果落地前该屏**没有草稿**，落地后**屏级仍显示「已发布」**（即使内存里所有 region 都是「提议」）。
- 如果落地前该屏**有 owner 的真实草稿**，`screen_patch` **不会清**（判据见上）⇒ 屏级仍是草稿说了算。
- ⇒ **想让屏级变「未发布」，必须有一个「含提议 region 的草稿文件」**。两条路：
  1. **app 原生（推荐）**：GT 里载入该屏 → **做任意一次编辑**（哪怕方向键把某框挪 1px）→ 编辑自动保存写出草稿
     （`installDraftAutoSaveRequester`；「保存草稿」按钮 2026-10-04 已移除，改为编辑即自动保存）→ 屏立刻变未发布。
  2. **直接写草稿文件**：按 app draft schema 生成 `draft-NNNN.json`（全部 `annotationStatus: 提议`、
     `reviewedByOwner: false`、坐标取 A 仓当前值、`identifier` = GT 序号）。⚠️ app 运行中且停在目标屏时可能被内存态覆盖。
- 另注：草稿**解析失败 / profile 不符**按 **fail-closed** 计为「含提议」⇒ 显示未发布（别用坏文件去凑这个状态）。

## 「裁定属性」在哪里

**A 仓信封没有状态字段**。状态在**候选文件**里：
- live 候选 `annotation_proposals.split.json` 的 `targets[]._needs_adjudication`
- `true` = **提议**（待裁定）；缺失/false = 已裁定
- `candidate_codec.convert_screen` **恒置 `_needs_adjudication: True`** ⇒ 经 `screen_patch` 落地的屏，
  其全部 target 都会变成「提议」

owner 说「缩紧的裁定属性改为提议」时，先查该屏候选 target 是否**已经全为 true**（多数情况已是，则无需额外动作）。

## 第三步：envelope + audit

顶层字段沿用旧 envelope：`schema_version:"a-screen/v2"`、`screen_id`、`batch`、`app`、`image_sha256`、
`img_w`、`img_h`、`producer`、`spec_version:"v0.16"`、`ontology_version:"visual-regions-v1 (v3.9)"`、
`created_at`、`input_sha256`、`guide_sha256`、`lease_id`、`generation`、`boxes`。

- `guide_sha256` = **构建时现算**的当前 GUIDE sha256（GUIDE 会被并发 agent 随时改动）
- `input_sha256` = `inputs/<batch>/input-lock.json` 的 **`batch_input_sha256`**（不是 `pinned_input_fingerprint`）
- box：`{box_id, bbox, visual_kind, note, origin, source_refs}`；`origin`/`source_refs` 自洽
  （`reviewed_candidate` ⇒ 非空 refs；`visual_new` ⇒ `[]`）；除对象集合变化外逐框沿用旧值，`box_id` 保持稳定
- audit：旧结构 + **必填** `correction:{supersedes:<该屏当前提交哈希>, note}`

## 第四步：校验与落地

```bash
PY=~/.workbuddy-ai/binaries/python/envs/default/bin/python
A=~/.cache/macim-review-p1/c-pilot-a-data
shasum -a 256 $A/ANNOTATION_GUIDE.md                      # 现算 guide sha
$PY $A/tools/validate_a.py <env> --screen-id N --input-lock $A/inputs/<batch>/input-lock.json
# ↑ --input-lock 必须显式传（默认值只对 51-100 有效，否则报 screen outside fixed batch）
$PY ~/.cache/macim-review-p1/batch2/tools/screen_patch.py \
    --screen-id N --envelope <env> --audit <audit> --batch <batch> [--dry-run]
```

落地后核验（父代理必做）：
1. **逐框对象集合 diff**：新 envelope 与旧 envelope 的 `box_id` / `visual_kind` / `note` / `origin` / `source_refs`
   必须一一相同（B 模式）；框数不变。
2. 指纹：`guide_sha256` == 当前 GUIDE；`input_sha256` == 各批 `batch_input_sha256`；`image_sha256`/`img_w`/`img_h` 未变。
3. audit `correction.supersedes` == 该屏修订前提交。
4. **候选写回链首尾相接**：每屏 `batches/<batch>.revision-NNNN.json` 的
   `candidate.before_sha256` 应等于上一屏的 `after_sha256`，最后一屏的 `after` 应等于当前 live 候选 sha256。
   ⚠️ **链在「写回回执」处会合法断开**（2026-10-07 实测）：`a_to_candidate` 写回会整体重写 live 候选，
   之后的 patch 的 `before` 自然等于「最近一次写回之后 + 期间其他会话 patch 之后」的值，而非上一条 revision 的 `after`。
   **不要当异常**。真正要断言只有两条：① 本条 revision 的 `sha256_after` == **当前 live 候选 sha256**；
   ② `screens_unchanged == 770`（其余屏逐字节保留）。两个时点之间候选被改动，也可能是**别的会话在别的批次上跑 patch**
   （候选是全 771 屏共用的单文件）。
5. **Δ 标准差**（区分「逐框修正」vs「整体平移」）：逐框算 `new_bbox − old_bbox`，
   若四边均值≈同一常数且 σ≈0 ⇒ 疑似整体平移（错）；σ 与均值同量级 ⇒ 逐框修正（对）。
6. `batches/<batch>.revision-NNNN.json` 全部生成；A 仓 `git status` 干净。
7. 通知 owner 点「载入工作区」。

## ⚠️ `source_refs` 的校验基准 = **pinned 基线候选**，不是 live 候选

`screen_patch` 用 `git show HEAD:inputs/<batch>/candidate.json` 当基线，`candidate_codec.convert_screen` 要求：

```
baseline_targets[ref["candidate_target_id"]]["source"] == ref["source"]
```

否则报 `ValueError: source_refs do not match pinned candidate`（**信封/审计/预览已写盘、候选未 splice、A 仓变脏**）。

- **pinned 基线的 target 数量与编号和 live 候选完全不同**（实测 151-200 批：屏 194 pinned 只有 17 个 `legacy_candidate`，id 26882–26899；
  屏 195 pinned 30 个 `groundcua_truth_candidate`，id 1–31；而 live 候选分别是 56 / 45 个）。**绝不能拿 `annotation_proposals.split.json` 的 target id 当 refs。**
- **⚠️ 同一批内不同屏的 pinned `source` 可以不同，必须逐屏读**（2026-10-07 实测 301-350）：306/307/310/311/313 的 pinned 全是
  `legacy_candidate`（id 28338+），而 **312 全是 `groundcua_truth_candidate`（id 0–38）**。⇒ 别按批外推 source 名，也别拿邻屏的 id 段做参考。
- **provenance 失真的识别**：若某屏旧信封**全部** `origin:"visual_new"` 而 pinned 基线其实有几十个候选 ⇒ 是**离群错误**（实测 312：62 框全 visual_new，
  而 pinned 有 36 个候选，且与 live 框是 1:1/N:1 对应；同批屏 317 落成 `reviewed_candidate 21 / visual_new 19`、屏 474 落成 `30 / 43`）。
  A 模式重标时应按「紧致框落在所引 pinned 粗框内（容差 4px）」恢复 refs，**一个粗框拆成 N 个紧致框时 N 框全部引用同一 id**。
  注意 `groundcua` 粗框常把**一个菜单项拆成两段**（如 `Atom Dark` = id30「Atom」+ id31「Dark」）⇒ 该框同源引用 `{30,31}`（多 ref 必须同源）。
- 正确做法：`git -C <A> show HEAD:inputs/<batch>/candidate.json` 取出该屏 targets 再比对；
  **拆分/新增框优先引用与同源兄弟框相同的 pinned target**（先例屏 177 的 11 个快捷键框全部引用名称框那条行级 target）；
  若 pinned 基线里根本没有对应对象（例：页脚 `×`、194 的页脚三件套）⇒ 用 `origin:"visual_new"` + `source_refs:[]`，
  与同屏同源框保持一致。
- **失败恢复**：`git -C <A> checkout -- screens/screen-NNNN.json audit/screen-NNNN.json previews/screen-NNNN.json`（预览是 `.png`）后重跑。
  注意 A 仓常有并发 agent，`checkout` 前先确认自己刚写的这三个文件脏。
- **怎么把 pinned 基线喂给子代理**（2026-10-07 实测）：`candidate.json` 的顶层是
  `{schema_version, created_at, screens:[...], generator_sha256, manifest_sha256}`，
  而 `screens[]` 的键是 **`image_id` / `image_sha256` / `targets`——没有 `screen_id`**，
  且 `image_id` 就是 1..771 的屏号。所以：
  ```python
  pin = {s['image_id']: s for s in json.load(open('/tmp/pinned.json'))['screens']}
  facts['candidate_targets'] = pin[N]['targets']     # 覆盖掉 dump_candidates 的 live 值
  ```
  写成 `pinned/dump-<N>.json` 给子代理；`facts/dump-<N>.json`（`dump_candidates.py` 产出）
  在本批实测**恰好等于 pinned**，但别假设——改批后必须重新核对。
- **⚠️ 派发前必须核验 `pinned/dump-<N>.json` 的容器形状**（2026-10-07 实测踩到）：同一批次里
  不同会话写出的 pinned 形状会**不一致**——本批 app-sync33 是**字典** `{batch,screen_id,…,candidate_targets:[…]}`
  （=文档约定），而 app-sync34 那轮落盘成了**裸 target 列表** `[{id,bbox,source,…}]`。
  子代理按 BRIEF 的 `['candidate_targets']` 取值时，遇到裸列表会**自行猜测适配**（有的按列表遍历、
  有的当成字典取空）⇒ `source_refs` 可能静默取错，`validate_a` **不报错**，直到 `submit_screen` 才炸。
  ⇒ 父代理写完后**必须断言**：
  ```python
  d = json.load(open(f'{T}/pinned/dump-{n}.json'))
  assert isinstance(d, dict) and 'candidate_targets' in d, f'{n} pinned 形状不符'
  auth = {s['image_id']: s['targets'] for s in json.load(open('/tmp/auth.json'))['screens']}
  assert [(t['id'], t['source']) for t in d['candidate_targets']] == \
         [(t['id'], t['source']) for t in auth[n]], f'{n} pinned 与权威基线不一致'
  ```
  形状不符就**归一化后再派发**（在 pinned 侧修，**不要**改 BRIEF 里的约定）；若已有子代理跑完，
  其产物仍须按**归一化后的 pinned** 重跑 §8 自检与父代理字段级核验。

## 父代理独立复核：用「框内墨迹紧致度审计」而不是几何复算

几何复算（自己再跑一遍 tighten）**不可靠**——同一套自动方法在「紧贴面板边框 / 1px 高字形 / 低对比小 glyph」上会给出 ±22px 的假分歧。

**可靠的复核 = 紧致度审计**：对每个框**只用框内墨迹**（框内众数底色 + 自适应阈值）求外接框；
紧致框的墨迹必然四边贴边 ⇒ **内留白应全 ≤1px**。先在同批**已验证紧致**的屏上标定通过率（177/310/182 = 49/51、94/96、60/62），
再看目标屏是否同档。未通过的应当是「1px 窗控横线」或「2~3px 抗锯齿差」这类已知形态，逐条解释。
**两个必知前提**：①该指标**只对 `text` 框成立**——`non_text` 内容图 / 海报的框内不是均匀墨迹，会给出假「松」（实测屏 675 整幅拼贴框的 bottom 内留白虚高到数百 px）；②算内留白时**墨迹坐标与框坐标必须同一参照系**，混用「相对窗口」与「绝对」会让整批结果系统性偏移（实测第一版脚本因此把全部 115 个 text 框判成「越界」）。
**父代理读到明确缺陷时要区分「数量级错误」与「亚像素/边缘偏差」**：前者（如框覆盖整块海报、右边界多 127px）有确凿量化证据，应直接修正并复跑 `validate_a`；后者（彩色艺术字叠在复杂海报上，掩膜被相邻元素污染、精度 ±3px 以上）**不要猜**，写进 REPORT 交 owner——修正本身也是一次标注，精度不足时改更糟。

**⚠️ 审计的底色估计必须用「框外环（3px）中位数」，不要用本节前面 §2 的「框内 3px 带」（2026-10-07 单屏重标 312 实测修正）**：
审计的对象是**已经紧致**的框，此时框内 3px 带几乎被字形覆盖（如 29×10 的侧栏文字框）⇒ 底色估错 ⇒ 掩膜近乎全真 ⇒ 内留白假 0（**假 PASS**）或假 `L18/T18`（**假松**）。
§2 的「框内 3px 带」只适用于**从粗候选起测**（那时框内有富余背景），**不适用于审计紧致框**。
改用框外 3px 环的**中位数**（中位数抗少量污染像素）后，屏 312 实测有区分度：新信封 **38/38 text 框紧致（100%）**、旧信封 **19/35（54.3%）**。
两个配套细节：① 判据用「**框内**取掩膜求外接框 → 四边内留白」，**不要**用「外扩窗口取墨迹 bbox」——后者会把邻居并进来（实测同一批：外扩法 24 条假「松」→ 框内法 0 条）；② 越界/切字检查才用外扩窗口，但**必须加连通域过滤**（只保留与框相交的连通域）。

## 多屏并行：子代理分派模式（重标 / 单屏修订）

- 每屏一个子代理，**在一个消息里同时发起**（并发且前台）。
- **子代理只做到 `dry-run`**：实测 → 建 envelope + audit → `validate_a` → `screen_patch --dry-run` → 写 REPORT。
  **真实 patch 由父代理串行执行**（避免三写并发；锁虽能串行，父代理落地更可控、更好核验）。
- 写一份**共享任务书**放任务目录（路径速查 / 每屏事实表 / 验收标准 / 测量方法 / schema / 命令 / 硬约束 / 汇报格式），
  子代理 prompt 里只给「读任务书 + 你负责哪一屏 + 该屏已知线索」。
- 父代理独立复跑 `validate_a` 并核对信封字段（guide/input 指纹、image_sha256、origin/refs 自洽、box_id 唯一）。
- **单屏重标（owner 说「重标 N」/「N 重做」）= 同一模式的最小实例**（2026-10-07 屏 312 跑通）：父代理建任务目录
  （`tasks/redo-<N>/{BRIEF.md,pinned/dump-<N>.json,facts/}`）→ 派 **1 个**前台子代理做到 `--dry-run` → 父代理
  独立复跑 `validate_a` + 16 键/指纹/refs 解析/box_id/IoU/audit 字段级核验 + **紧致度审计（框外环底色）** →
  真实 `screen_patch` 落地 → 核验 `revision-<N>.json`（`screens_unchanged==770`）与 live 候选 == `convert_screen` 输出。
  ⚠️ 子代理的**汇报数字可能笔误**（实测 312：自报 kind `44→47 / 18→14`，实为 `35→38 / 27→23`）⇒ **以磁盘产物为准**，父代理核验后顺手改正 REPORT。
  ⚠️ 子代理自曝「超 Read 预算」时，按协议 §9 由**父代理补录**进 audit `observation_notes` 再落地。
- **落地会让该批 `writeback.json` 回执过期**（即使不是当前 `active_batch`）⇒ 后续该批/整链 QC 需重建（见下）；单屏重标照做，但要在汇报里向 owner 点明。

## 多屏并行：**新屏批量标注**模式（不是重标；2026-10-06 实测 27 屏 / 1344 框跑通）

触发语：「选取未进行的屏批次并行标注」「你也同步处理」。与上一节的差别：**走 `claim_range` 租约 + `submit_screen` 提交**，
不用 `screen_patch`；`active_batch` 决定可领范围。

**每轮固定 5 步**（一轮 = 3 个前台子代理 × 3 屏 = 9 屏，`MAX_CLAIM_SIZE` 就是 9）：

```bash
A=~/.cache/macim-review-p1/c-pilot-a-data
STATE=<训练仓>/reports/visual_regions/c-pilot/local-state.json
PY=~/.workbuddy-ai/binaries/python/envs/default/bin/python
# ① 领段（返回 screen_ids/lease_id/generation/expires_at）
cd $A && $PY tools/claim_range.py --app-id <app-id> --size 9 --state "$STATE" --repo "$A"
# ② 预取事实（--batch 必须显式传；dump/overlay 的默认值是 101-150）
for n in ...; do $PY ~/.cache/macim-review-p1/batch2/tools/dump_candidates.py --screen $n --batch <batch> > facts/dump-$n.json; done
# ③ 写 BRIEF.md（从上一轮复制后替换 lease_id/generation/app_id/批次/屏号）
# ④ 一条消息并发 3 个子代理（各 3 屏）：实测 → envelope+audit → validate_a → overlay 目视复核 → REPORT（不提交）
# ⑤ 父代理：heartbeat → 独立复跑 validate_a → 字段级核验 → 串行 submit_screen
$PY tools/heartbeat.py --app-id X --lease-id Y --generation N --state "$STATE"
$PY tools/submit_screen.py <env> <audit> --screen-id N --app-id X --lease-id Y --generation N --state "$STATE"
#    ⚠️ 提交循环里按屏号取产物一律用 `find <taskdir> -name "screen-*<N>.envelope.json"`：
#    各子代理产物的补零不一致（同轮里既有 `screen-0675.*` 也有 `screen-678.*`），
#    写死 `screen-0*<N>.*` 会对无补零的那批 no matches，循环空跑却不报错（实测 678–683 六屏静默漏交）。
```

### 开新批（批次门禁）：`active_batch` 是**全局单值**，多会话并行时切批会打断所有在途会话

**开一批 = 两步**（缺一不可）：

```bash
# ① pin 固定输入（additive，安全，可提前做；先 --dry-run 看 fingerprint）
$PY ~/.cache/macim-review-p1/batch2/install_batch_inputs.py --batch 451-500
#    约束：批次必须是 51+ 且 50 屏一档（lower-51)%50==0、upper==lower+49）；源基线默认取 51-100 的冻结快照
# ② 切 active_batch（危险！见下）—— 训练仓提交 chore(c-pilot): <prev batch> gate passed, 开启批次 <next>
```

**① 可以提前做**（本项目既有实践：计划日志里「批次未切换…仅完成前置准备（A 输入 pin）」）。
**② 必须先确认前一批没有在途工作**：

- `submit_screen.py` 与 `claim_range.py` 都按 `control.active_batch` 解析批次；
  `submit_screen` 对不在范围内的屏直接抛 `screen is outside active batch`。
- ⇒ **只要前一批还有 `status == claimed` 的屏（别的会话正在标注），切批就会硬拒它的提交**，
  该批卡在 N/50、QC/写回/gate 全部无法收口 —— **比等待更糟**。
- **切批前必查**：`[s for s in screens if lower<=s['screen_id']<=upper and s['status']!='completed']` 必须为空
  （或那些屏的租约已过期且不会再续）。`claim_range` 返回的 `active_leases` 也能看出谁还在跑。

**判断对方是否还活着**：看它工作目录的文件 mtime（如 `tasks/b<batch>/lead/`），
`ls -lat <dir> | head` 有最近 1–2 分钟的文件 ⇒ 活着，**等**；几分钟无新文件 ⇒ 可能已停，可等租约到期后接管。

**等待手法**：起一个后台守望脚本（每 60s 读 `local-state.json`，前一批全部 completed 或 `active_batch` 变化即退出），
比阻塞式 sleep 好；收到通知再切批。

### 批次闭环（QC → 逐屏视觉复核 → 候选写回）：**不要与主 coordinator 抢做**

```bash
$PY tools/qc_batch.py --state "$STATE" --batch <batch>                     # 结构 QC + 渲染 50 张 overlay（会自己提交）
$PY tools/record_visual_review.py --screen-id N --decision pass --reviewer <name> --note "..." --state "$STATE"   # 逐屏，不提交
git add qc/visual-review-<batch>.json && git commit -m "chore(a-data): record <batch> visual review"
$PY tools/a_to_candidate.py --state "$STATE" --batch <batch>               # 写回候选 + 回执（幂等，重跑返回 already_written）
```

**并发风险（实测踩过）**：`qc_batch` / `a_to_candidate` 是幂等的，重复跑无害（会多出重复提交）；
但 **`record_visual_review` 是逐屏「读-改-写同一个 JSON」**，两个会话并发会互相覆盖
（本次两边都是 pass 所以没出事；**若一方标了 `fail`，会被另一方覆盖掉**）。
⇒ **动手前先看对方是否还在活动**（`git log -1 --format=%ad` + 其工作目录 mtime）；
主 coordinator（如 `app-lead`）在做闭环时，**让给它**，你只做「它不做的部分」或等下一批。

**视觉复核的可靠方法**：`qc_batch` 渲染的 `previews/screen-NNNN.png` 是**全图叠框**。50 屏全读会 OOM，改用：
1. **紧致度数值审计**（全批）：每框用「边框环底色 + 相对阈值」求框内墨迹外接框，四边内留白 >2px 记为松。
   标定：已确认紧致的批通过率 ≈ 96–97%（先例 177/310/182 = 49/51、94/96、60/62）。
2. **异常类型逐类目视**：把各类代表框裁成**一张拼图**一次读完（而不是逐屏读）。
3. 只对真正离群的屏读全图。
**⚠️ 该审计的两类假阳性（实测）**：① 深色主题上的低对比文字（墨迹 Δ<10，阈值取不到 ⇒ 假「松」）；
② **边框环被高对比内容污染**（框偏移压到字形上 ⇒ 底色估错 ⇒ 墨迹只剩几个像素 ⇒ 假「松」）。
⇒ **不得只凭数值审计就判 `fail`**；必须目视确认。

### ⚠️ 批次闭环的**两个隐藏前置**（2026-10-07 实测，缺一就卡住）

`qc_batch` 与 `a_to_candidate` 各有一个**文档里没写**的前置，第一次跑整批闭环必踩：

1. **`qc_batch` 需要 `batches/<batch>.manifest.json` 已存在** —— 它只 `load_json` 后更新
   `completed_screen_ids`，**不会创建**。缺文件报
   `FileNotFoundError: .../batches/<batch>.manifest.json`。
   **注意**：它会**先渲染 50 张 previews 再读 manifest**，所以报错时 previews 已经生成（别误判为「有人并发跑了 QC」）。
   播种模板（沿用 `batch2/tasks/w4-157-159/add_batch_manifest.py`）：
   ```python
   {"schema_version":"batch-manifest/v1","batch":"<batch>","screen_ids":list(range(lo,hi+1)),
    "completed":[],"failed":[],"status":"ready","input_lock":f"inputs/<batch>/input-lock.json"}
   ```
   写成紧凑 JSON，提交信息 `chore(a-data): seed batch manifest for <batch>`。

2. **`control.owner_gates[<batch>]` 可能**整个键缺失**（不只是 `pending`）** —— 实测 551-600 开批后
   `owner_gates` 里只有到 501-550。`a_to_candidate` 要求该键 ∈ {`pending`,`passed`}，否则 `invalid gate state`。
   ⇒ 训练仓先补一次 `owner_gates[<batch>]="pending"`（提交 `chore(c-pilot): backfill owner_gates[<batch>]=pending`），
   闭环走完再改 `passed` 并切 `active_batch`（一次提交，见下）。

**gate 收口提交**（对照 `git show aa9c531`，只动 3 处）：`control.active_batch` → 下一批、
`control.owner_gates[<batch>]` → `passed`、`updated_at`。提交信息
`chore(c-pilot): <batch> gate passed, 开启批次 <next>`。下一批 `inputs/` 可用
`batch2/install_batch_inputs.py --batch <next>` 提前 pin（additive，安全）。
`local-state.json` 用 **UTF-8 原文 + `indent=2` + 末尾换行** 写（工具就是这么写的；用
`ensure_ascii=True` 会把 34 个中文字符转义、diff 爆掉）。

### ⚠️ 多会话**任务目录命名撞车**（2026-10-07 实测，会互相覆盖）

两个并发会话都按「批次首屏 → `tasks/sync-<lo>-<hi>/r<N>`」起名，结果**用了同一个 `r3` 目录**：
对方把 578-586 写进 `r3/agent-{a,b,c}`，我把 569-577 也写进去；我 `cp` 任务书时还**覆盖了对方的 BRIEF.md**。

⇒ **产物目录一律带 app-id**：`tasks/sync-<lo>-<hi>/<app-id>/r<N>/`，且**不要在共享目录里 `cp` 覆盖**。
发现撞车后：只搬**自己屏号**的文件（`screen-0<NNN>.*`），对方的原样留下，别整体 `mv`。
`facts/` 按屏号命名、内容与调用方无关，可以共享。

**已成事实的生态约定（2026-10-07 实测，4 个会话并行）**：各会话都按 `<app-id>/r<N>/` 分目录，
并在批次根目录互相留**接管说明** `TAKEOVER-<屏段>-<app-id>.md`（内容：领取时间/租约/缘由/复用了谁的信封/
哪些废弃重做/提交哈希清单/给原会话的提醒）。**接管他人屏时照此留一份**，原会话才不会再白跑一遍。
另外批次根目录还会出现 `CLOSURE-OWNER-<app-id>.md` 这类**收口公告**——动手做闭环前先看有没有，
有的话就让给对方（避免 `record_visual_review` 并发覆盖）。

### 接管**过期租约**时复用对方磁盘产物（2026-10-07 实测 569-577）

> 盘点租约时注意：**leases 在 `local-state.json` 的 `control.leases` 下，不是顶层 `leases`**
> （顶层只有 `control/inputs/phase/screens/...`；读错会得到「0 个租约」的假象）。screens 是**列表**，键为 `screen_id`。

对方租约过期（`claim_range` 惰性回收）后我领到同一段，但对方**磁盘上已有 7/9 屏产物**。
正确做法（LESSONS「租约过期后的恢复路径」的实操版）：
1. 盘点对方目录的 `screen-*.envelope.json` / `.audit.json`（注意**文件名补零不一致**：
   有 `screen-569.` 也有 `screen-0572.`，用 `find -name "screen-*<N>.envelope.json"` 别用固定格式）；
2. 逐个把 `lease_id` / `generation` / `producer.app_id` 改写成**自己**的租约（`worker_id` 可写成
   `takeover(<原名>)` 保留归属），补齐缺屏；
3. 父代理复跑 `validate_a` + 字段核验后**立即**串行提交（租约可能又要过期）。
**先判断对方是否还活着**（其目录 mtime）：活着也照接不误——**租约是唯一权威**，
但要让对方能识别（对方提交会因 provenance 不匹配被拒，属预期）。

### 任务书模板换批时**必须同步替换的字段**（漏一个就会让子代理白跑）

`lease_id`、`generation`、`app_id`、`batch`（含所有 `--batch` 与 `inputs/<batch>/` 路径）、屏号列表、
**`input_sha256`**（= 新批 `inputs/<batch>/input-lock.json` 的 `batch_input_sha256`，各批不同！）、
`guide_sha256`（构建时现算）。
实测踩坑：451-459 的任务书仍留着 401-450 的 `input_sha256 = c2c837cf…`，子代理自己发现并改用实算值才通过 `validate_a`。

### ⚠️ `validate_a` **不校验** `source_refs` 能否解析 —— 父代理必须自建字段级核验

`validate_a` 只查 schema/指纹/几何，`submit_screen` 才查 refs 解析。**不核验就会在提交时才炸**（或更糟：静默错 provenance）。
核验清单（本轮抓出 2 类真实缺陷）：

| 检查 | 本轮实测抓到的缺陷 |
|---|---|
| `reviewed_candidate` 的每个 ref 能在**本屏** pinned 基线 `candidate_targets` 里按 `id`+`source` 解析 | **跨屏候选 id 误用**：屏 420 的 b001–b015 引用了屏 **421** 的 id（29683–29697），本屏真实是 29628–29670，**常量偏移 42** |
| `visual_new` ⇒ `source_refs == []`；`reviewed_candidate` ⇒ 非空 | **origin 与 refs 自相矛盾**：屏 439 十三框写 `visual_new` 却带 refs |
| 16 键精确一致；`lease_id`/`generation`/`producer.app_id` == CLI；`guide_sha256`/`input_sha256`/`image_sha256`/尺寸 == 固定输入 | — |
| `box_id` 唯一且 `s<4位屏号>-b<3位>`；bbox 在图内；note 含中文；两两 IoU < 0.95；audit `coverage` 7 键 + `unresolved_items == []` | — |

**submit_screen 路径的 audit schema（实测固定，别再猜键名）**：顶层 5 键
`{screen_id, guide_sha256, unresolved_items, coverage, observation_notes}`（**无** `correction`——那是
`screen_patch` 路径才有）；`coverage` 的 7 键是
`{menus_titles, main_content, sidebar, status_bar, scroll_controls, images_and_inner_text, dialogs}`，
值取 `covered` / `not_applicable`。⚠️ 别用 `text_regions`/`icons` 之类的自造键名做断言——会得到整批假阳性。

**发现 refs 异常时的正确处置 = 几何核验后改判，不是删框**：算「紧致框是否落在所引基线粗框内」（容差 4px）。
本轮两次都是 **13–15/15 全包含的 1:1 对应** ⇒ 属于 id 写错，改 id（或改 origin）即恢复；只有在**找不到任何对应基线对象**时才退回 `visual_new`。

### ⚠️ 子代理的最终汇报**不可靠**，以磁盘产物为准

本轮第三段 3 个子代理全部返回 `Tool ran without output or errors`（空输出），但**产物已落盘**（8/9 屏齐全，缺 1 屏）。
⇒ 收到空汇报时**不要重跑整轮**：先 `find <任务目录> -name "screen-*.envelope.json"` 盘点，缺的屏另派 1 个子代理补做。

### ⚠️ 429 限流：**被拒的子代理仍可能跑成一部分**

实测（2026-10-06 16:05）：3 个子代理同时返回
`429 usage exceeds frequency limit ... Failed to execute task after subagent was created`。
但盘点后发现 **agent-a 已产出 1 屏、agent-b 已产出 1 屏**（envelope+audit+overlay+REPORT 齐全），agent-c 空手。
⇒ **收到 429 后必须盘点磁盘**，半成品可直接核验提交；不要直接判定「这一轮白跑」。

**首选取证：换 `model` 参数再派子代理**（2026-10-07 实测）。429 是**按模型池**计频 ⇒ 换模型即换池。
本轮 3 个默认模型子代理全部 429，但各自仍跑出 2 屏（**6/9 落盘**）；随后 `Agent(model="lite")` 派 1 个补做子代理
**一次成功**补齐剩余 3 屏（686/690/692），产物与默认模型同质量（validate_a + 字段级核验全通过）。
⇒ **优先试这条**，比父代理手标快得多；补做子代理的 prompt 要显式写明「只做缺的 N 屏、其余屏已由别人完成、不要重做」。

**换池也 429 时：等恢复后重试原模型**（2026-10-07 实测，第三轮）。本轮 3 个默认模型子代理返回
**空输出**（`Tool ran without output or errors`）但 8/9 屏已落盘；紧接着派 `model="lite"` 补做 718
却报 **429 整池耗尽**（提示次日才恢复）。**没有转父代理手标**，而是**等用户确认恢复后重试默认模型**，
一次成功（718 → 49 框，validate_a + 字段级核验全通过）。
⇒ 顺序是：**① 先盘点磁盘**（本轮 8/9 已落盘，只缺 1 屏）→ ② 换 `model` → ③ 换池也 429 就**等恢复再重试**，
而不是立刻退回手标。手标是最后手段，不是第二手段。
⚠️ 空输出的子代理**产物质量与正常无异**（本轮 8 屏全部一次通过父代理核验），别因空汇报就重跑整轮。

额度真恢复不了（或换池也 429）时，才**改用父代理手标**：

**父代理手标流程（已跑通）**
1. `lib_annotate.Screen(path)` 按**行带** `hblocks(x0,y0,x1,y1,thr,gap,min_w)` 吸附；深色主题用亮度掩膜分对象
   （绿底白字 `g>110`、白字绿底 `g>190`、深底浅字 `|g-40|>16`、低对比再降阈值）。
2. 写 `spec-XXXX.json`：`{"observation_notes":[...], "coverage":{...}, "boxes":[{"bbox":[..],"kind":"text|non_text","note":"...","origin":"visual_new|reviewed_candidate","candidate":{"id":N,"source":"..."}}]}`
3. 建信封（自动按 y/x 阅读序重排 `box_id`、写 envelope+audit、跑 validate_a）：
   `build_screen.py --screen N --spec spec-XXXX.json --batch <batch> --lease-id <L> --generation <G> --app-id <A> --worker-id <W>`
   （该工具来自 lead 工作目录 `tasks/b<batch>/lead/build_screen.py`，只需改文件头的 `WORKDIR`）
4. `overlay.py --envelope <env> --batch <batch> --scale 0.55` → Read 叠框图目视 → `submit_screen.py`。

**代价**：一屏约 8–12 次工具调用（含 1 次全图 Read + 4–6 次掩膜测量），远慢于子代理并行。仅在 429 时用。

### ⚠️ 租约过期后的恢复路径

`heartbeat.py` 返回 `{"ok": false, "error": "lease has expired"}` ⇒ 该租约作废（`status` 字段可能仍显示 `active`，
reaper 只在下次 `claim_range` 时清理）。恢复：

1. **用同一 app-id 重新 `claim_range`**（reaper 释放过期租约后，仍能领回同一段屏号）；
2. 把**已产信封**的 `lease_id` / `generation` / `producer.app_id` **改写为新租约**（否则 `submit_screen` 报
   `envelope provenance must match the CLI lease owner and generation`）；
3. 补齐缺屏后一并提交。

**⚠️ 三个实测陷阱（2026-10-06）**

1. **`heartbeat.py … >/dev/null && echo 已续租` 会骗你**：租约过期时它打印 `{"ok": false, "error": "lease has expired"}`
   但**退出码仍是 0**，`&&` 照常执行。**必须读返回 JSON 的 `ok` 字段**，不要只看退出码。
2. **租约（30 min）比一轮子代理（30–90 min）短 ⇒ 一轮必过期，这是常态不是例外**（2026-10-07 实测连续两批都撞）。
   ⇒ 两条对策，选一条：
   - **后台心跳守望**（推荐，app-sync22 实测有效）：起一个每 3–5 min 调一次 `heartbeat.py` 的后台循环，
     把 `ok` 写进 `heartbeat.log`，提交完成后再 `TaskStop`；
     **⚠️ `TaskStop` 只在同一会话内有效**（2026-10-07 实测）：会话中断/重启后后台任务句柄丢失，
     `TaskStop` 报 `No task found with ID`，而**循环仍在跑**（`ps -eo pid,ppid,command | grep heartbeat.py`
     可见 `PPID == 1` 的孤儿）⇒ 必须 `kill <PID>` 直接终止，然后 `ps` 复核。
     这与「僵尸租约」是**同一根因**：孤儿心跳会一直把 `expires_at` 推后。**每轮收尾必做**：
     `ps -eo pid,ppid,command | grep "heartbeat.py" | grep <自己的 app-id>` 应为空。
   - **或**子代理返回后**第一件事**就是 heartbeat + 读 `ok`；已过期就走「重领 → 改写信封租约字段 → **立即**提交」。
   ⚠️ 没做这两件事的代价（实测）：一轮 9 屏做完 5 屏时租约到期，**整段被别的会话领走**，
   且对方已自行产出同样几屏 ⇒ 我的产物全成废件。**一轮的时长要按租约窗口排**（宁可一轮 6 屏也不要 9 屏）。
3. **不要假设自己的 claim 还在**：租约过期后别的 worker 会接管你的屏并可能已经提交完成。
   ⇒ 提交前先看 `status`：若目标屏已 `completed` 且内容不同，`submit_screen` 会拒（`already committed with different content`），别白跑。

### ⚠️⚠️ 僵尸租约：**永远不会过期**的那种（2026-10-07 实证，与上一节完全不同）

上一节是「租约自然过期」。**更隐蔽的一类**是：会话 agent 早已死掉，但它的**后台心跳守望循环没死**
（父 shell 退出后循环被 reparent 到 `PPID=1`），于是 `expires_at` 被**每 3 min 一直推后**
⇒ `_reap_expired_leases` **只看 `expires_at`**，**永远回收不了**，该段屏被无限期占用。
（实测：`app-sync23` 屏 660–665，最后产物 12:47，到 15:33 仍被「占用」，心跳却一直 `ok:true`。）

**识别（三条同中即僵尸）**：

1. **任务目录里非 `heartbeat*` 文件的最新 mtime** 远早于现在（实测 >2h 无任何产物）；
2. `ps aux | grep "[a]pp-<id>"` 找心跳进程：命令行是 `bash -c for i in $(seq 1 N); do … heartbeat.py …`，
   **`PPID == 1`（孤儿）** ⇒ 父 agent shell 已死；
3. 该租约 `last_heartbeat` 是**几十秒前**（循环刚续过），`expires_at` 还在未来 —— 这就是「永不过期」的假活。

⚠️ 只看 `heartbeat.py` 返回 `ok:true` **会骗你**（那是循环打的，不是 agent 打的）；
`supervisor-report.md` 的「疑似弃权（心跳 > 600s 未续）」**也抓不到它**（因为心跳一直没停）。

**处置（本轮跑通；关键是「不手写释放逻辑」，只校正 `expires_at` 后交给官方 reaper）**：

```bash
# ① 停掉孤儿心跳（否则一切白做）
kill <孤儿心跳 PID>            # 停完 ps 复核：不应再有该 app-id 的循环
# ② 在 A 仓写锁内把该租约 expires_at 校正为过去（只改这一个字段，不碰 screens）
cd ~/.cache/macim-review-p1/c-pilot-a-data && $PY - <<'EOF'
import sys, datetime
sys.path.insert(0, "tools")
import claim_range as cr
from repo_transaction import locked_repo, atomic_write_json
A = "/Users/dengdeng/.cache/macim-review-p1/c-pilot-a-data"
STATE = "<训练仓>/reports/visual_regions/c-pilot/local-state.json"
now = cr._utc_now()
with locked_repo(A):                                  # 必须持锁，别的会话也在写
    st = cr._read_state(STATE)
    _, leases, _ = cr._ensure_control_maps(st)
    for lid, l in leases.items():
        if isinstance(l, dict) and l.get("app_id") == "<僵尸 app-id>" and l.get("status") == "active":
            l["expires_at"] = cr._format_time(now - datetime.timedelta(minutes=1))
            l["stale_repair"] = {"at": cr._format_time(now), "by": "<我的 app-id>", "reason": "zombie: orphan heartbeat loop"}
    st["updated_at"] = cr._format_time(now)
    atomic_write_json(STATE, st, sort_keys=False)     # 复刻工具写盘格式（ensure_ascii=False, indent=2, 末尾换行）
EOF
# ③ 正常领取：官方 reaper 会正规回收（标记 expired + 释放屏为 not_started）并立刻领回
$PY tools/claim_range.py --app-id <我的 app-id> --size 9 --state "$STATE" --repo "$A"
```

**复用对方产物**：领回后若对方**磁盘上已有 envelope**（本例 660/661/662），只改写
`lease_id` / `generation` / `producer.app_id`，`worker_id` 写 `takeover(<原 app-id>/<原 worker>)`，
**不要重做**；缺的屏再派子代理。提交前务必跑一遍字段级核验（对方信封的 `source_refs` 可能引用别屏 id）。

**留痕**：按生态约定在批次根目录写 `TAKEOVER-<屏段>-<我的 app-id>.md`
（领取时间 / 缘由 / 复用了谁的信封 / 废弃件 / 提交哈希清单 / 给原会话的提醒）。

### `_supervisor/`：动手前先读它

`~/.cache/macim-review-p1/batch2/tasks/_supervisor/`（由 launchd 定时巡检，非 A 仓内容）：

| 文件 | 内容 |
|---|---|
| `KICK.md` | **续跑提示**：当前可领取的屏号列表 + 建议动作（`worker_resume.py --app-id <id> --dir <dir> --heartbeat`） |
| `supervisor-report.md` | 租约巡检（含「心跳 > 600s 未续但未到期」的**僵尸租约**清单）、空白屏列表、published GT 快照回滚方法、已知机制说明 |
| `launchd.out.log` | 巡检历史输出 |

⇒ **每轮开工前先读 `KICK.md` 与 `supervisor-report.md`**：能直接看到「谁已成僵尸、哪些屏可领」，
比自己去遍历 `local-state.json` 快得多。
⚠️ **但它抓不到「孤儿心跳循环」型僵尸**（那种 `last_heartbeat` 一直新鲜、`expires_at` 一直被推后，
既不在「疑似弃权」清单里、也不会被惰性 reaper 释放）—— 见上一节「僵尸租约」的识别三步，
**必须自己按任务目录 mtime + `PPID=1` 心跳进程去查**。
（`supervisor-report.md` 的「已知机制」也承认：reaper **只看 `expires_at`，不看 `last_heartbeat`**，
该缺口需 owner 批准才改代码。）

### 空控件「保不保留外框」的判据（本轮裁定，owner 待复核）

- **内部有可框内容**（哪怕只有一个箭头）⇒ **不框外边界**，只框内部内容（GUIDE §1.13①「下拉框 = 2 框（文字 + 箭头，不含外框）」+ 坑 P11）。
- **内部无任何可框内容**（真空搜索框/空输入框）⇒ **保留可见轮廓**（GUIDE §1.13②）。
- 判据是**内部有没有内容**，不是「是不是下拉框」。

### 行内蓝色短语 = 行内代码块还是 Inline Link（先例，别猜）

设置页说明行里的蓝色短语（`atom` / `hidden` / `apm`）是**行内代码块** ⇒ **整行一个 text 框、不拆**。
先例：已提交屏 **212 `b012`**「含行内代码块 atom，按先例保留行内」、屏 274/280/285/316 的
「…calling the apm command-line tool.」整行一框。
（与 GUIDE 2026-10-04「Packages list 类蓝色短语是 Inline Link」**不是同一类**——后者有 owner 的交互证据。）

### ⚠️ Atom 帮助区列表项的**行首圆点 `•` 必须单独成 `non_text` 框**（owner 2026-10-08 裁定）

「For help, please visit」下的三条项目符号列表（`• The Atom docs …` / `• The Atom forum at Github Discussions` /
`• The Atom org. …`）：**圆点 `•` 是独立的非文字视觉对象，单独成框、`visual_kind="non_text"`；
列表项正文 text 框从文字起算（不含圆点）**。正文再按 v0.16「内联链接独立成框」可继续拆为
链接前 / Link / 链接后。

**先例（已落地）**：屏 **3**（2026-10-08 08:01）、屏 **32**（08:02）、屏 **458**（08:19）。

**几何常量（scale = 1.0，屏 32 实测；`scale = 锚框宽/141`，锚 = 注记含 `For help, please visit` 的框）**：
圆点 `x1 = 锚.x1 + 12.9px`、圆点 **5.4×5.4px**、正文 `x1 = 锚.x1 + 30.1px`、圆点↔正文间隙 ≈ **11.6px**、行距 ≈ **21.2px**。

**判定（判「圆点是否已被框住」）**：
```python
# 行 y 带 = 该行 text 框 y1..y2（±2）；窗口 x ∈ [锚.x1-7, 锚.x1+62*scale]
bg = median(窗口左缘 4 列 + 顶 2 行)          # ⚠️ 见下「明暗混排」
prof = (abs(crop - bg) > 30).sum(axis=0)      # 列墨迹剖面
rs = 墨迹游程(prof)
圆点 = rs[0] if (宽 ≤ 10*scale 且 与 rs[1] 的间隙 ≥ 4*scale) else None
并入 = (text框.x1 <= 圆点.x2 + 1)             # True ⇒ 圆点被并进 text 框（需拆出）
```

**三个必踩的坑**：

1. **本批截图明暗混排**：同一帮助区，屏 **118 是浅底**（bg≈243、墨迹 66），
   屏 **67/143/158 是深底**（bg≈37、墨迹 ≈155）。**必须用 `|px − bg|` + 相对底色阈值**；
   写成「深字浅底」的 `(bg-px)>thr` 会让全部深底屏静默返回「无圆点」（实测第一版脚本因此漏判 30 屏）。
2. **注记措辞是强信号但不是全集**：A 仓 30 屏注记明写「**含行首圆点**」/「行首圆点+The」，
   与几何判定逐屏一致；但 **67 / 120 / 426 / 431 / 455 / 456 的注记完全没提圆点**。
   ⇒ **不得只凭注记措辞出清单**，必须做图像测量。
3. **认屏用多尺度 NCC 时阈值要按断崖取**：以屏 32 帮助块（500×117）为模板、scale 0.75–1.25 步长 0.05
   扫全 458 Atom 屏，真命中 **≥0.576**、次高仅 **0.471** —— 取 0.5 即可。
   **低分段（0.41–0.47）全是 Atom 设置页的普通文本块**（274/212/46/112/178/128/307/94…），
   必须抽查排除，别把 0.7 的假阳性（实测屏 33 = 0.742 空白区）当真。

**2026-10-08 全量排查结论（Atom 458 屏；**判据源 = `published-visual-v1/annotations.json`**）**：

| 类别 | 屏数 | 屏号 |
|---|---|---|
| A 已合规（圆点已是 `non_text`） | 5 | 3, 32, 455, 456, 458 |
| **B 圆点被并进 text 框（需拆）** | **31** | 67, 118, 143, 147, 158, 168, 171, 193, 194, 195, 213, 241, 245, 255, 257, 279, 291, 296, 305, 317, 324, 345, 349, 354, 361, 377, 379, 406, 414, 434, 439 |
| **C 圆点在图上但完全未标注（需补框）** | **4** | 21, 120, 426, 431 |

⚠️ **「是否已合规」必须以 `published-visual-v1/annotations.json` 为准，不能用 A 仓信封**：
实测屏 455 / 456 的圆点框**只在 published**、A 仓信封没有（owner 2026-10-08 16:00/16:12 改、16:35 发布）
⇒ 拿 A 仓判会得出**过期结论**（第一版报告就因此把 455/456 误报为「漏标」）。
A 仓只用来取**注记文本**与交叉核对。

⚠️ **这 40 屏在工作台全部有 owner 真实草稿**（`已裁定` + `reviewedByOwner=true` + `sourceKind=human_new`）
⇒ `screen_patch` 的 `draft_is_pure_materialization` 三条判据缺一即**不清草稿**，
**只做 A 仓 patch 不会改变工作台显示（落地空转）**。动手前先定落地目标（草稿/发布 还是 A 仓，或两者）。

**已知连带**：① A 仓 `ANNOTATION_GUIDE.md` **不能改**（改它会让全部既有信封的 `guide_sha256` 失效）⇒
本规则只能落训练仓 `docs/visual_region_annotation_spec.md`（v0.17）与本技能；
② 屏 **255 / 354** bbox 与注记逐条相同，疑为近重复，改一屏须同步另一屏；
③ 屏 **255 / 354** 只可见第 3 条列表项、**361** 的「For help」行被语言对话框遮挡 ⇒ 无锚框，
按注记 + 同模板几何同构 + 目视裁图判定；
④ **C 类不是「并框」而是「漏标非文字对象」**，与 B 类不是同一种缺陷，处置口径须 owner 明确；
⑤ 完整报告：训练仓 `reports/visual_regions/c-pilot/help-list-bullet-scan.md`（+ `-evidence.png` 逐屏裁图）。

### 存疑小框用 **RGB 相对底色**核验，不要靠目视

```python
r = np.asarray(Image.open(path).convert('RGB')).astype(int)[y1:y2, x1:x2]
# 与紧邻外环底色比：最大差 > ~20 且通道差明显 ⇒ 真对象；最大差 ≈ 0 ⇒ 幽灵框
```
本轮实例：427 标签栏 9×9「圆形标记」实为蓝色圆点（最亮 `[29,42,68]`，通道差 24）⇒ 真；425 最小化 glyph 仅 10×1px
但压在浅色标题栏（Δ−241）⇒ 真。**⚠️ 深色主题屏不能用 `亮度>150` 做 ASCII 目视**（会全黑 ⇒ 误判「什么都没有」）。

### 读图协议 v2：OOM 防护 + 流量防护 + audit atlas（必写进 BRIEF；2026-10-07 两轮 ChatGPT 复核后定稿）

历史事故与实测：单会话大量 Read 大 PNG ⇒ V8 OOM 崩溃丢进度；**图片 base64 进上下文后每一轮 API 请求都全量重传**
（实测单 agent 进程 45 min 上行 243 MB=含空闲的累计均值，活跃期瞬时 ↑0.33 MB/s——**两个指标必须分开命名记录，
不得混用**）。以下做法 27 屏 0 OOM，v2 再叠加流量防护：

**总原则：量用原图、看用缩图、小目标/细结构裁原图 ROI。测量精度不受降采样影响（量测永远跑原图）；
降采样只作用于「给模型目视复核的副本」。**

1. **父代理全程不读 PNG**（只做数值核验 + 提交）；图像阅读全部交给子代理。
2. **自适应 overview**（正常路径每屏 1 次）：
   `desired_scale = min(1, 8 / H_p10)`；`desired_long = 源图长边 × desired_scale`；
   `overview_long = min(源图长边, clamp(desired_long, 1280, 1600))`；`overview_scale = overview_long / 源图长边`。
   **H_p10 只从本屏 text 候选的紧致墨迹高度计算**（单视觉行优先，**不得混入 non_text/图标/分隔线/多行块**）；
   text 样本 ≥10 个算 P10，3–9 个取最小 3 个的中位数，**<3 个或无可靠 text 高度时退化为固定长边 1600**。
   若 clamp 后 `H_p10 × overview_scale < 8px`，不得声称满足保真目标——对应小字对象**自动加入 ROI 名单**。
   LANCZOS 重采样；**先缩图、再把 bbox 按比例映射后画框**（不要先画框再缩，否则 1px 偏移会被框线+插值
   「焊」到目标边缘）。overview 只判：漏大块、框错对象、明显重复/合并、整体布局；**禁止**用 overview
   下「紧致度 PASS」结论。
3. **风险触发原图 ROI**（不是「bbox <20px」——判定依据的尺度 ≠ bbox 尺度，大框上的 1–3px 细结构同样危险，
   如 200×1 横线、大按钮 1px 边框）。满足任一条件即出 ROI：
   ① 最细结构 ≤2–3px——「最细结构」可来自任一证据：类别先验（separator/border/glyph）、连通域局部最小笔画宽、
   边缘 run-length、已知元数据 borderWidth；无法可靠估计时**保守按命中处理**并标 uncertain；
   ② 低对比——统一定义：原图 sRGB 上取候选墨迹像素中位亮度 Y_fg 与 bbox 外背景环（3px）中位 Y_bg，
   `ΔY = |median(Y_fg) − median(Y_bg)| < 10` 仅作风险 trigger，**不作「对象不存在」的依据**；
   ③ bbox 边缘外扩窗口测出墨迹越界/负留白异常；④ 相邻框间隙 <4px；
   ⑤ text/non_text 靠形态判定的对象（单字符按钮、SF Symbols、省略号图标——低分辨率下类别会翻转）；
   ⑥ 极端长宽比；⑦ 贴图像边缘；⑧ 测量置信度低或 REPORT 标记 uncertain。
   ROI 从**未画框原图**裁，放大用 **NEAREST ×2**（NEAREST 只复制源像素、不增加信息，作用是让像素级结构
   可观察；LANCZOS 版可另附作读字辅助，但 raw 版才是几何证据）；框线画在**外偏 1–2px** 或用角点 tick，
   不得覆盖被检像素。语义存疑的 ROI 带上下文（外扩 `max(8px, 0.5×目标高)`）。
4. **audit atlas + tile manifest**：把 overview + boundary strip（bbox 四边内外各 4px 条带，专查 ±1px
   紧致度/越界/合并）+ 高风险 ROI 拼成一张图。**atlas 必须生成机器可读 sidecar manifest**：
   `{"tile_id":"R037:right","region_id":"R037","kind":"boundary_strip","edge":"right",
     "source_rect":[...],"source_bbox":[...],"display_scale":2}`，图上只标注短 ID（如 `R037:R`），
   **文字标签放 tile 外**，不得污染被审计像素。
   **atlas 总像素预算**：strip 总面积随 bbox 周长总和膨胀，超预算时优先保留风险 ROI、strip 紧密 packing、
   必要时拆 atlas A/B（第二次 Read 记录原因 `atlas_pixel_budget_split`），**不得缩小 native strip**。
   **坐标 round-trip 是程序 Gate，不是抽查**：对每个 overview bbox 做 source→preview→source 四边回投，
   误差 ≤1 源像素；对每个 tile 校验 `source_rect/tile_rect/scale` 解析一致；并测四角极值点
   `(0,0),(W-1,0),(0,H-1),(W-1,H-1)`。人工抽查仅作 sanity check，不替代程序检查。
5. **Read 预算**：正常路径**每屏 1 次** atlas Read；首次视觉复核**新发现事前无法机械预测的疑点**时
   （漏框、text/icon 翻转、未命中 trigger 的视觉异常），允许生成 targeted ROI 追加 1 次 Read，
   **必须在 REPORT 记录原因**；不得为方便常态化用第二次 Read。
6. **增强图（锐化/CLAHE/拉对比）只能作并排辅助，不得单独决定 bbox 或 text/non_text**。
7. **单屏落盘与汇报不变**：测量脚本只 print 汇总 bbox，绝不 print 像素矩阵；每屏立刻落盘 envelope+audit
   再进下一屏；每屏完成追加一行 REPORT。
8. **会话滚动**：子代理完成即退出；同一 agent 会话满足任一条件即换新会话，从 REPORT/manifest 恢复状态：
   ① 含图会话 ≥6–9 屏；② 估算保留图片 payload ≥20 MB（口径=**进入对话历史的实际编码后图像 payload**，
   客户端取不到时按发送文件字节 ×4/3 估 base64；与 V8 heap/OOM 不是同一指标）；③ 内部 context/heap 安全水位。
   这条的作用：在每轮近似重传全部累计历史、每轮新增量近似恒定时，切断累计上传量随轮数的近似二次增长。
   6–9 屏/20 MB 是**事故数据驱动的 operational limit**，不是图像处理常数，后续批次实测后调整。
9. 汇报里若子代理自曝超了 Read 预算、用了增强图定框或二次 Read，记入该屏 audit `observation_notes`。

## 硬约束

- 禁 `git push`；禁改 `ANNOTATION_GUIDE.md`（会让全部既有信封的 `guide_sha256` 失效）。
- 禁改 A 仓既有文件（`screens/`、`audit/`、`batches/`、`qc/`、`previews/`、`inputs/`）——只能经 `screen_patch` 落。
- 禁碰工作台 `drafts-visual-v1/` 与候选文件（除 `screen_patch` 内部流程）。
- **读图失败（Read 返回「不支持图像 / Content filtered」）时禁止描述图面内容**，改用数据核查并明说「我没看到图」。
- A 仓常有其他 agent 并发提交，只读不写，遇 git 报错重试。
