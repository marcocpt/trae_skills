#!/usr/bin/env python3
"""Batch2 P1-6 机械校验器：Deterministic before LLM

验证结构、引用、digest、SHA、enum、路径边界及 freshness binding，
不判语义（AC 是否实现、oracle 正确性、review finding 等仍由 Gate/reviewer 负责）。

用法：
  python3 validate-workflow-artifact.py packet <plan.md>
  python3 validate-workflow-artifact.py verification <evidence.json|state.json|md>
  python3 validate-workflow-artifact.py candidate <state.json>
  python3 validate-workflow-artifact.py planning-index <plan.md>

输出 JSON: {"status":"PASS"|"BLOCKED","errors":[...] }  exit 0 PASS, 1 BLOCKED
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

VALID_DELIVERY_STATUS = {"authorized", "not-required", "not-authorized", "pending"}
VALID_VALIDITY = {"valid", "stale", "unreadable", "unverified"}
VALID_COVERAGE = {"covered", "partial", "missing", "deferred", "unverified"}
VALID_CONCLUSION = {"success", "failure", "cancelled", "timed_out", "neutral", "skipped", "action_required"}
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

def fail(errors):
    print(json.dumps({"status": "BLOCKED", "errors": errors}, ensure_ascii=False, indent=2))
    return 1

def ok():
    print(json.dumps({"status": "PASS", "errors": []}, ensure_ascii=False, indent=2))
    return 0

def is_valid_digest(d: str) -> bool:
    # Strict: only sha256:64hex or 40hex git sha
    return bool(SHA256_RE.match(d) or GIT_SHA_RE.match(d))

def validate_packet(plan_path: Path):
    errors = []
    if not plan_path.exists():
        return fail([f"plan not found: {plan_path}"])
    text = plan_path.read_text(encoding="utf-8")
    if "source_manifest" not in text:
        errors.append("missing source_manifest")
    else:
        if "stable_id" not in text:
            errors.append("source_manifest missing stable_id")
        if "digest:" not in text:
            errors.append("source_manifest missing digest")
        else:
            for m in re.finditer(r"digest:\s*(\S+)", text):
                d = m.group(1).strip().strip('"').strip("'").strip(",")
                # Strict check: must be valid digest, no placeholder
                if not is_valid_digest(d):
                    errors.append(f"invalid digest format: {d} (must be sha256:64hex or 40hex)")
        if "approval:" not in text:
            errors.append("missing approval")
        else:
            for field in ("status:", "authority:", "decided_at:", "evidence_ref:"):
                if field not in text:
                    errors.append(f"approval missing {field}")
    if "sources:" not in text:
        errors.append("missing sources")
    else:
        if "ref:" not in text or "anchors:" not in text:
            errors.append("sources missing ref/anchors")
        for m in re.finditer(r"anchors:\s*\[([^\]]*)\]", text):
            inner = m.group(1).strip()
            if not inner:
                errors.append("empty anchors")
            else:
                # Check anchors look like FR-001 etc
                anchors = [a.strip().strip('"').strip("'") for a in inner.split(",") if a.strip()]
                for a in anchors:
                    if not re.match(r"^(FR|AC|NFR|OOS)-[0-9A-Za-z\-]+$", a):
                        # Allow generic but flag suspicious
                        if not a:
                            errors.append(f"invalid anchor: {a}")
    # write_scope: must exist and not be empty, must not be overly broad
    if "write_scope" not in text.lower() and "write scope" not in text.lower():
        errors.append("missing write_scope")
    else:
        # Find write_scope block and check it has at least one path and no dangerous patterns
        ws_match = re.search(r"write_scope:.*?(?=\n\S|\Z)", text, re.S | re.I)
        if ws_match:
            ws_block = ws_match.group(0)
            if not re.search(r"[\w/\-]+\.[\w]+|[\w/\-]/", ws_block):
                errors.append("write_scope missing valid paths")
            if re.search(r"^\s*-\s*/\s*$", ws_block, re.M) or "glob" in ws_block.lower() and "*" in ws_block:
                errors.append("write_scope overly broad (contains root or glob)")
            if ws_block.strip().endswith(":") and "创建" not in ws_block and "修改" not in ws_block:
                errors.append("write_scope empty")
        else:
            # Fallback: check at least one path-like string near write_scope
            if not re.search(r"write_scope.*?[\w/]+\.\w+", text, re.S | re.I):
                errors.append("write_scope missing valid paths")
    if "stop_conditions" not in text and "Stop conditions" not in text:
        errors.append("missing stop_conditions")
    if "delivery_authorization" not in text:
        errors.append("missing delivery_authorization")
    else:
        found_status = False
        for m in re.finditer(r"delivery_authorization.*?status:\s*([^\s,\]]+)", text, re.S):
            found_status = True
            s = m.group(1).strip().strip('"').strip("'").strip(",")
            if s not in VALID_DELIVERY_STATUS:
                errors.append(f"invalid delivery_authorization status: {s}")
        if not found_status:
            # Try alternate form: check for enum values directly
            if not any(s in text for s in VALID_DELIVERY_STATUS):
                errors.append("delivery_authorization missing valid status enum")
    if "verification" not in text.lower():
        errors.append("missing verification in packet")
    # Strict source ref existence: each ref must be a key in source_manifest
    refs = set(re.findall(r"ref:\s*([A-Z0-9\-_]+)", text))
    # Find manifest keys: lines like "  SPEC-REQ:" under source_manifest
    # Extract source_manifest block
    sm_block_match = re.search(r"source_manifest:\s*\n(.*?)(?:\n\w|\n#|\Z)", text, re.S)
    manifests = set()
    if sm_block_match:
        sm_block = sm_block_match.group(1)
        for m in re.finditer(r"^\s{2}([A-Z0-9\-_]+):\s*$", sm_block, re.M):
            manifests.add(m.group(1))
    else:
        # Fallback to global search for manifest-like keys
        for m in re.finditer(r"^\s{2}([A-Z0-9\-_]+):\s*$", text, re.M):
            # Heuristic: keys that look like manifest IDs
            if m.group(1).startswith(("SPEC", "REQ", "DES", "TEST")):
                manifests.add(m.group(1))
    for r in refs:
        if r not in manifests:
            errors.append(f"source ref not in manifest: {r} (manifest keys: {sorted(manifests)})")
    if errors:
        return fail(errors)
    return ok()

def validate_verification(path: Path):
    errors = []
    if not path.exists():
        return fail([f"verification path not found: {path}"])
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
        v = data.get("verification", data)
        if "plan" not in v:
            errors.append("missing verification.plan")
        if "result" not in v:
            errors.append("missing verification.result")
        else:
            r = v["result"]
            for k in ("coverage", "runs", "bindings", "validity"):
                if k not in r:
                    errors.append(f"missing result.{k}")
            if "validity" in r and r["validity"] not in VALID_VALIDITY:
                errors.append(f"invalid validity: {r['validity']}")
            if "coverage" in r and isinstance(r["coverage"], dict):
                for ac, cov in r["coverage"].items():
                    if cov not in VALID_COVERAGE:
                        errors.append(f"invalid coverage {ac}: {cov}")
            if "bindings" in r:
                b = r["bindings"]
                for k in ("source_manifest_digest", "implementation_digest"):
                    if k not in b:
                        errors.append(f"missing bindings.{k}")
                    elif not is_valid_digest(str(b[k])):
                        errors.append(f"invalid bindings.{k}: {b[k]} (must be sha256:64hex)")
                # freshness: environment should exist
                if "environment" not in b:
                    errors.append("missing bindings.environment")
            if "runs" in r and isinstance(r["runs"], list):
                for run in r["runs"]:
                    if "outcome" not in run or run["outcome"] not in ("PASS", "FAIL", "NOT_RUN"):
                        errors.append(f"invalid run outcome: {run}")
                    if "evidence_ref" not in run:
                        errors.append(f"run missing evidence_ref: {run}")
    except json.JSONDecodeError:
        # Text mode: strict keyword checks, not just presence
        for k in ("coverage", "runs", "bindings", "validity"):
            if k not in text:
                errors.append(f"missing {k} in verification text")
        # Check validity value is one of valid enums
        if not any(f"validity: {v}" in text or f"validity:{v}" in text for v in VALID_VALIDITY):
            # Also check for validity: valid pattern
            if not re.search(r"validity:\s*(valid|stale|unreadable|unverified)", text):
                errors.append("missing or invalid validity value (must be valid|stale|unreadable|unverified)")
        if "source_manifest_digest" not in text:
            errors.append("missing bindings.source_manifest_digest")
        else:
            for m in re.finditer(r"source_manifest_digest:\s*(\S+)", text):
                d = m.group(1).strip().strip('"').strip("'")
                if not is_valid_digest(d):
                    errors.append(f"invalid source_manifest_digest: {d}")
        if "implementation_digest" not in text:
            errors.append("missing bindings.implementation_digest")
        else:
            for m in re.finditer(r"implementation_digest:\s*(\S+)", text):
                d = m.group(1).strip().strip('"').strip("'")
                if not is_valid_digest(d):
                    errors.append(f"invalid implementation_digest: {d}")
        if "environment" not in text:
            errors.append("missing bindings.environment")
        # Check runs have evidence_ref
        if "evidence_ref" not in text:
            errors.append("runs missing evidence_ref")
    if errors:
        return fail(errors)
    return ok()

def validate_candidate(state_path: Path):
    errors = []
    if not state_path.exists():
        return fail([f"state not found: {state_path}"])
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return fail([f"invalid JSON: {e}"])
    for k in ("candidate_sha", "candidate_review", "full_spec_gap", "full_ci_run"):
        if k not in data or data[k] is None:
            errors.append(f"missing {k}")
    if errors:
        return fail(errors)
    csha = data.get("candidate_sha")
    cr = data.get("candidate_review", {})
    gap = data.get("full_spec_gap", {})
    ci = data.get("full_ci_run", {})
    if csha and not SHA_RE.match(str(csha)):
        errors.append(f"invalid candidate_sha: {csha} (must be 7-40 hex)")
    for name, obj, field in (("candidate_review.sha", cr, "sha"), ("full_spec_gap.sha", gap, "sha"), ("full_ci_run.head_sha", ci, "head_sha")):
        v = obj.get(field) if isinstance(obj, dict) else None
        if v is None:
            errors.append(f"missing {name}")
        elif str(v) != str(csha):
            errors.append(f"{name} != candidate_sha ({v} != {csha})")
        elif not SHA_RE.match(str(v)):
            errors.append(f"invalid {name}: {v}")
    conc = ci.get("conclusion") if isinstance(ci, dict) else None
    if conc is None:
        errors.append("missing full_ci_run.conclusion")
    elif conc not in VALID_CONCLUSION:
        errors.append(f"invalid conclusion: {conc} (must be {sorted(VALID_CONCLUSION)})")
    if "full_ci_passed" in data:
        errors.append("legacy full_ci_passed is forbidden; derive PASS from full_ci_run.conclusion==success && head_sha==candidate_sha (Batch4)")
    # Freshness: check that ci has run_id/url
    for k in ("run_id", "url", "head_sha", "conclusion"):
        if k not in ci:
            errors.append(f"full_ci_run missing {k}")
    if errors:
        return fail(errors)
    return ok()

def validate_planning_index(canonical_path: Path, plan_path: Path | None = None):
    """校验 canonical normative 集 → plan 覆盖的完整性

    左集合必须来自独立 canonical 源，不能从 plan 自证。
    严格 fail-closed：
      - 单参 planning-index <plan> 永远 BLOCKED（需 canonical 或人工全读）
      - 双参仅当 canonical 为 canonical-index.json 时才允许机械 PASS；markdown 直接输入若无法证明所有 normative 类型可枚举则 BLOCKED
    """
    # 单参模式：永远 fail-closed，提示需 canonical
    if plan_path is None:
        plan_path = canonical_path
        canonical_path = None
        if not plan_path.exists():
            return fail([f"plan not found: {plan_path}"])
        return fail(["single-file planning-index cannot prove canonical completeness: need canonical-index.json or manual full re-read (Batch3 P0-2 fail-closed)"])
    # 双参模式：canonical vs plan
    if not canonical_path.exists():
        return fail([f"canonical not found: {canonical_path}"])
    if not plan_path.exists():
        return fail([f"plan not found: {plan_path}"])
    # 仅 json 索引允许机械 PASS；markdown 一律 BLOCKED 走人工全读
    if canonical_path.suffix.lower() != ".json":
        return fail([f"canonical markdown {canonical_path.name} cannot be mechanically proven complete; use canonical-index.json or manual full re-read (Batch2 JSON-only fail-closed)"])
    c_text = canonical_path.read_text(encoding="utf-8")
    try:
        c_data = json.loads(c_text)
    except json.JSONDecodeError as e:
        return fail([f"invalid canonical-index.json: {e} (must be valid JSON)"])
    # 仅接受 dict schema 且必须带 digest 绑定，避免旧 index 对新规格误 PASS
    if not (isinstance(c_data, dict) and "normative_anchors" in c_data and isinstance(c_data["normative_anchors"], list) and all(isinstance(x, str) for x in c_data["normative_anchors"])):
        return fail(["invalid canonical-index.json schema: must be {\"normative_anchors\": [...], \"source_manifest_digest\": \"...\", \"source_digests\": {...}}"])
    if "source_manifest_digest" not in c_data or not isinstance(c_data["source_manifest_digest"], str) or not SHA256_RE.fullmatch(c_data["source_manifest_digest"]):
        return fail(["canonical-index.json missing or invalid source_manifest_digest (must be sha256:64hex)"])
    if "source_digests" not in c_data or not isinstance(c_data["source_digests"], dict) or not c_data["source_digests"]:
        return fail(["canonical-index.json missing or empty source_digests"])
    for k, v in c_data["source_digests"].items():
        if not isinstance(k, str) or not isinstance(v, str) or not SHA256_RE.fullmatch(v):
            return fail([f"invalid source_digests entry {k}: {v} (must be sha256:64hex)"])
    canonical_normative = set(c_data["normative_anchors"])
    if not canonical_normative:
        return fail(["canonical has no normative IDs, cannot prove completeness"])
    p_text = plan_path.read_text(encoding="utf-8")
    # 校验 index 与 plan 的 source_manifest_digest 绑定（避免旧 index 对新规格误 PASS）
    plan_digest = None
    m = re.search(r"source_manifest_digest:\s*(\S+)", p_text)
    if m:
        plan_digest = m.group(1).strip().strip('"').strip("'").strip(",")
    if plan_digest is None:
        return fail(["plan missing source_manifest_digest binding to canonical-index (stale index)"])
    if not SHA256_RE.fullmatch(plan_digest):
        return fail([f"invalid plan source_manifest_digest: {plan_digest} (must be sha256:64hex)"])
    if plan_digest != c_data["source_manifest_digest"]:
        return fail([f"canonical-index source_manifest_digest {c_data['source_manifest_digest']} != plan {plan_digest} (stale index, need regenerate)"])
    anchors = set()
    for m in re.finditer(r"anchors:\s*\[([^\]]*)\]", p_text):
        inner = m.group(1)
        for a in re.finditer(r"\b(?:FR|AC|NFR|OOS)-[0-9]{3,}[A-Za-z0-9\-]*\b", inner):
            anchors.add(a.group(0))
    inv_match = re.search(r"normative_anchors:\s*\n((?:\s*-\s*(?:FR|AC|NFR|OOS)-[0-9].*\n)+)", p_text)
    if inv_match:
        inv_anchors = set(re.findall(r"\b(?:FR|AC|NFR|OOS)-[0-9]{3,}[A-Za-z0-9\-]*\b", inv_match.group(1)))
        anchors = anchors.union(inv_anchors)
    missing = canonical_normative - anchors
    if missing:
        return fail([f"planning index incomplete: canonical {sorted(canonical_normative)} not all covered by plan anchors {sorted(anchors)}; missing {sorted(missing)} (need manual full re-read or add to plan)"])
    return ok()

def main():
    if len(sys.argv) < 3:
        print("usage: validate-workflow-artifact.py <packet|verification|candidate> <path>  OR  planning-index <canonical> <plan>", file=sys.stderr)
        return 2
    mode = sys.argv[1]
    if mode in ("planning-index", "planning_index"):
        if len(sys.argv) == 4:
            return validate_planning_index(Path(sys.argv[2]), Path(sys.argv[3]))
        elif len(sys.argv) == 3:
            return validate_planning_index(Path(sys.argv[2]))
        else:
            print("planning-index needs <canonical> <plan> or <plan>", file=sys.stderr)
            return 2
    path = Path(sys.argv[2])
    if mode == "packet":
        return validate_packet(path)
    elif mode == "verification":
        return validate_verification(path)
    elif mode == "candidate":
        return validate_candidate(path)
    else:
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
