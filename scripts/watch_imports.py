#!/usr/bin/env python3
"""Incrementally import authorized local JSON/CSV exports. This is not an SNS crawler."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import httpx
from dotenv import load_dotenv


def import_once(directory: Path, state_path: Path, client: httpx.Client) -> dict:
    """Only successful snapshots are remembered; API import is atomic and idempotent."""
    if not directory.is_dir():
        raise ValueError(f"Import folder does not exist: {directory}")
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    results = {"imported_files": 0, "unchanged_files": 0, "failed_files": 0}
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".json", ".csv"} or path.resolve() == state_path.resolve():
            continue
        try:
            if path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("File exceeds the 2MB import limit")
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if state.get(path.name) == digest:
                results["unchanged_files"] += 1
                continue
            response = client.post("/api/observations/import-file", files={"file": (path.name, content, "application/octet-stream")})
            response.raise_for_status()
            response.json()  # Require a valid API acknowledgement, not an HTML proxy success page.
            state[path.name] = digest
            state_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = state_path.with_suffix(state_path.suffix + ".tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(temporary, state_path)
            results["imported_files"] += 1
            print(f"Imported: {path.name}")
        except (OSError, ValueError, httpx.HTTPError) as exc:
            results["failed_files"] += 1
            # Do not echo response bodies or request headers that may contain personal data.
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            print(f"Failed: {path.name} ({status}); not marked as imported")
    return results


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--state", type=Path, default=Path("data/import-state.json"))
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    target = urlparse(args.url)
    if target.scheme not in {"http", "https"} or target.hostname not in {"127.0.0.1", "localhost", "::1"} or target.username or target.password:
        parser.error("This local-only importer accepts only localhost or loopback URLs.")
    if not args.once and args.interval < 60:
        parser.error("The minimum polling interval is 60 seconds.")
    headers = {"X-Creative-Loop": "1"}
    if os.getenv("APP_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["APP_TOKEN"]
    with httpx.Client(base_url=args.url, headers=headers, timeout=60, follow_redirects=False) as client:
        try:
            while True:
                result = import_once(args.directory, args.state, client)
                print(json.dumps(result))
                if args.once:
                    return 1 if result["failed_files"] else 0
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
