#!/usr/bin/env bash
# Pre-commit hook: block secrets from being committed
# Exit 0 = pass, exit 1 = block with message

SECRETS_PATTERNS=(
    'GEMINI_API_KEY\s*=\s*["\x27][^"\x27]{10,}'
    'sk-ant-[A-Za-z0-9_-]{20,}'
    'sk-proj-[A-Za-z0-9_-]{20,}'
    'api[_-]?key\s*[:=]\s*["\x27][^"\x27]{10,}'
    'password\s*[:=]\s*["\x27]\S+["\x27]'
)

FILES=$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)

if [ -z "$FILES" ]; then
    exit 0
fi

for pattern in "${SECRETS_PATTERNS[@]}"; do
    MATCH=$(echo "$FILES" | xargs grep -lnE "$pattern" 2>/dev/null || true)
    if [ -n "$MATCH" ]; then
        echo ""
        echo "  BLOCKED: Possible secret detected in staged files:"
        echo "$MATCH" | while read -r f; do echo "    - $f"; done
        echo ""
        echo "  Remove the secret or add a .gitignore entry, then re-stage."
        echo "  To bypass (DANGEROUS): git commit --no-verify"
        echo ""
        exit 1
    fi
done

exit 0
