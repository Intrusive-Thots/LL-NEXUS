"""Build the champion catalog asset (assets/champions.json).

Primary source: Riot Data Dragon versioned champion list.
Offline fallback: a curated seed set so tests/simulation never depend on
network access. Run:  python scripts/build_champion_catalog.py [--offline]

The generated file is committed to the repository, so the shipped app does
not need internet at first launch (only for champion *images*, which are
cached and gracefully fall back to placeholders).
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "champions.json"

DD_BASE = "https://ddragon.leagueoflegends.com/api"

ROLE_MAP = {"Assassin": "MIDDLE", "Fighter": "TOP", "Marksman": "ADC",
            "Mage": "MIDDLE", "Tank": "TOP", "Support": "SUPPORT"}


def fetch_online() -> list[dict]:
    versions = json.load(urllib.request.urlopen(f"{DD_BASE}/versions.json", timeout=10))
    v = versions[0]
    data = json.load(urllib.request.urlopen(f"{DD_BASE}/v{v}/data/en_US/champion.json", timeout=15))
    rows = []
    for c in data["data"].values():
        roles = []
        for t in c.get("tags", []):
            r = ROLE_MAP.get(t)
            if r and r not in roles:
                roles.append(r)
        if "JUNGLE" not in roles and any(t in ("Fighter", "Mage", "Assassin")
                                         for t in c.get("tags", [])):
            roles.append("JUNGLE")   # heuristic secondary role; user can override
        rows.append({"id": int(c["key"]), "key": c["key"], "name": c["id"],
                     "alias": c["id"], "roles": roles or ["TOP"],
                     "resource": c.get("partype", "mana").lower()})
    return rows


#: Curated offline seed — enough breadth per role for realistic recommendations.
SEED = [
    ("Ashe", "4", "ADC", "mana"), ("Caitlyn", "51", "ADC", "mana"),
    ("Ezreal", "81", "ADC", "mana"), ("Jinx", "222", "ADC", "mana"),
    ("Kai'Sa", "145", "ADC", "mana"), ("Lucian", "236", "ADC", "mana"),
    ("Vayne", "67", "ADC", "mana"), ("Xayah", "498", "ADC", "mana"),
    ("Aphelios", "523", "ADC", "mana"), ("Miss Fortune", "21", "ADC", "mana"),
    ("Ahri", "103", "MIDDLE", "mana"), ("Annie", "12", "MIDDLE", "mana"),
    ("Ekko", "245", "MIDDLE", "mana"), ("Orianna", "61", "MIDDLE", "mana"),
    ("Syndra", "134", "MIDDLE", "mana"), ("Yasuo", "157", "MIDDLE", "mana"),
    ("Zed", "238", "MIDDLE", "energy"), ("Viktor", "29", "MIDDLE", "mana"),
    ("Amumu", "32", "JUNGLE", "mana"), ("Evelynn", "28", "JUNGLE", "mana"),
    ("Lee Sin", "64", "JUNGLE", "energy"), ("Viego", "234", "JUNGLE", "mana"),
    ("Hecarim", "120", "JUNGLE", "mana"), ("Kayn", "141", "JUNGLE", "mana"),
    ("Darius", "122", "TOP", "mana"), ("Fiora", "114", "TOP", "mana"),
    ("Garen", "86", "TOP", "mana"), ("Sett", "875", "TOP", "mana"),
    ("Camille", "164", "TOP", "mana"), ("Mordekaiser", "82", "TOP", "mana"),
    ("Blitzcrank", "53", "SUPPORT", "mana"), ("Lulu", "117", "SUPPORT", "mana"),
    ("Nautilus", "111", "SUPPORT", "mana"), ("Thresh", "412", "SUPPORT", "mana"),
    ("Janna", "40", "SUPPORT", "mana"), ("Rakan", "143", "SUPPORT", "mana"),
    ("Pyke", "555", "SUPPORT", "mana"), ("Karma", "43", "SUPPORT", "mana"),
]


def build_seed() -> list[dict]:
    rows = []
    for name, key, role, resource in SEED:
        alias = "".join(ch for ch in name if ch.isalnum())
        rows.append({"id": int(key), "key": key, "name": name, "alias": alias,
                     "roles": [role] + ([] if role != "SUPPORT" else ["SUPPORT"]),
                     "resource": resource})
    return rows


def main() -> int:
    offline = "--offline" in sys.argv
    try:
        champions = [] if offline else fetch_online()
        if not champions:
            raise RuntimeError("offline requested")
        source = "ddragon"
    except Exception as exc:
        champions = build_seed()
        source = f"seed ({exc.__class__.__name__})"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"version": 1, "source": source,
                               "champions": champions}, indent=1), encoding="utf-8")
    print(f"wrote {len(champions)} champions from {source} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
