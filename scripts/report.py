"""Print statistics from the database.

    python scripts/report.py                 # all sessions, latest first
    python scripts/report.py --session 3     # one session in detail
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import db  # noqa: E402


def table(con, sql, params=()):
    cur = con.execute(sql, list(params))
    cols = [d[0] for d in cur.description]
    rows = [["" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v)) for v in r] for r in cur.fetchall()]
    widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)))
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--session", type=int)
    args = ap.parse_args()
    con = db.connect(args.db)

    if args.session is None:
        print("Sessions\n")
        table(con, """
            SELECT se.session_id AS id, se.played_on, se.kind, se.player, se.opponent,
                   round(se.duration_s) AS seconds,
                   count(DISTINCT p.point_id) AS rallies, count(s.shot_id) AS shots
            FROM sessions se
            LEFT JOIN points p USING (session_id)
            LEFT JOIN shots s ON s.point_id = p.point_id
            GROUP BY ALL ORDER BY se.session_id DESC""")
        print("Strokes across all sessions\n")
        where, params = "", ()
    else:
        where, params = "WHERE session_id = ?", (args.session,)
        print(f"Session {args.session}: rallies\n")
        table(con, f"SELECT seq AS rally, server, rally_length AS shots, winner, end_reason FROM points {where} ORDER BY seq", params)
        print("Strokes\n")

    table(con, f"""
        SELECT hitter, stroke, count(*) AS shots,
               round(100 * avg(CASE WHEN in_court THEN 1.0 WHEN in_court = false THEN 0.0 END)) AS in_pct,
               round(avg(speed_kmh)) AS avg_kmh, round(max(speed_kmh)) AS max_kmh,
               round(100 * avg(CASE WHEN depth = 'deep' THEN 1.0 WHEN depth IS NOT NULL THEN 0.0 END)) AS deep_pct,
               round(100 * avg(CASE WHEN direction = 'cross' THEN 1.0 WHEN direction IS NOT NULL THEN 0.0 END)) AS cross_pct,
               round(avg(confidence), 2) AS confidence
        FROM shots {where}
        GROUP BY ALL ORDER BY hitter, shots DESC""", params)

    if args.session is not None:
        print("Shots\n")
        table(con, f"""
            SELECT round(t_s, 2) AS t_s, hitter, stroke, round(bounce_x_m, 1) AS bounce_x, round(bounce_y_m, 1) AS bounce_y,
                   in_court, round(speed_kmh) AS kmh, direction, depth, outcome, confidence
            FROM shots {where} ORDER BY frame""", params)


if __name__ == "__main__":
    main()
