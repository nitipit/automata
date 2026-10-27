"""Task-local deterministic exporter; not an exam runner or Automata tool mock."""

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    rows = json.loads(args.rows.read_text())
    columns = config.get("columns")
    delimiter = config.get("delimiter")
    if columns != ["id", "status"] or delimiter != "\t":
        parser.error("config requires columns ['id', 'status'] and a tab delimiter")
    if not isinstance(rows, list) or not all(
        isinstance(row, dict)
        and all(isinstance(row.get(key), str) for key in columns)
        for row in rows
    ):
        parser.error("rows must be objects with string id/status values")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.writer(stream, delimiter=delimiter, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows([row[key] for key in columns] for row in rows)
    print(f"wrote {len(rows)} records to {args.output}")


if __name__ == "__main__":
    main()
