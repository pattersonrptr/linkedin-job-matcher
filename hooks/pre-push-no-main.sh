#!/usr/bin/env bash
# Pre-push hook: block direct pushes to main

BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null)

if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
    echo ""
    echo "  BLOCKED: Direct push to '$BRANCH' is not allowed."
    echo "  Push to a feature branch and open a PR instead."
    echo ""
    echo "  To bypass (not recommended): git push --no-verify"
    echo ""
    exit 1
fi

exit 0
