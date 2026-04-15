#!/usr/bin/env python3
"""
rollback.py — Restore memory system from backup
Verifies integrity and ensures consistency.
Non-destructive until explicitly confirmed.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
MEMORY_DIR = WORKSPACE / "memory"
BACKUP_DIR = Path(__file__).parent.parent / "backups"
ROLLBACK_FILE = BACKUP_DIR / "rollback_manifest.json"


def log(msg):
    print(f"[rollback] {msg}", file=sys.stderr)


def get_file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_latest_backup():
    backups = sorted(BACKUP_DIR.glob("memory_backup_*.tar.gz"), reverse=True)
    if backups:
        return backups[0]
    return None


class RollbackManager:
    def __init__(self, backup_path=None, dry_run=False, force=False):
        self.backup_path = backup_path
        self.dry_run = dry_run
        self.force = force
        self.manifest = None

    def run(self):
        log(f"Starting rollback (dry_run={self.dry_run})")

        # Find backup if not specified
        if not self.backup_path:
            self.backup_path = find_latest_backup()
            if not self.backup_path:
                log("ERROR: No backup found in memory/backups/")
                return False
            log(f"Using latest backup: {self.backup_path}")

        # Validate backup
        if not self._validate_backup():
            return False

        # Load manifest
        self._load_manifest()

        # Report
        self._report_restore_plan()

        if self.dry_run:
            log("Dry run complete. No changes made.")
            return True

        # Confirmation
        if not self.force:
            response = input("\nProceed with rollback? (yes/no): ").strip().lower()
            if response != "yes":
                log("Aborted.")
                return False

        # Execute
        return self._execute_rollback()

    def _validate_backup(self):
        log(f"Validating backup: {self.backup_path}")

        if not self.backup_path.exists():
            log(f"ERROR: Backup file not found: {self.backup_path}")
            return False

        # Verify checksum
        checksum_file = Path(str(self.backup_path) + ".sha256")
        if checksum_file.exists():
            expected = checksum_file.read_text().split()[0]
            actual = get_file_hash(self.backup_path)
            if expected != actual:
                log("ERROR: Checksum mismatch! Backup may be corrupted.")
                return False
            log("Checksum verified.")

        # Verify tarball
        try:
            with tarfile.open(self.backup_path) as tf:
                members = tf.getmembers()
                log(f"Backup contains {len(members)} items")
        except Exception as e:
            log(f"ERROR: Failed to read backup: {e}")
            return False

        return True

    def _load_manifest(self):
        if ROLLBACK_FILE.exists():
            with open(ROLLBACK_FILE) as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {}

    def _report_restore_plan(self):
        log("=== Rollback Plan ===")
        log(f"Source: {self.backup_path}")
        log(f"Destination: {MEMORY_DIR}")

        if self.manifest.get("files_backed_up"):
            log(f"Files in backup: {len(self.manifest['files_backed_up'])}")

        if self.manifest.get("timestamp"):
            log(f"Rollback point: {self.manifest['timestamp']}")

        log("=====================")

    def _execute_rollback(self):
        log("Executing rollback...")

        # Create temp directory for extraction
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="memory_rollback_")

        try:
            # Extract backup
            log("Extracting backup...")
            with tarfile.open(self.backup_path) as tf:
                tf.extractall(temp_dir)

            # Find extracted memory directory
            extracted_memory = Path(temp_dir) / "memory"
            if not extracted_memory.exists():
                log("ERROR: Invalid backup structure")
                return False

            # Remove current memory files
            log("Clearing current memory...")
            if MEMORY_DIR.exists():
                for item in MEMORY_DIR.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir() and item.name != ".":
                        shutil.rmtree(item)

            # Restore files
            log("Restoring files...")
            for item in extracted_memory.iterdir():
                dest = MEMORY_DIR / item.name
                shutil.copy2(item, dest)
                log(f"  Restored: {item.name}")

            # Verify restored files match hashes
            if self.manifest.get("files_backed_up"):
                log("Verifying integrity...")
                for rel_path, info in self.manifest["files_backed_up"].items():
                    restored_file = MEMORY_DIR / rel_path
                    if restored_file.exists():
                        actual_hash = get_file_hash(restored_file)
                        if actual_hash != info.get("hash"):
                            log(f"WARNING: Hash mismatch for {rel_path}")

            log("Rollback complete.")

        finally:
            shutil.rmtree(temp_dir)

        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rollback memory system from backup")
    parser.add_argument("--backup", help="Specific backup file path")
    parser.add_argument("--dry-run", action="store_true", help="Preview restore without writing")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")

    args = parser.parse_args()

    manager = RollbackManager(backup_path=args.backup, dry_run=args.dry_run, force=args.force)
    success = manager.run()

    sys.exit(0 if success else 1)