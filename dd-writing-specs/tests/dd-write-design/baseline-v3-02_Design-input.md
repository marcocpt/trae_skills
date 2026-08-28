> 最后更新：2026-06-30 | 版本：v1.2
> 文档状态：已批准

# F3.2 模板匹配 Design

## 模块划分

- TemplateMatcher：负责模板加载、匹配执行；
- MatchReporter：负责结果聚合与输出；
- BatchRunner：负责批量任务调度。

## 职责边界

TemplateMatcher 不写文件；MatchReporter 不执行匹配；BatchRunner 不解析模板内容。

## 数据流

输入图像与模板 → TemplateMatcher → 原始匹配结果 → MatchReporter → 报告文件。

## 状态变化

BatchRunner 任务状态：pending → running → done / failed。

## 协作关系

BatchRunner 调度 TemplateMatcher，TemplateMatcher 输出交给 MatchReporter。

## 版本记录

- v1.2：MatchReporter 增加聚合去重职责
- v1.1：BatchRunner 增加 failed 状态语义
- v1.0：初版
