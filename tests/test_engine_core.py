"""Synthetic tests of the deterministic core. No external receiver proof."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from handoff_monitor import compare_handoff, digest_file

PLAN = {"run_id":"r", "critical_rule_ids":["KEEP"], "contracts":[
    {"contract_id":"c","version":"1","from_step":"A","to_step":"B",
     "required_artifact_ids":["a"],"accepted_versions":{"a":["v1"]},
     "required_rule_ids":["KEEP"]}]}

def manifest(role, sha=None):
    artifact={"artifact_id":"a","artifact_version_id":"v1","kind":"pdf","required":True,
              "checks":{"exact_bytes":True},"observation":{"source":role,"access":"verified"}}
    if sha:
        artifact["content_sha256"]=sha
    return {"run_id":"r","handoff_id":"h","event_id":"e-"+role,"from_step":"A","to_step":"B",
            "contract_id":"c","contract_version":"1","manifest_role":role,
            "rule_ids":["KEEP"],"artifacts":[artifact]}

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a=Path(self.tmp.name)/"source.pdf"
        self.b=Path(self.tmp.name)/"received.pdf"
        self.a.write_bytes(b"exact synthetic source")
        self.b.write_bytes(b"exact synthetic source")
        self.sent=manifest("sent",digest_file(self.a))
        self.received=manifest("received",digest_file(self.b))

    def result(self, *, bytes_available=False, plan=None):
        kw=({"sender_files":{"a":self.a},"receiver_files":{"a":self.b}} if bytes_available else {})
        return compare_handoff(plan or PLAN,self.sent,self.received,**kw)

    def codes(self, result):
        return {f["code"] for f in result["findings"]}

    def test_verified_local_bytes_match(self):
        result=self.result(bytes_available=True)
        self.assertEqual("PASS", result["verdict"])
        self.assertIn("EXACT_BYTES_MATCH",self.codes(result))

    def test_matching_declared_hashes_are_not_proof(self):
        self.assertEqual("UNKNOWN",self.result()["verdict"])

    def test_actual_byte_modification(self):
        self.b.write_bytes(b"changed")
        result=self.result(bytes_available=True)
        self.assertEqual("ALERT",result["verdict"])
        self.assertIn("HASH_MISMATCH",self.codes(result))

    def test_missing_receiver_file(self):
        self.b.unlink()
        self.assertEqual("UNKNOWN",self.result(bytes_available=True)["verdict"])

    def test_untrue_manifest_digest(self):
        self.received["artifacts"][0]["content_sha256"]="a"*64
        result=self.result(bytes_available=True)
        self.assertEqual("ALERT",result["verdict"])
        self.assertIn("DECLARED_HASH_MISMATCH",self.codes(result))

    def test_version_reversion(self):
        self.received["artifacts"][0]["artifact_version_id"]="v0"
        self.assertIn("VERSION_ROLLBACK",self.codes(self.result()))

    def test_required_file_missing(self):
        self.received["artifacts"]=[]
        self.assertIn("MISSING_REQUIRED_ARTIFACT",self.codes(self.result()))

    def test_replacement_preserves_count(self):
        self.received["artifacts"][0]["artifact_id"]="replacement"
        self.assertIn("MISSING_REQUIRED_ARTIFACT",self.codes(self.result()))

    def test_required_rule_dropped(self):
        self.received["rule_ids"]=[]
        self.assertIn("MISSING_REQUIRED_RULE",self.codes(self.result()))

    def test_critical_rule_absent_from_contract(self):
        plan=copy.deepcopy(PLAN)
        plan["critical_rule_ids"].append("EXTRA")
        self.assertIn("MISSING_REQUIRED_RULE",self.codes(self.result(plan=plan)))

    def test_reused_event_id(self):
        self.received["event_id"]=self.sent["event_id"]
        self.assertIn("DUPLICATE_OR_UNEXPECTED",self.codes(self.result()))

    def test_changed_artifact_kind(self):
        self.received["artifacts"][0]["kind"]="docx"
        self.assertIn("ARTIFACT_ID_COLLISION",self.codes(self.result()))

    def test_contract_version_mismatch(self):
        self.received["contract_version"]="2"
        self.assertIn("CONTRACT_MISMATCH",self.codes(self.result()))

    def test_duplicate_artifact(self):
        self.received["artifacts"].append(copy.deepcopy(self.received["artifacts"][0]))
        self.assertIn("DUPLICATE_OR_UNEXPECTED",self.codes(self.result()))

    def test_unsupported_structure_is_unknown(self):
        self.sent["artifacts"][0]["checks"]["required_structure"]=[
            {"check_type":"pdf_min_pages","min_pages":2}]
        self.received["artifacts"][0]["checks"]["required_structure"]=[
            {"check_type":"pdf_min_pages","min_pages":2}]
        self.assertEqual("UNKNOWN",self.result(bytes_available=True)["verdict"])

    def test_undeclared_check_is_unknown(self):
        self.sent["artifacts"][0]["checks"]={}
        self.received["artifacts"][0]["checks"]={}
        self.assertEqual("UNKNOWN",self.result(bytes_available=True)["verdict"])

    def test_received_manifest_cannot_drop_exact_byte_check(self):
        self.received["artifacts"][0]["checks"] = {}
        result = self.result(bytes_available=True)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_received_manifest_cannot_remove_structure_checks(self):
        check = {"check_type": "pdf_min_pages", "min_pages": 3}
        self.sent["artifacts"][0]["checks"]["required_structure"] = [check]
        result = self.result(bytes_available=True)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_identical_checks_but_no_files_remain_unknown(self):
        result = self.result()
        self.assertEqual("UNKNOWN", result["verdict"])

    def test_required_flag_cannot_be_weakened(self):
        self.received["artifacts"][0]["required"] = False
        result = self.result(bytes_available=True)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("MISSING_REQUIRED_RULE", self.codes(result))

    def test_declared_sender_size_must_match_real_file(self):
        self.sent["artifacts"][0]["size_bytes"] = self.a.stat().st_size + 1
        result = self.result(bytes_available=True)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("DECLARED_SIZE_MISMATCH", self.codes(result))

    def test_declared_receiver_size_must_match_real_file(self):
        self.received["artifacts"][0]["size_bytes"] = self.b.stat().st_size + 1
        result = self.result(bytes_available=True)
        self.assertEqual("ALERT", result["verdict"])
        self.assertIn("DECLARED_SIZE_MISMATCH", self.codes(result))

    def test_correct_declared_sizes_allow_local_byte_match(self):
        self.sent["artifacts"][0]["size_bytes"] = self.a.stat().st_size
        self.received["artifacts"][0]["size_bytes"] = self.b.stat().st_size
        self.assertEqual("PASS", self.result(bytes_available=True)["verdict"])

    def test_unavailable_bytes_cannot_validate_declared_size(self):
        self.sent["artifacts"][0]["size_bytes"] = 999
        self.received["artifacts"][0]["size_bytes"] = 999
        self.assertEqual("UNKNOWN", self.result()["verdict"])

    def test_observe_file_reports_digest_and_size_together(self):
        from handoff_monitor.core import observe_file
        sha, size = observe_file(self.a)
        self.assertEqual(hashlib.sha256(self.a.read_bytes()).hexdigest(), sha)
        self.assertEqual(len(self.a.read_bytes()), size)

    def test_observe_empty_file(self):
        from handoff_monitor.core import observe_file
        self.a.write_bytes(b"")
        sha, size = observe_file(self.a)
        self.assertEqual(hashlib.sha256(b"").hexdigest(), sha)
        self.assertEqual(0, size)

    def test_digest_reads_real_bytes(self):
        self.assertEqual(hashlib.sha256(self.a.read_bytes()).hexdigest(), digest_file(self.a))

if __name__=="__main__":
    unittest.main()
