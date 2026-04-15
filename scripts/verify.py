#!/usr/bin/env python3
"""
verify.py — Verification suite for memory system
- Check index integrity
- Spot-check random memories
- Performance benchmarks
- Report mismatches
Idempotent, read-only by default.
"""

import argparse
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_DIR = WORKSPACE / "memory"
INDEX_FILE = MEMORY_DIR / "index.json"


def log(msg):
    print(f"[verify] {msg}", file=sys.stderr)


def get_file_hash(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class VerificationResult:
    """Result of a verification check"""
    check_name: str
    passed: bool
    message: str
    details: Dict = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Performance benchmark result"""
    operation: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float


from dataclasses import dataclass, field


class VerificationSuite:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.results: List[VerificationResult] = []
        self.benchmarks: List[BenchmarkResult] = []

    def run_all(self) -> bool:
        """Run all verification checks"""
        checks = [
            ("Index Integrity", self.check_index_integrity),
            ("Memory Files", self.check_memory_files),
            ("Index Consistency", self.check_index_consistency),
            ("File Permissions", self.check_file_permissions),
            ("Storage Limits", self.check_storage_limits),
        ]

        all_passed = True
        for name, check_fn in checks:
            log(f"Running: {name}...")
            result = check_fn()
            self.results.append(result)
            if not result.passed:
                all_passed = False
                print(f"  ✗ FAILED: {result.message}")
            else:
                print(f"  ✓ PASSED: {result.message}")

        return all_passed

    def check_index_integrity(self) -> VerificationResult:
        """Verify index file is valid JSON and properly structured"""
        if not INDEX_FILE.exists():
            return VerificationResult(
                check_name="Index Integrity",
                passed=False,
                message="index.json not found"
            )

        try:
            with open(INDEX_FILE) as f:
                index = json.load(f)
        except json.JSONDecodeError as e:
            return VerificationResult(
                check_name="Index Integrity",
                passed=False,
                message=f"Invalid JSON: {e}"
            )

        # Check required fields
        required_fields = ["entries", "version", "last_updated"]
        missing = [f for f in required_fields if f not in index]
        if missing:
            return VerificationResult(
                check_name="Index Integrity",
                passed=False,
                message=f"Missing fields: {missing}",
                details={"found_fields": list(index.keys())}
            )

        return VerificationResult(
            check_name="Index Integrity",
            passed=True,
            message=f"Valid index with {len(index['entries'])} entries",
            details={"entries": len(index["entries"])}
        )

    def check_memory_files(self) -> VerificationResult:
        """Verify all referenced files exist"""
        if not INDEX_FILE.exists():
            return VerificationResult(
                check_name="Memory Files",
                passed=False,
                message="No index to check against"
            )

        with open(INDEX_FILE) as f:
            index = json.load(f)

        missing_files = []
        for entry in index.get("entries", []):
            if "file" in entry:
                file_path = MEMORY_DIR / entry["file"]
                if not file_path.exists():
                    missing_files.append(entry["file"])

        if missing_files:
            return VerificationResult(
                check_name="Memory Files",
                passed=False,
                message=f"{len(missing_files)} referenced files missing",
                details={"missing": missing_files}
            )

        return VerificationResult(
            check_name="Memory Files",
            passed=True,
            message="All referenced files exist"
        )

    def check_index_consistency(self) -> VerificationResult:
        """Verify index entries match actual files"""
        if not INDEX_FILE.exists():
            return VerificationResult(
                check_name="Index Consistency",
                passed=False,
                message="No index to check"
            )

        with open(INDEX_FILE) as f:
            index = json.load(f)

        indexed_files = {e.get("file") for e in index.get("entries", []) if "file" in e}
        actual_files = {f.name for f in MEMORY_DIR.glob("*.md")} - {"index.json"}

        orphaned = indexed_files - actual_files  # In index but not on disk
        unindexed = actual_files - indexed_files  # On disk but not in index

        issues = []
        if orphaned:
            issues.append(f"{len(orphaned)} orphaned index entries")
        if unindexed:
            issues.append(f"{len(unindexed)} unindexed files")

        if issues:
            return VerificationResult(
                check_name="Index Consistency",
                passed=False,
                message="; ".join(issues),
                details={"orphaned": list(orphaned), "unindexed": list(unindexed)}
            )

        return VerificationResult(
            check_name="Index Consistency",
            passed=True,
            message="Index matches filesystem"
        )

    def check_file_permissions(self) -> VerificationResult:
        """Verify files have appropriate permissions"""
        issues = []
        for f in MEMORY_DIR.glob("*.md"):
            if not os.access(f, os.R_OK):
                issues.append(f"{f.name} not readable")

        if issues:
            return VerificationResult(
                check_name="File Permissions",
                passed=False,
                message=f"{len(issues)} permission issues",
                details={"files": issues}
            )

        return VerificationResult(
            check_name="File Permissions",
            passed=True,
            message="All files readable"
        )

    def check_storage_limits(self) -> VerificationResult:
        """Check storage usage against limits"""
        total_size = sum(f.stat().st_size for f in MEMORY_DIR.glob("*.md"))
        file_count = len(list(MEMORY_DIR.glob("*.md")))

        # Arbitrary limits - adjust as needed
        SIZE_LIMIT = 100 * 1024 * 1024  # 100MB
        FILE_LIMIT = 10000

        issues = []
        if total_size > SIZE_LIMIT:
            issues.append(f"Size {total_size / 1024 / 1024:.1f}MB exceeds {SIZE_LIMIT / 1024 / 1024}MB limit")
        if file_count > FILE_LIMIT:
            issues.append(f"File count {file_count} exceeds {FILE_LIMIT} limit")

        if issues:
            return VerificationResult(
                check_name="Storage Limits",
                passed=False,
                message="; ".join(issues),
                details={"size_bytes": total_size, "file_count": file_count}
            )

        return VerificationResult(
            check_name="Storage Limits",
            passed=True,
            message=f"Within limits ({total_size / 1024:.1f}KB, {file_count} files)"
        )

    def spot_check_memories(self, count: int = 5) -> List[VerificationResult]:
        """Spot-check random memory files for basic validity"""
        results = []
        memory_files = [f for f in MEMORY_DIR.glob("*.md") if f.name != "index.json"]

        if not memory_files:
            results.append(VerificationResult(
                check_name="Spot Check",
                passed=False,
                message="No memory files to check"
            ))
            return results

        sample = random.sample(memory_files, min(count, len(memory_files)))

        for f in sample:
            try:
                content = f.read_text()
                lines = content.split("\n")

                # Basic checks
                issues = []
                if len(content) < 10:
                    issues.append("very short")
                if not content.strip():
                    issues.append("empty")

                if issues:
                    results.append(VerificationResult(
                        check_name=f"Spot Check: {f.name}",
                        passed=False,
                        message=f"Issues: {', '.join(issues)}",
                        details={"size": len(content), "lines": len(lines)}
                    ))
                else:
                    results.append(VerificationResult(
                        check_name=f"Spot Check: {f.name}",
                        passed=True,
                        message=f"OK ({len(content)} chars, {len(lines)} lines)",
                        details={"size": len(content), "lines": len(lines)}
                    ))
            except Exception as e:
                results.append(VerificationResult(
                    check_name=f"Spot Check: {f.name}",
                    passed=False,
                    message=f"Read error: {e}"
                ))

        return results

    def run_benchmarks(self, iterations: int = 100) -> List[BenchmarkResult]:
        """Run performance benchmarks"""
        benchmarks = []

        # Benchmark 1: Index loading
        if INDEX_FILE.exists():
            times = []
            for _ in range(iterations):
                start = time.time()
                with open(INDEX_FILE) as f:
                    json.load(f)
                times.append((time.time() - start) * 1000)

            benchmarks.append(BenchmarkResult(
                operation="Index Loading",
                iterations=iterations,
                total_time_ms=sum(times),
                avg_time_ms=sum(times) / len(times),
                min_time_ms=min(times),
                max_time_ms=max(times)
            ))

        # Benchmark 2: File enumeration
        times = []
        for _ in range(iterations):
            start = time.time()
            list(MEMORY_DIR.glob("*.md"))
            times.append((time.time() - start) * 1000)

        benchmarks.append(BenchmarkResult(
            operation="File Enumeration",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=sum(times) / len(times),
            min_time_ms=min(times),
            max_time_ms=max(times)
        ))

        # Benchmark 3: Hash computation
        memory_files = [f for f in MEMORY_DIR.glob("*.md") if f.name != "index.json"]
        if memory_files:
            sample_file = memory_files[0]
            times = []
            for _ in range(iterations):
                start = time.time()
                get_file_hash(sample_file)
                times.append((time.time() - start) * 1000)

            benchmarks.append(BenchmarkResult(
                operation="Hash Computation",
                iterations=iterations,
                total_time_ms=sum(times),
                avg_time_ms=sum(times) / len(times),
                min_time_ms=min(times),
                max_time_ms=max(times)
            ))

        self.benchmarks = benchmarks
        return benchmarks

    def report_benchmarks(self):
        """Print benchmark results"""
        if not self.benchmarks:
            log("No benchmarks run")
            return

        print("\n=== Performance Benchmarks ===")
        for b in self.benchmarks:
            print(f"\n{b.operation}:")
            print(f"  Iterations: {b.iterations}")
            print(f"  Average: {b.avg_time_ms:.3f}ms")
            print(f"  Min: {b.min_time_ms:.3f}ms")
            print(f"  Max: {b.max_time_ms:.3f}ms")

    def report_mismatches(self):
        """Report any detected mismatches"""
        mismatches = [r for r in self.results if not r.passed]

        if not mismatches:
            print("\n=== No Mismatches Detected ===")
            return

        print(f"\n=== Mismatches ({len(mismatches)}) ===")
        for r in mismatches:
            print(f"\n{r.check_name}:")
            print(f"  Message: {r.message}")
            if r.details:
                print(f"  Details: {r.details}")


def main():
    parser = argparse.ArgumentParser(description="Memory system verification suite")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    parser.add_argument("--index", action="store_true", help="Check index integrity")
    parser.add_argument("--files", action="store_true", help="Check memory files")
    parser.add_argument("--consistency", action="store_true", help="Check index consistency")
    parser.add_argument("--spot-check", action="store_true", help="Spot-check random memories")
    parser.add_argument("--spot-count", type=int, default=5, help="Number of spot checks")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmarks")
    parser.add_argument("--benchmark-iterations", type=int, default=100, help="Benchmark iterations")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    suite = VerificationSuite(verbose=args.verbose)

    # Default: run all checks
    run_all_checks = not any([args.index, args.files, args.consistency, args.spot_check, args.benchmark])

    if run_all_checks or args.all:
        passed = suite.run_all()
        if args.spot_check or run_all_checks:
            spot_results = suite.spot_check_memories(args.spot_count)
            for r in spot_results:
                suite.results.append(r)
                if r.passed:
                    print(f"  ✓ {r.check_name}: {r.message}")
                else:
                    print(f"  ✗ {r.check_name}: {r.message}")

    if args.index:
        suite.run_all()

    if args.files:
        suite.check_memory_files()

    if args.consistency:
        suite.check_index_consistency()

    if args.benchmark or (args.all and not run_all_checks):
        suite.run_benchmarks(args.benchmark_iterations)
        suite.report_benchmarks()

    # Report mismatches
    suite.report_mismatches()

    # Summary
    failed = len([r for r in suite.results if not r.passed])
    if failed == 0:
        log("All checks passed.")
        return 0
    else:
        log(f"{failed} check(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())