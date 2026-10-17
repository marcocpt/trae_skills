# Feature Specification

只在Specification阶段读取。文档组织与change_tier风险档无关，两档默认均使用项目已有任务专属持久入口，不新增mini_spec_path字段。

## 最小任务包

复用目标/范围、必要设计决定、可验证验收条件与任务安排；必要时调用dd-writing-specs的child轻量路径，继承父入口和已有批准依据。不要复制另一份看板。批准遵循artifact-source-and-packet：复用仍有效的用户指令/决定，未决或变化的实质语义先确认；仅整理文件不重问。

## 需要独立文档时

明确消费者只补其所需的合同。用户或项目明确要求完整套件时，调用dd-writing-specs作为child，明确选择full文档路径并复用父入口；没有新增共享状态字段。Requirements/Design/Visual（有UI时）/Test Matrix按依赖产出，不因完整套件自动要求逐篇确认；用户或项目明确逐篇时才逐篇。自检与未解决产品决定仍必须处理。

## Gate

目标、范围、验收条件和关键决定明确且有有效批准依据；保存到既有规格路径/批准记录与source_manifest属主，不再维护批准镜像。旧批准记录兼容保留，不能删除唯一依据。完整质量控制由change_tier及review-gate决定，不以任务包文件数替代。仅按已有授权交付Git。随后更新current_stage=planning。
