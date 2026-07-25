"""Download the raw StatsBomb open-data JSON for one competition/season.

Fetches competitions.json, the match list, and per-match events, lineups and
360 freeze-frame files into DATA_DIR. Idempotent: existing files are skipped,
so an interrupted download can simply be re-run.
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from pipeline.config import COMPETITION_ID, DATA_DIR, OPEN_DATA_BASE, SEASON_ID

_TIMEOUT = httpx.Timeout(30.0, read=120.0)


def _fetch(client: httpx.Client, rel_path: str, dest: Path) -> bool:
    """Download one file unless it already exists. Returns True if fetched."""
    if dest.exists() and dest.stat().st_size > 0:
        return False
    resp = client.get(f"{OPEN_DATA_BASE}/{rel_path}")
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    return True


def download_all(max_workers: int = 8) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
        _fetch(client, "competitions.json", DATA_DIR / "competitions.json")
        matches_rel = f"matches/{COMPETITION_ID}/{SEASON_ID}.json"
        matches_path = DATA_DIR / "matches.json"
        _fetch(client, matches_rel, matches_path)

        matches = json.loads(matches_path.read_text())
        match_ids = sorted(m["match_id"] for m in matches)
        print(f"{len(match_ids)} matches in competition {COMPETITION_ID}/{SEASON_ID}")

        jobs: list[tuple[str, Path]] = []
        for mid in match_ids:
            jobs.append((f"events/{mid}.json", DATA_DIR / "events" / f"{mid}.json"))
            jobs.append((f"lineups/{mid}.json", DATA_DIR / "lineups" / f"{mid}.json"))
            jobs.append(
                (f"three-sixty/{mid}.json", DATA_DIR / "three-sixty" / f"{mid}.json")
            )

        done = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch, client, rel, dest): rel for rel, dest in jobs}
            for fut in as_completed(futures):
                try:
                    fut.result()
                except httpx.HTTPStatusError as exc:
                    # 360 data can be missing for individual matches; that is fine.
                    if exc.response.status_code == 404 and "three-sixty" in futures[fut]:
                        print(f"no 360 data: {futures[fut]}")
                    else:
                        raise
                done += 1
                if done % 25 == 0:
                    print(f"{done}/{len(jobs)} files done", flush=True)
    print("download complete")


if __name__ == "__main__":
    download_all()
    sys.exit(0)
