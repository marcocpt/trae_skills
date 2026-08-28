> 拆分来源：`artifact-contract.md` §4。唯一属主：验证证据 compact plan+result 与四个不变量只在此维护。

# Artifact Verification

仅在创建或消费验证证据时读取。来源/执行包与生命周期见对应分文件。

## 4. 验证证据（compact：`plan` + `result`，保留四个不变量）

verification 只存两块：`plan` 与 `result`。但 `coverage`、`run`、`bindings`、`validity` 四个语义**必须**存在；`validity` 每次都验证，不只异常时记录。

```yaml
verification:
  plan:
    requirement_refs: [AC-001]
    checks:
      - id: CHECK-001
        command: exact-command-or-manual-step
        oracle: exact-pass-condition
  result:
    coverage:
      AC-001: covered
    runs:
      - check_id: CHECK-001
        outcome: PASS
        evidence_ref: repository-relative-evidence
    bindings:
      source_manifest_digest: sha256:current-manifest
      implementation_digest: git-or-file-digest
      environment: recorded-environment-id
    validity: valid
```

| 字段 | 记录 | 不能推出 |
|---|---|---|
| `plan` | 计划检查、oracle、预期、requirement refs | 已覆盖或已通过 |
| `result.coverage` | 指定来源版本的 AC／路径覆盖 | 本次运行通过 |
| `result.runs` | 本次命令／步骤、`PASS | FAIL | NOT_RUN`、证据位置 | 后续版本仍有效 |
| `result.bindings` | source_manifest_digest、implementation_digest、environment | — |
| `result.validity` | `valid | stale | unreadable | unverified` | 未运行也可 PASS |

Gate 规则：必需 coverage 无 `partial|missing|unverified`；必需 run 全部 `PASS`；bindings 与当前输入一致；`validity` 必须为 `valid`。非 `valid` 时才追加 `validity_exception`，但 exception 不能替代 validity 检查——即使 run 全 PASS、无 exception，只要 candidate SHA 与 evidence binding 不一致，也必须判 `stale`。

`coverage` 只取 `covered`（完整）、`partial`（部分）、`missing`（缺失）、`deferred`（已批准延后，含负责人／触发条件）、`unverified`（无法核对，设 blocker）。测试存在或 `covered` 都不等于运行通过。只有必需 `run=PASS`、`validity=valid`、AC／失败路径无缺口且 blocker 为零，Gate 才能 `PASS`。

计划写规范；覆盖快照、运行结果、审查发现和进度写既有状态／证据记录，不回填冻结合同。旧的 `verification_plan`／`existing_coverage`／`run_result`／`evidence_validity` 四层并列字段不再作为现行合同。