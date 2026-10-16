#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_DIR}"
python3 -m src.main --vfs "${PROJECT_DIR}/vfs-stage2.xml" \
  --script "${PROJECT_DIR}/scripts/stage2_errors.txt"
