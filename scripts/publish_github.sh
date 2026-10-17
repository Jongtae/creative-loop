#!/usr/bin/env bash
# Create a NEW PRIVATE repository and upload this project. Never touches unrelated repos.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for tool in gh git; do
  command -v "$tool" >/dev/null || { echo "$tool is required. Install it and rerun." >&2; exit 1; }
done
gh auth status >/dev/null || { echo 'Run: gh auth login' >&2; exit 1; }
OWNER="$(gh api user --jq .login)"
USER_ID="$(gh api user --jq .id)"
NAME="${1:-creative-loop}"
[[ "$NAME" =~ ^[A-Za-z0-9._-]+$ ]] || { echo 'Use a repository name only, not an owner/path.' >&2; exit 1; }
REPO="$OWNER/$NAME"
if git rev-parse --show-toplevel >/dev/null 2>&1; then
  [[ "$(git rev-parse --show-toplevel)" == "$ROOT" ]] || { echo 'This folder is inside an unrelated Git repository. Move it outside that repository first.' >&2; exit 1; }
else
  git init -b main
fi
if git remote get-url origin >/dev/null 2>&1; then
  echo 'An origin remote already exists. This script does not overwrite or republish existing repositories.' >&2
  echo 'Inspect git remote -v, then use git push after confirming the intended private repository.' >&2
  exit 1
fi
if gh repo view "$REPO" --json name >/dev/null 2>&1; then
  echo "$REPO already exists. Choose a new name: bash scripts/publish_github.sh another-name" >&2
  exit 1
fi
# No wildcard staging of credentials or runtime data. .gitignore adds another boundary.
git add -- README.md AGENTS.md SECURITY.md LICENSE.md requirements.txt requirements-dev.txt \
  pyproject.toml .env.example .gitignore .dockerignore Dockerfile compose.yaml \
  creative_loop tests scripts docs examples .github
if git ls-files | grep -E '(^|/)(\.env$|data/|\.venv/)|\.(sqlite3|pem|key)$' >/dev/null; then
  echo 'Potential secret/runtime files are tracked. Stop and remove them from Git before publishing.' >&2
  exit 1
fi
if ! git diff --cached --quiet; then
  git -c user.name="$OWNER" -c user.email="$USER_ID+$OWNER@users.noreply.github.com" \
    commit -m 'feat: bootstrap Creative Loop local-first creative production MVP'
fi
git rev-parse --verify HEAD >/dev/null
printf '\nCreating PRIVATE repository: %s\nSource: %s\n' "$REPO" "$ROOT"
gh repo create "$REPO" --private --source=. --remote=origin --push \
  --description 'Creative Loop: evidence-linked creative generation, editing and selection workbench' \
  --disable-wiki
printf '\nPublished: https://github.com/%s\n' "$REPO"
echo 'Optional backlog issues: python scripts/create_github_issues.py'
