#!/usr/bin/env python3
"""Publish backlog issues AFTER the user creates the private repository. Requires gh."""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def gh(*args):
    return subprocess.check_output(["gh", *args], cwd=ROOT, text=True).strip()


def main():
    repo = json.loads(gh("repo", "view", "--json", "nameWithOwner,isPrivate"))
    if not repo["isPrivate"]:
        raise SystemExit("Refusing to publish project details into a public repository.")
    existing = json.loads(gh("issue", "list", "--state", "all", "--limit", "1000", "--json", "title"))
    titles = {r["title"] for r in existing}
    for item in json.loads((ROOT / "docs/backlog.json").read_text()):
        if item["title"] not in titles:
            print(gh("issue", "create", "--title", item["title"], "--body", item["body"]))


if __name__ == "__main__":
    main()
