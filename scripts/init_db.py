"""Create (or upgrade) the local DuckDB database.

    python scripts/init_db.py                  # -> data/tennis.duckdb
    python scripts/init_db.py --db other.duckdb
"""
import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src" / "mytenniscoach" / "schema.sql"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / "data" / "tennis.duckdb"))
    args = ap.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    con.execute(SCHEMA.read_text(encoding="utf-8"))
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    con.close()
    print(f"Database ready: {db_path}")
    print("Tables/views:", ", ".join(tables))


if __name__ == "__main__":
    main()
