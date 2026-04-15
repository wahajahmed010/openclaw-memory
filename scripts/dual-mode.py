#!/usr/bin/env python3
"""
dual-mode.py — Run old and new memory systems in parallel
Compare outputs for sanity checking during migration.
Feature flag system for gradual rollout.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_DIR = WORKSPACE / "memory"
CONFIG_DIR = MEMORY_DIR / ".config"


@dataclass
class FeatureFlags:
    """Feature flags for gradual rollout"""
    new_search: bool = False  # Use new semantic search
    new_index: bool = False   # Use new index structure
    new_storage: bool = False  # Use new storage format
    compare_mode: bool = True  # Compare old vs new outputs

    def to_dict(self):
        return {
            "new_search": self.new_search,
            "new_index": self.new_index,
            "new_storage": self.new_storage,
            "compare_mode": self.compare_mode
        }

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class QueryResult:
    """Standardized query result"""
    system: str  # "old" or "new"
    query: str
    results: List[Dict[str, Any]]
    execution_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DualModeRunner:
    def __init__(self, flags: FeatureFlags):
        self.flags = flags
        self.results_log: List[QueryResult] = []

    def query_old_system(self, query: str) -> QueryResult:
        """Query using legacy memory system"""
        start = time.time()

        # TODO: Implement actual old system query
        # Placeholder: basic file-based search
        results = self._old_search(query)

        return QueryResult(
            system="old",
            query=query,
            results=results,
            execution_time_ms=(time.time() - start) * 1000
        )

    def query_new_system(self, query: str) -> QueryResult:
        """Query using new memory system"""
        if not self.flags.new_search:
            return QueryResult(system="new", query=query, results=[], execution_time_ms=0)

        start = time.time()

        # TODO: Implement actual new system query
        results = self._new_search(query)

        return QueryResult(
            system="new",
            query=query,
            results=results,
            execution_time_ms=(time.time() - start) * 1000
        )

    def _old_search(self, query: str) -> List[Dict]:
        """Legacy search implementation"""
        results = []
        query_lower = query.lower()

        for md_file in MEMORY_DIR.glob("*.md"):
            if md_file.name == "index.json":
                continue
            content = md_file.read_text().lower()
            if query_lower in content:
                results.append({
                    "file": md_file.name,
                    "type": "memory",
                    "relevance": "medium"
                })

        return results

    def _new_search(self, query: str) -> List[Dict]:
        """New semantic search implementation"""
        # TODO: Implement semantic search
        return []

    def run_query(self, query: str) -> tuple[QueryResult, QueryResult]:
        """Run query on both systems if compare mode enabled"""
        old_result = self.query_old_system(query)
        new_result = self.query_new_system(query)

        self.results_log.append(old_result)
        self.results_log.append(new_result)

        if self.flags.compare_mode:
            self._compare_results(old_result, new_result)

        return old_result, new_result

    def _compare_results(self, old: QueryResult, new: QueryResult):
        """Compare results from both systems"""
        print(f"\n[dual-mode] Comparing results for: {old.query}")

        old_files = {r["file"] for r in old.results}
        new_files = {r["file"] for r in new.results}

        if old_files == new_files:
            print("  ✓ Same files returned")
        else:
            only_old = old_files - new_files
            only_new = new_files - old_files
            if only_old:
                print(f"  ⚠ Only in old: {only_old}")
            if only_new:
                print(f"  ⚠ Only in new: {only_new}")

        # Performance comparison
        if new.execution_time_ms > 0:
            speedup = old.execution_time_ms / new.execution_time_ms
            print(f"  Performance: {speedup:.2f}x ({old.execution_time_ms:.1f}ms vs {new.execution_time_ms:.1f}ms)")


def load_flags() -> FeatureFlags:
    """Load feature flags from config"""
    flag_file = CONFIG_DIR / "feature_flags.json"
    if flag_file.exists():
        with open(flag_file) as f:
            return FeatureFlags.from_dict(json.load(f))
    return FeatureFlags()


def save_flags(flags: FeatureFlags):
    """Save feature flags to config"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    flag_file = CONFIG_DIR / "feature_flags.json"
    with open(flag_file, "w") as f:
        json.dump(flags.to_dict(), f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Dual-mode memory system runner")
    parser.add_argument("--query", help="Run a query against both systems")
    parser.add_argument("--enable-search", action="store_true", help="Enable new search")
    parser.add_argument("--enable-index", action="store_true", help="Enable new index")
    parser.add_argument("--enable-storage", action="store_true", help="Enable new storage")
    parser.add_argument("--disable-compare", action="store_true", help="Disable comparison mode")
    parser.add_argument("--status", action="store_true", help="Show current feature flags")
    parser.add_argument("--reset", action="store_true", help="Reset all flags to default")

    args = parser.parse_args()

    flags = load_flags()

    if args.status:
        print("=== Feature Flags ===")
        for k, v in flags.to_dict().items():
            print(f"  {k}: {v}")
        print("====================")
        return

    if args.reset:
        flags = FeatureFlags()
        save_flags(flags)
        print("Flags reset to defaults.")
        return

    # Update flags
    if args.enable_search:
        flags.new_search = True
        print("Enabled: new_search")
    if args.enable_index:
        flags.new_index = True
        print("Enabled: new_index")
    if args.enable_storage:
        flags.new_storage = True
        print("Enabled: new_storage")
    if args.disable_compare:
        flags.compare_mode = False
        print("Disabled: compare_mode")

    save_flags(flags)

    if args.query:
        runner = DualModeRunner(flags)
        old_result, new_result = runner.run_query(args.query)

        print(f"\n--- Old System ({old_result.execution_time_ms:.1f}ms) ---")
        for r in old_result.results:
            print(f"  {r['file']}")

        if new_result.results:
            print(f"\n--- New System ({new_result.execution_time_ms:.1f}ms) ---")
            for r in new_result.results:
                print(f"  {r['file']}")
        else:
            print("\n--- New System: Not enabled ---")


if __name__ == "__main__":
    main()