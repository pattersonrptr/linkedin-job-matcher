#!/usr/bin/env bash
# Pre-install hook: warn when new dependencies are added
# Usage: Run this manually or wire as a pre-commit check on requirements*.txt / pyproject.toml

DEP_FILES=(requirements.txt requirements.in pyproject.toml setup.py setup.cfg Pipfile)

FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
CHANGED_DEP=""

for dep_file in "${DEP_FILES[@]}"; do
    if echo "$FILES" | grep -q "$dep_file"; then
        CHANGED_DEP="$dep_file"
        break
    fi
done

if [ -n "$CHANGED_DEP" ]; then
    echo ""
    echo "  WARNING: Dependency file changed: $CHANGED_DEP"
    echo "  New dependencies should be discussed before committing."
    echo "  If intentional and approved: git commit --no-verify"
    echo ""
    exit 0  # warn but don't block
fi

exit 0
