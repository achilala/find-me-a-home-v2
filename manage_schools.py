"""CLI for managing highlighted school enrolment zones.

Usage:
    uv run manage_schools.py list
    uv run manage_schools.py add --name "Mt Roskill Grammar"
    uv run manage_schools.py add --id 74
    uv run manage_schools.py add --id 74 --short "MRG"
    uv run manage_schools.py remove 74

After adding or removing a school, regenerate the map:
    uv run server.py          (local server)
    uv run python build.py    (static Vercel build)
"""

import argparse
import json
import sys
from pathlib import Path

import requests

from config import SCHOOL_COLOR_PALETTE, AppConfig

SCHOOLS_DIR_URL = (
    "https://services.arcgis.com/XTtANUDT8Va4DLwI/arcgis/rest/services"
    "/Schools_Directory_New_Zealand/FeatureServer/0"
)
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def load_config(config: AppConfig) -> dict[int, dict]:
    if config.schools_config_file.exists():
        raw = json.loads(config.schools_config_file.read_text())
        return {int(k): v for k, v in raw.items()}
    return dict(config.highlight_schools)


def save_config(schools: dict[int, dict], config: AppConfig) -> None:
    config.schools_config_file.parent.mkdir(exist_ok=True)
    config.schools_config_file.write_text(
        json.dumps({str(k): v for k, v in schools.items()}, indent=2)
    )


def next_color(schools: dict) -> dict:
    return SCHOOL_COLOR_PALETTE[len(schools) % len(SCHOOL_COLOR_PALETTE)]


def search_schools(name: str) -> list[dict]:
    params = {
        "where": f"Org_Name LIKE '%{name}%' AND Status='Open'",
        "outFields": "School_Id,Org_Name,Org_Type",
        "f": "json",
        "resultRecordCount": 10,
        "orderByFields": "Org_Name",
    }
    resp = requests.get(f"{SCHOOLS_DIR_URL}/query", params=params, timeout=15, headers=_HEADERS)
    resp.raise_for_status()
    return [f["attributes"] for f in resp.json().get("features", [])]


def fetch_school_by_id(school_id: int) -> dict | None:
    params = {
        "where": f"School_Id = {school_id} AND Status='Open'",
        "outFields": "School_Id,Org_Name,Org_Type",
        "f": "json",
    }
    resp = requests.get(f"{SCHOOLS_DIR_URL}/query", params=params, timeout=15, headers=_HEADERS)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    return features[0]["attributes"] if features else None


def derive_short_name(name: str) -> str:
    words = name.split()
    if len(words) <= 2:
        return words[0]
    # Use initials of first three words, e.g. "Mt Roskill Grammar" → "MRG"
    return "".join(w[0].upper() for w in words[:3])


# ---------------------------------------------------------------------------
# Sub-commands
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace, config: AppConfig) -> None:
    schools = load_config(config)
    if not schools:
        print("No schools configured.")
        return
    print(f"\n{'ID':<8} {'Short':<12} Name")
    print("─" * 55)
    for sid, info in schools.items():
        print(f"{sid:<8} {info['short']:<12} {info['name']}")
    print()


def cmd_add(args: argparse.Namespace, config: AppConfig) -> None:
    schools = load_config(config)

    if args.id:
        school = fetch_school_by_id(args.id)
        if not school:
            print(f"No open school found with ID {args.id}.")
            sys.exit(1)
        candidates = [school]
    elif args.name:
        candidates = search_schools(args.name)
        if not candidates:
            print(f"No schools found matching '{args.name}'.")
            sys.exit(1)
    else:
        print("Provide --name or --id.")
        sys.exit(1)

    if len(candidates) > 1:
        print(f"\nMultiple matches for '{args.name}':")
        for i, s in enumerate(candidates):
            print(f"  [{i}] {s['School_Id']:>6}  {s['Org_Name']}  ({s['Org_Type']})")
        try:
            idx = int(input("\nSelect index: "))
            school = candidates[idx]
        except (ValueError, IndexError):
            print("Invalid selection.")
            sys.exit(1)
    else:
        school = candidates[0]

    sid = int(school["School_Id"])
    if sid in schools:
        print(f"'{school['Org_Name']}' (ID {sid}) is already configured.")
        return

    short = args.short or derive_short_name(school["Org_Name"])
    schools[sid] = {"name": school["Org_Name"], "short": short, **next_color(schools)}
    save_config(schools, config)

    print(f"\nAdded: {school['Org_Name']} (ID {sid}, short='{short}')")
    print("Regenerate the map to see the change:")
    print("  uv run server.py    or    uv run python build.py\n")


def cmd_remove(args: argparse.Namespace, config: AppConfig) -> None:
    schools = load_config(config)
    if args.id not in schools:
        print(f"School ID {args.id} is not in the current configuration.")
        print("Run 'uv run manage_schools.py list' to see configured schools.")
        sys.exit(1)

    name = schools.pop(args.id)["name"]
    save_config(schools, config)

    print(f"\nRemoved: {name} (ID {args.id})")
    print("Regenerate the map to see the change:")
    print("  uv run server.py    or    uv run python build.py\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage highlighted school enrolment zones.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List currently configured schools")

    add_p = sub.add_parser("add", help="Add a school by name or ID")
    add_p.add_argument("--name", help="Search by school name (partial match)")
    add_p.add_argument("--id", type=int, help="Add by exact school ID")
    add_p.add_argument("--short", help="Short display name (auto-derived if omitted)")

    remove_p = sub.add_parser("remove", help="Remove a school by ID")
    remove_p.add_argument("id", type=int, help="School ID to remove")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AppConfig()

    {"list": cmd_list, "add": cmd_add, "remove": cmd_remove}[args.command](args, config)


if __name__ == "__main__":
    main()
