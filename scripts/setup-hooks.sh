#!/usr/bin/env bash
# scripts/setup-hooks.sh — install .githooks as the repo's hook source
# Usage: bash scripts/setup-hooks.sh   (or: make hooks)
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
if [[ ! -d .githooks ]]; then
  echo "[FAIL] .githooks/ not found at $ROOT_DIR"
  exit 1
fi
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
# Normalize line endings for WSL users (hooks must be LF)
if command -v dos2unix >/dev/null 2>&1; then
  dos2unix .githooks/* 2>/dev/null || true
fi
echo "[PASS] git hooks installed: core.hooksPath=.githooks"
echo "  Hooks: $(ls -1 .githooks | tr '\n' ' ')"
echo "  Test:  git commit --allow-empty -m 'chore: test hooks'  (should run pre-commit + commit-msg)"
