"""Batch-render printable opposition reports ("the Monday-morning routine").

Renders the dashboard's print-ready match report to PDF for a list of
opponents — or a whole tournament — in one command, using headless Chrome
against a running instance of the app:

    python -m pipeline matchpack --teams "Spain,France"
    python -m pipeline matchpack --all --comp 55-282 --out matchpacks/euro24
"""

import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

import httpx

DEFAULT_BASE_URL = os.environ.get("SCOUT_APP_URL", "http://localhost:8000")

_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def find_chrome() -> str:
    """Locate a Chrome/Chromium binary (env CHROME_BIN wins)."""
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    if platform.system() == "Darwin" and Path(_MAC_CHROME).exists():
        return _MAC_CHROME
    for name in ("google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "No Chrome/Chromium found; set CHROME_BIN to a browser binary."
    )


def parse_comp(comp: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d+)-(\d+)", comp)
    if not m:
        raise ValueError(f"competition must look like '43-106', got {comp!r}")
    return int(m.group(1)), int(m.group(2))


def resolve_teams(
    base_url: str, comp: str, names: list[str] | None
) -> list[tuple[int, str]]:
    """(team_id, name) for the requested team names, or all teams in the
    competition when names is None. Unknown names raise, listing what exists."""
    comp_id, season_id = parse_comp(comp)
    resp = httpx.get(
        f"{base_url}/api/teams",
        params={"competition_id": comp_id, "season_id": season_id},
        timeout=30,
    )
    resp.raise_for_status()
    available = {t["name"]: t["team_id"] for t in resp.json()}
    if names is None:
        return sorted((tid, name) for name, tid in available.items())
    out = []
    for name in names:
        if name not in available:
            raise ValueError(
                f"{name!r} is not in competition {comp}; "
                f"available: {', '.join(sorted(available))}"
            )
        out.append((available[name], name))
    return out


def report_url(base_url: str, comp: str, team_id: int) -> str:
    return (
        f"{base_url}/?comp={comp}&team={team_id}&tab={quote('Match report')}"
    )


def render_pack(
    comp: str,
    team_names: list[str] | None,
    out_dir: Path,
    base_url: str = DEFAULT_BASE_URL,
) -> list[Path]:
    chrome = find_chrome()
    teams = resolve_teams(base_url, comp, team_names)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for team_id, name in teams:
        dest = out_dir / f"{name.replace(' ', '_')}.pdf"
        subprocess.run(
            [
                chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={dest}", "--virtual-time-budget=10000",
                report_url(base_url, comp, team_id),
            ],
            check=True,
            capture_output=True,
        )
        print(f"wrote {dest}")
        written.append(dest)
    return written
