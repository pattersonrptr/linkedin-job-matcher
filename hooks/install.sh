#!/usr/bin/env bash
# Run this after `git init` to install hooks into .git/hooks/
set -e

HOOKS_DIR="$(cd "$(dirname "$0")/../.git/hooks" && pwd)"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$SOURCE_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
cp "$SOURCE_DIR/pre-push" "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-commit" "$HOOKS_DIR/pre-push"

echo "Hooks installed to $HOOKS_DIR"
