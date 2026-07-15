"""Summarize what changed between two housing_data.csv snapshots, keyed by LISTING_ID.

Usage: uv run python diff_listings.py <old_csv> <new_csv>

LISTING_AGE is ignored when detecting "changed" listings — it's a days-on-market
counter that increments on every refresh regardless of whether anything real changed.
"""
import csv
import sys

IGNORE_FIELDS = {"LISTING_AGE"}


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {row["LISTING_ID"]: row for row in csv.DictReader(f)}


def describe(row):
    addr = f"{row.get('STREET_NUMBER', '').strip()} {row.get('STREET', '').strip()}".strip()
    suburb = row.get("SUBURB", "").split(",")[-1].strip()
    price = row.get("EXPECTED_SALE_PRICE", "").strip()
    try:
        price = f"${float(price):,.0f}"
    except ValueError:
        price = "price n/a"
    return f"{addr}, {suburb} — {price}" if suburb else f"{addr} — {price}"


def main():
    old_path, new_path = sys.argv[1], sys.argv[2]
    old, new = load(old_path), load(new_path)

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    common = set(old) & set(new)

    changed = []
    for listing_id in sorted(common):
        old_row, new_row = old[listing_id], new[listing_id]
        diffs = [
            (field, old_row.get(field, ""), new_row.get(field, ""))
            for field in new_row
            if field not in IGNORE_FIELDS and old_row.get(field, "") != new_row.get(field, "")
        ]
        if diffs:
            changed.append((listing_id, new_row, diffs))

    if added:
        print(f"New listings ({len(added)}):")
        for listing_id in added:
            print(f"  - {listing_id}: {describe(new[listing_id])}")
        print()

    if removed:
        print(f"Removed listings ({len(removed)}):")
        for listing_id in removed:
            print(f"  - {listing_id}: {describe(old[listing_id])}")
        print()

    if changed:
        print(f"Changed listings ({len(changed)}):")
        for listing_id, row, diffs in changed:
            print(f"  - {listing_id}: {describe(row)}")
            for field, old_val, new_val in diffs:
                print(f"      {field}: {old_val or '(empty)'} -> {new_val or '(empty)'}")
        print()

    if not (added or removed or changed):
        print("No listing-level changes detected (only LISTING_AGE ticked up).")


if __name__ == "__main__":
    main()
