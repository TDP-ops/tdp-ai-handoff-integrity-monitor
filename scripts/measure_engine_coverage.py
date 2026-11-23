"""Measure deterministic-engine Python line coverage using the stdlib.

This measures executed bytecode source lines, not branches, detection quality,
authenticated remote delivery, or the correctness of security decisions.
"""
import dis
import json
import sys
import trace
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "handoff_monitor/core.py",
    "handoff_monitor/journey.py",
    "handoff_monitor/lineage.py",
    "handoff_monitor/validation.py",
)


def executable_lines(code):
    lines = {line for _, line in dis.findlinestarts(code)}
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            lines.update(executable_lines(const))
    return lines


def run_tests():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"),
                                                pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return result.wasSuccessful(), result.testsRun


def main():
    sys.path.insert(0, str(ROOT))
    tracer = trace.Trace(count=True, trace=False)
    passed, tests_run = tracer.runfunc(run_tests)
    counts = tracer.results().counts
    report = {"tests_run": tests_run, "tests_passed": passed,
              "line_coverage": {}}
    for relative in MODULES:
        path = (ROOT / relative).resolve()
        candidates = executable_lines(compile(
            path.read_text(encoding="utf-8"), str(path), "exec"))
        covered = {line for (filename, line), count in counts.items()
                   if count > 0 and Path(filename).resolve() == path}
        total = len(candidates)
        report["line_coverage"][relative] = {
            "covered": len(covered & candidates),
            "executable": total,
            "percent": round(100 * len(covered & candidates) / total, 1)
                       if total else 100.0,
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    # Failing tests or an empty suite must not produce a successful measure.
    return 0 if passed and tests_run > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
