#!/usr/bin/env python3
import json
import tempfile
import subprocess
import sys
from pathlib import Path
import unittest

AGENT = Path(__file__).resolve().parents[1] / "agents" / "validate-workflow-artifact.py"

def run(mode, path):
    r = subprocess.run([sys.executable, str(AGENT), mode, str(path)], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)

def run2(mode, p1, p2):
    r = subprocess.run([sys.executable, str(AGENT), mode, str(p1), str(p2)], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)

def write_tmp(content, suffix=".md"):
    p = Path(tempfile.gettempdir()) / f"tmp_{suffix}_{hash(content) % 100000}{suffix}"
    p.write_text(content)
    return p

VALID_SHA = "a" * 40
VALID_SHA256 = "sha256:" + "b" * 64
OTHER_SHA = "c" * 40

PACKET_VALID = f"""
source_manifest:
  SPEC-REQ:
    stable_id: SPEC-REQ
    path: docs/specs/requirements.md
    digest: {VALID_SHA256}
    approval:
      status: approved
      authority: user
      decided_at: 2026-08-28
      evidence_ref: repo
task:
  sources:
    - ref: SPEC-REQ
      anchors: [FR-001, AC-001]
write_scope:
  - 创建: exact/path/file.py
verification:
  plan: something
  result: something
stop_conditions: BLOCKED
delivery_authorization:
  status: authorized
"""

class TestValidatePacket(unittest.TestCase):
    def test_valid_packet(self):
        p = write_tmp(PACKET_VALID)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "PASS")

    def test_missing_approval(self):
        p = write_tmp(PACKET_VALID.replace("approval:", "nope:"))
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("approval" in e for e in out["errors"]))

    def test_dangling_ref(self):
        bad = PACKET_VALID.replace("ref: SPEC-REQ", "ref: SPEC-MISSING")
        p = write_tmp(bad)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("not in manifest" in e for e in out["errors"]))

    def test_invalid_digest(self):
        bad = PACKET_VALID.replace(VALID_SHA256, "sha256:invalid")
        p = write_tmp(bad)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_empty_anchors(self):
        bad = PACKET_VALID.replace("anchors: [FR-001, AC-001]", "anchors: []")
        p = write_tmp(bad)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_invalid_delivery_enum(self):
        bad = PACKET_VALID.replace("status: authorized", "status: bogus")
        p = write_tmp(bad)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_missing_write_scope(self):
        bad = PACKET_VALID.replace("write_scope:", "nope:")
        p = write_tmp(bad)
        code, out = run("packet", p)
        self.assertEqual(out["status"], "BLOCKED")

class TestValidateVerification(unittest.TestCase):
    def test_valid_json(self):
        data = {
            "verification": {
                "plan": {"requirement_refs": ["AC-001"]},
                "result": {
                    "coverage": {"AC-001": "covered"},
                    "runs": [{"check_id": "CHECK-001", "outcome": "PASS", "evidence_ref": "evidence"}],
                    "bindings": {"source_manifest_digest": VALID_SHA256, "implementation_digest": VALID_SHA256, "environment": "test"},
                    "validity": "valid"
                }
            }
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("verification", p)
        self.assertEqual(out["status"], "PASS")

    def test_invalid_validity(self):
        data = {
            "verification": {
                "plan": {},
                "result": {
                    "coverage": {"AC-001": "covered"},
                    "runs": [],
                    "bindings": {"source_manifest_digest": VALID_SHA256, "implementation_digest": VALID_SHA256, "environment": "test"},
                    "validity": "bogus"
                }
            }
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("verification", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_missing_bindings(self):
        data = {"verification": {"plan": {}, "result": {"coverage": {}, "runs": [], "validity": "valid"}}}
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("verification", p)
        self.assertEqual(out["status"], "BLOCKED")

class TestValidateCandidate(unittest.TestCase):
    def test_valid_candidate(self):
        data = {
            "candidate_sha": VALID_SHA,
            "candidate_review": {"sha": VALID_SHA},
            "full_spec_gap": {"sha": VALID_SHA},
            "full_ci_run": {"head_sha": VALID_SHA, "conclusion": "success", "run_id": "1", "url": "https://x"}
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("candidate", p)
        self.assertEqual(out["status"], "PASS")

    def test_sha_mismatch(self):
        data = {
            "candidate_sha": VALID_SHA,
            "candidate_review": {"sha": OTHER_SHA},
            "full_spec_gap": {"sha": VALID_SHA},
            "full_ci_run": {"head_sha": VALID_SHA, "conclusion": "success", "run_id": "1", "url": "https://x"}
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("candidate", p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("candidate_review.sha" in e for e in out["errors"]))

    def test_invalid_conclusion(self):
        data = {
            "candidate_sha": VALID_SHA,
            "candidate_review": {"sha": VALID_SHA},
            "full_spec_gap": {"sha": VALID_SHA},
            "full_ci_run": {"head_sha": VALID_SHA, "conclusion": "bogus", "run_id": "1", "url": "https://x"}
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("candidate", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_legacy_full_ci_passed_forbidden(self):
        data = {
            "candidate_sha": VALID_SHA,
            "candidate_review": {"sha": VALID_SHA},
            "full_spec_gap": {"sha": VALID_SHA},
            "full_ci_run": {"head_sha": VALID_SHA, "conclusion": "success", "run_id": "1", "url": "https://x"},
            "full_ci_passed": True
        }
        p = write_tmp(json.dumps(data), suffix=".json")
        code, out = run("candidate", p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("full_ci_passed" in e for e in out["errors"]))

class TestPlanningIndex(unittest.TestCase):
    def test_incomplete_index(self):
        # normative FR-002 present but not in anchors (single-file self-check)
        txt = "FR-001 AC-001 FR-002\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        p = write_tmp(txt)
        code, out = run("planning-index", p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_complete_index(self):
        # 单参永远 fail-closed，需 canonical 索引才能 PASS
        txt = "FR-001 AC-001\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        p = write_tmp(txt)
        code, out = run("planning-index", p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("single-file" in e or "canonical" in e for e in out["errors"]))

    def test_canonical_vs_plan_missing(self):
        # canonical (json) has FR-002, plan omits it → must BLOCK
        canonical = json.dumps({"normative_anchors": ["FR-001", "FR-002", "AC-001"], "source_manifest_digest": VALID_SHA256, "source_digests": {"SPEC-REQ": VALID_SHA256}})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("FR-002" in e for e in out["errors"]))

    def test_canonical_vs_plan_complete(self):
        # 即使纯 FR/AC 的 markdown 也必须 BLOCKED，需 json 索引才允许机械 PASS
        canonical = "FR-001 AC-001"
        plan = " sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        c = write_tmp(canonical, suffix=".md")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_canonical_markdown_with_constraints_needs_json(self):
        # canonical markdown 含 Constraints/无法枚举类型时，必须走 json 或人工全读
        canonical = "FR-001 Constraints: must not do X"
        plan = " sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".md")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertTrue(any("canonical" in e.lower() for e in out["errors"]))

    def test_canonical_json_allows_mechanical_pass(self):
        canonical = json.dumps({"normative_anchors": ["FR-001", "AC-001"], "source_manifest_digest": VALID_SHA256, "source_digests": {"SPEC-REQ": VALID_SHA256}})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "PASS")

    def test_malformed_json_blocked(self):
        canonical = "{ not json FR-001"  # malformed but contains FR-001
        plan = " sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_invalid_schema_blocked(self):
        canonical = json.dumps({"foo": ["FR-001"]})  # wrong schema
        plan = " sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_dict_non_string_elements_blocked(self):
        canonical = json.dumps({"normative_anchors": [{"id": "FR-001"}]})
        plan = " sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_missing_source_manifest_digest_blocked(self):
        canonical = json.dumps({"normative_anchors": ["FR-001"], "source_digests": {"SPEC-REQ": VALID_SHA256}})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_missing_source_digests_blocked(self):
        canonical = json.dumps({"normative_anchors": ["FR-001"], "source_manifest_digest": VALID_SHA256})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_stale_digest_blocked(self):
        canonical = json.dumps({"normative_anchors": ["FR-001"], "source_manifest_digest": VALID_SHA256, "source_digests": {"SPEC-REQ": VALID_SHA256}})
        other_digest = "sha256:" + "c" * 64
        plan = f"source_manifest_digest: {other_digest}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_top_level_list_blocked(self):
        canonical = json.dumps(["FR-001", "AC-001"])
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001, AC-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_invalid_source_digests_value_blocked(self):
        canonical = json.dumps({"normative_anchors": ["FR-001"], "source_manifest_digest": VALID_SHA256, "source_digests": {"SPEC-REQ": "garbage"}})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

    def test_git_sha_in_source_digests_blocked(self):
        git_sha = "a" * 40
        canonical = json.dumps({"normative_anchors": ["FR-001"], "source_manifest_digest": VALID_SHA256, "source_digests": {"SPEC-REQ": git_sha}})
        plan = f"source_manifest_digest: {VALID_SHA256}\n sources:\n  - ref: SPEC-REQ\n    anchors: [FR-001]"
        c = write_tmp(canonical, suffix=".json")
        p = write_tmp(plan, suffix=".md")
        code, out = run2("planning-index", c, p)
        self.assertEqual(out["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
