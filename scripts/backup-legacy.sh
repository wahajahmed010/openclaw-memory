#!/usr/bin/env bash
# backup-legacy.sh — Pre-migration backup of memory system
# Safe, idempotent, non-destructive

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${SCRIPT_DIR}/../../../memory"
BACKUP_DIR="${SCRIPT_DIR}/../backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="memory_backup_${TIMESTAMP}.tar.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"
CHECKSUM_PATH="${BACKUP_PATH}.sha256"

echo "=== Pre-Migration Backup ==="
echo "Source: ${WORKSPACE}"
echo "Destination: ${BACKUP_PATH}"

# Verify source exists
if [[ ! -d "${WORKSPACE}" ]]; then
    echo "ERROR: Source directory ${WORKSPACE} does not exist"
    exit 1
fi

# Ensure backup dir exists
mkdir -p "${BACKUP_DIR}"

# Create tarball
echo "Creating tarball..."
tar -czf "${BACKUP_PATH}" -C "${SCRIPT_DIR}/../../.." "memory" || {
    echo "ERROR: Failed to create backup archive"
    exit 1
}

# Generate checksum
echo "Verifying integrity..."
sha256sum "${BACKUP_PATH}" > "${CHECKSUM_PATH}"

# Verify checksum
echo "Validating backup..."
CHECKSUM=$(sha256sum "${BACKUP_PATH}" | awk '{print $1}')
EXPECTED=$(cat "${CHECKSUM_PATH}" | awk '{print $1}')

if [[ "${CHECKSUM}" != "${EXPECTED}" ]]; then
    echo "ERROR: Checksum mismatch! Backup may be corrupted"
    rm -f "${BACKUP_PATH}" "${CHECKSUM_PATH}"
    exit 1
fi

# Report
BACKUP_SIZE=$(du -h "${BACKUP_PATH}" | cut -f1)
FILE_COUNT=$(tar -tzf "${BACKUP_PATH}" | wc -l)

echo "=== Backup Complete ==="
echo "File: ${BACKUP_NAME}"
echo "Size: ${BACKUP_SIZE}"
echo "Files backed up: ${FILE_COUNT}"
echo "Checksum: ${CHECKSUM}"
echo ""
echo "To restore: tar -xzf ${BACKUP_PATH} -C <workspace>"