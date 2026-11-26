"""Actual local SQLite schema assertions through public strict handoff API."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from handoff_monitor import compare_handoff_validated
from test_lot4_structural_abstentions import load

SQLITE_CASES = (
    ("sqlite_table_column_and_fk_present", "clean", "PASS"),
    ("sqlite_required_table_missing", "violation", "ALERT"),
    ("sqlite_required_column_missing", "violation", "ALERT"),
    ("sqlite_required_column_type_wrong", "violation", "ALERT"),
    ("sqlite_required_fk_missing", "violation", "ALERT"),
    ("sqlite_not_database", "evidence_unavailable", "UNKNOWN"),
    ("sqlite_receiver_missing", "evidence_unavailable", "UNKNOWN"),
)


def run_sqlite_case(name):
    if name not in (row[0] for row in SQLITE_CASES):
        raise ValueError("Unknown SQLite scenario: " + name)
    with tempfile.TemporaryDirectory() as root:
        sender = Path(root) / "source.sqlite"
        receiver = Path(root) / "receiver.sqlite"
        if name == "sqlite_not_database":
            sender.write_bytes(b"not a SQLite database")
        else:
            con = sqlite3.connect(str(sender))
            try:
                con.execute("CREATE TABLE owners (id INTEGER PRIMARY KEY)")
                if name == "sqlite_required_table_missing":
                    con.execute("CREATE TABLE other_items (id INTEGER)")
                elif name == "sqlite_required_column_missing":
                    con.execute("CREATE TABLE items (id INTEGER, FOREIGN KEY(id) REFERENCES owners(id))")
                elif name == "sqlite_required_column_type_wrong":
                    con.execute("CREATE TABLE items (owner_id TEXT, FOREIGN KEY(owner_id) REFERENCES owners(id))")
                elif name == "sqlite_required_fk_missing":
                    con.execute("CREATE TABLE items (owner_id INTEGER)")
                else:
                    con.execute("CREATE TABLE items (owner_id INTEGER, FOREIGN KEY(owner_id) REFERENCES owners(id))")
                con.commit()
            finally:
                con.close()
        receiver.write_bytes(sender.read_bytes())
        raw = sender.read_bytes()
        plan, sent, received = (
            load("run-plan.json"), load("pass-sent.json"),
            load("pass-received.json"))
        checks = [
            {"check_type": "db_required_table", "table_name": "items"},
            {"check_type": "db_required_column", "table_name": "items",
             "column_name": "owner_id", "data_type": "INTEGER"},
            {"check_type": "db_required_foreign_key", "table_name": "items",
             "column_name": "owner_id", "references_table": "owners",
             "references_column": "id"},
        ]
        for manifest in (sent, received):
            artifact = manifest["artifacts"][0]
            artifact["kind"] = "db_schema"
            artifact["checks"] = {"exact_bytes": True,
                                  "required_structure": checks}
            artifact["content_sha256"] = hashlib.sha256(raw).hexdigest()
        receiver_files = {} if name == "sqlite_receiver_missing" else {
            "ART-001": receiver}
        return compare_handoff_validated(
            plan, sent, received,
            sender_files={"ART-001": sender}, receiver_files=receiver_files)


class SqliteSchemaTests(unittest.TestCase):
    def test_real_schema_observations(self):
        for name, truth, expected in SQLITE_CASES:
            with self.subTest(case=name):
                result = run_sqlite_case(name)
                codes = {x["code"] for x in result["findings"]}
                self.assertEqual(expected, result["verdict"])
                self.assertNotIn("INVALID_MANIFEST", codes)
                if truth == "violation":
                    self.assertIn("MISSING_REQUIRED_RULE", codes)
                elif truth == "evidence_unavailable":
                    self.assertIn("UNVERIFIABLE", codes)
                else:
                    self.assertIn("EXACT_BYTES_MATCH", codes)


if __name__ == "__main__":
    unittest.main()
