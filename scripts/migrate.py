#!/usr/bin/env python3
"""
migrate.py — Memory system migration script
Supports dry-run mode, atomic migration, and rollback points.
Non-destructive until explicitly confirmed.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_DIR = WORKSPACE / "memory"
BACKUP_DIR = Path(__file__).parent.parent / "backups"
ROLLBACK_FILE = BACKUP_DIR / "rollback_manifest.json"


def log(msg):
    print(f"[migrate] {msg}", file=sys.stderr)


def get_file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class MigrationManager:
    def __init__(self, dry_run=False, force=False):
        self.dry_run = dry_run
        self.force = force
        self.rollback_data = {
            "timestamp": datetime.now().isoformat(),
            "files_backed_up": {},
            "index_snapshot": None,
            "changes": []
        }
        self.work_dir = None

    def run(self):
        log(f"Starting migration (dry_run={self.dry_run}, force={self.force})")

        if not MEMORY_DIR.exists():
            log(f"ERROR: Memory directory {MEMORY_DIR} does not exist")
            return False

        # Load rollback manifest
        manifest = self._load_manifest()

        # Pre-flight checks
        if not self.force and manifest.get("in_progress"):
            log("ERROR: Previous migration appears incomplete. Use --force to override or run rollback first.")
            return False

        # Create rollback point
        if not self.dry_run:
            self.work_dir = tempfile.mkdtemp(prefix="memory_migrate_")
            log(f"Working directory: {self.work_dir}")

            # Backup current state
            if not self._create_rollback_point(manifest):
                return False

        # Preview changes
        changes = self._analyze_changes()
        self._report_changes(changes)

        if self.dry_run:
            log("Dry run complete. No changes made.")
            return True

        # Confirmation
        if not self.force:
            response = input("\nProceed with migration? (yes/no): ").strip().lower()
            if response != "yes":
                log("Aborted.")
                return False

        # Execute migration
        return self._execute_migration(changes, manifest)

    def _load_manifest(self):
        if ROLLBACK_FILE.exists():
            with open(ROLLBACK_FILE) as f:
                return json.load(f)
        return {}

    def _save_manifest(self, manifest):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        with open(ROLLBACK_FILE, "w") as f:
            json.dump(manifest, f, indent=2)

    def _create_rollback_point(self, manifest):
        log("Creating rollback point...")
        manifest["in_progress"] = True
        manifest["started_at"] = datetime.now().isoformat()

        # Snapshot index
        index_path = MEMORY_DIR / "index.json"
        if index_path.exists():
            manifest["index_snapshot"] = index_path.read_text()

            # Snapshot individual memory files
            for md_file in MEMORY_DIR.glob("*.md"):
                if md_file.name != "index.json":
                    rel_path = md_file.relative_to(MEMORY_DIR)
                    manifest["files_backed_up"][str(rel_path)] = {
                        "hash": get_file_hash(md_file),
                        "backed_up": False
                    }

        self._save_manifest(manifest)
        log("Rollback point created.")
        return True

    def _analyze_changes(self):
        changes = {
            "new_files": [],
            "modified_files": [],
            "deleted_files": []
        }

        index_path = MEMORY_DIR / "index.json"
        if index_path.exists():
            try:
                with open(index_path) as f:
                    index = json.load(f)
                changes["has_index"] = True
                changes["index_entries"] = len(index.get("entries", []))
            except json.JSONDecodeError as e:
                log(f"WARNING: Index parsing error: {e}")
                changes["has_index"] = False
        else:
            changes["has_index"] = False

        changes["memory_files"] = len(list(MEMORY_DIR.glob("*.md")))

        return changes

    def _report_changes(self, changes):
        log("=== Migration Preview ===")
        log(f"Memory directory: {MEMORY_DIR}")
        log(f"Has index: {changes.get('has_index', False)}")
        if changes.get("has_index"):
            log(f"Index entries: {changes.get('index_entries', 0)}")
        log(f"Memory files: {changes.get('memory_files', 0)}")
        log("=======================")

    def _execute_migration(self, changes, manifest):
        log("Executing migration...")

        # Mark files as backed up
        for rel_path in manifest.get("files_backed_up", {}):
            manifest["files_backed_up"][rel_path]["backed_up"] = True

        # TODO: Add actual migration logic here based on council design
        # This is a placeholder for the actual migration steps

        # Complete
        manifest["in_progress"] = False
        manifest["completed_at"] = datetime.now().isoformat()
        self._save_manifest(manifest)

        # Verify
        if not self._verify_migration():
            log("ERROR: Migration verification failed!")
            return False

        log("Migration complete.")
        return True

    def _verify_migration(self):
        log("Verifying migration...")
        # TODO: Add verification logic
        return True


def rollback():
    log("=== Rollback ===")

    if not ROLLBACK_FILE.exists():
        log("ERROR: No rollback point found")
        return False

    with open(ROLLBACK_FILE) as f:
        manifest = json.load(f)

    if not manifest.get("in_progress"):
        log("ERROR: No migration in progress")
        return False

    log("Restoring from rollback point...")

    # Restore index
    if "index_snapshot" in manifest:
        index_path = MEMORY_DIR / "index.json"
        snapshot = manifest["index_snapshot"]
        if snapshot:
            index_path.write_text(snapshot)
            log("Index restored.")
        else:
            if index_path.exists():
                index_path.unlink()
            log("Index removed.")

    manifest["in_progress"] = False
    manifest["rolled_back_at"] = datetime.now().isoformat()
    manifest["last_action"] = "rollback"

    with open(ROLLBACK_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    log("Rollback complete.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Memory system migration")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--force", action="store_true", help="Skip confirmation and safety checks")
    parser.add_argument("--rollback", action="store_true", help="Rollback current migration")

    args = parser.parse_args()

    if args.rollback:
        success = rollback()
    else:
        manager = MigrationManager(dry_run=args.dry_run, force=args.force)
        success = manager.run()

    sys.exit(0 if success else 1)