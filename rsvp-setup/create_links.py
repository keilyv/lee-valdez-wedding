#!/usr/bin/env python3
"""Create private links and D1 seed SQL. Keep the outputs outside your public repo."""
import argparse
import csv
import hashlib
import secrets
from pathlib import Path
from urllib.parse import quote


def sql_string(value):
    return "'" + value.replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("guest_csv", type=Path, help="CSV with household_name,max_guests")
    parser.add_argument("--output", type=Path, default=Path("../wedding-rsvp-private"))
    parser.add_argument("--site-url", default="https://keilyv.github.io/lee-valdez-wedding/")
    args = parser.parse_args()
    with args.guest_csv.open(newline="", encoding="utf-8-sig") as source:
        guests = list(csv.DictReader(source))
    if not guests or not all("household_name" in row and "max_guests" in row for row in guests):
        parser.error("CSV needs household_name and max_guests columns and at least one row")
    prepared = []
    for row in guests:
        household = row["household_name"].strip()
        if not household or len(household) > 120:
            parser.error("Every household name must be 1–120 characters")
        try:
            count = int(row["max_guests"])
        except ValueError:
            parser.error("Every max_guests value must be a number")
        if count < 1 or count > 20:
            parser.error("Every max_guests value must be between 1 and 20")
        token = secrets.token_urlsafe(24)
        prepared.append((household, count, token, hashlib.sha256(token.encode()).hexdigest()))
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    with (args.output / "links.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.writer(target)
        writer.writerow(["household_name", "max_guests", "private_link"])
        for name, count, token, _ in prepared:
            writer.writerow([name, count, args.site_url.rstrip("/") + "/#invite=" + quote(token)])
    with (args.output / "invites.sql").open("w", encoding="utf-8") as target:
        for name, count, _, digest in prepared:
            target.write(f"INSERT INTO invitations(token_hash, household_name, max_guests) VALUES ({sql_string(digest)}, {sql_string(name)}, {count});\n")
    for name in ("links.csv", "invites.sql"):
        (args.output / name).chmod(0o600)
    print(f"Created {len(prepared)} private links in {args.output}. Do not commit that folder to GitHub.")


if __name__ == "__main__":
    main()
