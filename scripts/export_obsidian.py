"""Write the tennis notes for Obsidian.

    python scripts/export_obsidian.py                  # all sessions
    python scripts/export_obsidian.py --compare 3 7    # also a note comparing session 3 with 7

Folder: "obsidian_dir" in data/player.json (for example the Tennis folder of
your vault), otherwise outputs/obsidian/Tennis. Only the notes written here are
replaced; anything else you put in the folder is left alone.

    Tennis.md                     home: latest session against the previous one and your best, records, trends
    Sessions/<date> <kind> S0003.md   one note per session: every metric as a property, the review, picture strips
    Sessions.base                 table of all sessions (Obsidian Bases): sort and filter on any metric
    Compare/*.md                  latest vs previous, vs best, vs the last-5 average, and any pair you ask for
    Metrics.md                    what every metric means and where it comes from
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import db, metrics  # noqa: E402
from mytenniscoach.metrics import BY_KEY, GROUPS, METRICS  # noqa: E402

KEY = ["first_serve_in_pct", "second_serve_in_pct", "double_faults", "points_won_pct", "winners", "unforced_errors",
       "winner_ue_ratio", "shots_before_error", "fh_in_pct", "bh_in_pct", "fh_kmh", "bh_kmh", "fh_deep_pct",
       "bh_deep_pct", "fh_net_clear_m", "bh_net_clear_m", "rally_avg", "contact_behind_m", "distance_per_point_m",
       "fh_contact_spread_m", "bh_off_hand_on_pct"]


def out_dir() -> Path:
    cfg = ROOT / "data" / "player.json"
    try:
        d = json.loads(cfg.read_text(encoding="utf-8")).get("obsidian_dir") if cfg.exists() else None
    except Exception:
        d = None
    return Path(d) if d else ROOT / "outputs" / "obsidian" / "Tennis"


def fmt(key, v) -> str:
    if v is None:
        return "–"
    u = BY_KEY[key].unit
    if u == "%":
        return f"{v:.0f} %"
    if u in ("count", "shots") and float(v).is_integer():
        return f"{int(v)}"
    if u in ("km/h", "rpm", "deg", "NTRP"):
        return f"{v:.0f} {u}" if u != "NTRP" else f"{v:.1f}"
    if u in ("m", "s"):
        return f"{v:.2f} {u}"
    return f"{v:.1f}"


def delta(key, a, b) -> str:
    """Change from b to a, with a mark when it is better or worse."""
    if a is None or b is None:
        return ""
    d = a - b
    m = BY_KEY[key]
    if abs(d) < 1e-9:
        return "="
    sign = "+" if d > 0 else "−"
    num = f"{abs(d):.0f}" if m.unit in ("%", "km/h", "rpm", "deg") else (f"{abs(d):.2f}" if m.unit in ("m", "s") else f"{abs(d):.1f}")
    mark = ""
    if m.better:
        good = (d > 0) == (m.better == "high")
        mark = " ▲" if good else " ▼"
    return f"{sign}{num}{mark}"


def val(vals, sid, key):
    d = vals.get(sid, {}).get(key)
    return None if d is None else d[0]


def enough(vals, sid, key) -> bool:
    d = vals.get(sid, {}).get(key)
    return d is not None and (d[2] == "coach" or (d[1] or 0) >= BY_KEY[key].min_n)


def title(s) -> str:
    return f"{s['played_on']} {s['kind']} S{s['session_id']:04d}"


def link(s, in_table: bool = False) -> str:
    bar = "\\|" if in_table else "|"          # a bare | would split a table cell
    return f"[[Sessions/{title(s)}{bar}{s['played_on']} {s['kind']}]]"


def compare_table(keys, cols: list[tuple[str, dict]], base: dict, vals_note=True) -> list[str]:
    """Rows: metric | base | each comparison column with its change."""
    head = "| Metric | " + " | ".join(c[0] for c in cols) + " |"
    lines = [head, "|---" * (len(cols) + 1) + "|"]
    for k in keys:
        cells = []
        for i, (_, col) in enumerate(cols):
            v = col.get(k)
            cell = fmt(k, v)
            if i > 0 and v is not None:
                ch = delta(k, cols[0][1].get(k), v)
                cell = f"{cell} ({ch})" if ch else cell
            cells.append(cell)
        if all(c == "–" for c in cells):
            continue
        lines.append(f"| {BY_KEY[k].label} | " + " | ".join(cells) + " |")
    return lines


def average(vals, sids, key):
    xs = [val(vals, s, key) for s in sids if enough(vals, s, key)]
    return sum(xs) / len(xs) if xs else None


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def session_note(s, vals, sessions, review, focus, folder: Path) -> str:
    sid = s["session_id"]
    earlier = [x for x in sessions if (x["played_on"], x["session_id"]) < (s["played_on"], sid)]
    prev = earlier[-1] if earlier else None
    props = {"date": str(s["played_on"]), "session": sid, "kind": s["kind"], "opponent": s["opponent"] or "",
             "surface": s["surface"] or "", "tags": ["tennis/session"]}
    for m in METRICS:
        v = val(vals, sid, m.key)
        if v is not None:
            props[m.key] = round(v, 2)
    fm = ["---"]
    for k, v in props.items():
        if isinstance(v, list):
            fm.append(f"{k}:")
            fm += [f"  - {x}" for x in v]
        elif isinstance(v, str):
            fm.append(f'{k}: "{v}"')
        else:
            fm.append(f"{k}: {v}")
    fm.append("---")
    body = [f"# Tennis {s['played_on']}: {s['kind']}" + (f" against {s['opponent']}" if s["opponent"] else ""), ""]
    if prev:
        body.append(f"Previous session: {link(prev)}")
        body.append("")
    if focus:
        body += ["## Priorities from the review", ""] + [f"- {f}" for f in focus.splitlines() if f.strip()] + [""]
    for g in GROUPS:
        keys = [m.key for m in METRICS if m.group == g and val(vals, sid, m.key) is not None]
        if not keys:
            continue
        body += [f"## {g}", "", "| Metric | This session | Previous | Best ever | Based on |", "|---|---|---|---|---|"]
        for k in keys:
            v = val(vals, sid, k)
            p = val(vals, prev["session_id"], k) if prev and enough(vals, prev["session_id"], k) else None
            b = metrics.best(vals, k)
            n, src = vals[sid][k][1], vals[sid][k][2]
            based = "told to the coach" if src == "coach" else (f"{n}" + ("" if enough(vals, sid, k) else ", too few to compare"))
            est = " ~" if BY_KEY[k].how == "estimate" else ""
            body.append(f"| {BY_KEY[k].label}{est} | {fmt(k, v)} | {fmt(k, p)} {delta(k, v, p)} | "
                        f"{fmt(k, b[1]) if b else '–'} | {based} |")
        body.append("")
    body.append("~ estimate from one camera: compare sessions with the same camera position.")
    body.append("")
    pics = sorted((ROOT / "outputs" / "coach" / f"session_{sid:04d}").glob("stroke_*.jpg"))
    if pics:
        dest = folder / "Attachments" / f"S{sid:04d}"
        dest.mkdir(parents=True, exist_ok=True)
        body += ["## Picture strips", ""]
        for p in pics:
            shutil.copyfile(p, dest / p.name)
            body.append(f"![[Attachments/S{sid:04d}/{p.name}]]")
        body.append("")
    if review:
        text = review.split("\n", 1)[1] if review.startswith("# ") else review
        body += ["## Review", "", text.strip(), ""]
    return "\n".join(fm + [""] + body)


def base_file() -> str:
    cols = ["file.name", "date", "kind", "opponent"] + KEY
    lines = ["filters:", "  and:", '    - file.inFolder("Tennis/Sessions")', "views:",
             "  - type: table", "    name: All sessions", "    order:"]
    lines += [f"      - {c}" for c in cols]
    lines += ["    sort:", "      - property: date", "        direction: DESC"]
    lines += ["  - type: table", "    name: Matches", "    filters:", "      and:", '        - kind == "match"',
              "    order:"] + [f"      - {c}" for c in cols]
    return "\n".join(lines) + "\n"


def metrics_note() -> str:
    how = {"auto": "measured", "estimate": "measured, one-camera estimate", "coach": "told to the coach"}
    lines = ["# Tennis metrics", "",
             "Every session stores each metric below. ▲ in a comparison means better, ▼ worse.",
             "Values resting on fewer strokes than the minimum are shown but not compared.", ""]
    for g in GROUPS:
        lines += [f"## {g}", "", "| Metric | Property | Unit | Better | Source | Min. sample | Note |",
                  "|---|---|---|---|---|---|---|"]
        for m in [m for m in METRICS if m.group == g]:
            lines.append(f"| {m.label} | `{m.key}` | {m.unit} | {m.better or '–'} | {how[m.how]} | {m.min_n} | {m.note} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--out", default=None)
    ap.add_argument("--compare", nargs=2, type=int, metavar=("A", "B"))
    args = ap.parse_args()
    folder = Path(args.out) if args.out else out_dir()
    con = db.connect(args.db)
    sessions, vals = metrics.table(con)
    if not sessions:
        print("No sessions of your own yet (pro footage is left out).")
        return
    reviews = {sid: (md, fp) for sid, md, fp in con.execute(
        "SELECT session_id, summary_md, focus_points FROM reviews WHERE scope = 'session'").fetchall()}
    con.close()
    by_id = {s["session_id"]: s for s in sessions}

    for s in sessions:
        md, fp = reviews.get(s["session_id"], (None, None))
        for old in (folder / "Sessions").glob(f"* S{s['session_id']:04d}.md"):
            old.unlink()                        # the date or kind may have been corrected
        write(folder / "Sessions" / f"{title(s)}.md", session_note(s, vals, sessions, md, fp, folder))

    last = sessions[-1]
    lid = last["session_id"]
    prev = sessions[-2] if len(sessions) > 1 else None
    best_col = {}
    for k in KEY + [m.key for m in METRICS]:
        b = metrics.best(vals, k)
        if b:
            best_col[k] = b[1]
    last_col = {m.key: val(vals, lid, m.key) for m in METRICS}
    prev_col = {m.key: val(vals, prev["session_id"], m.key) for m in METRICS
                if enough(vals, prev["session_id"], m.key)} if prev else {}
    five = [s["session_id"] for s in sessions[-6:-1]]
    avg_col = {m.key: average(vals, five, m.key) for m in METRICS} if five else {}

    all_keys = [m.key for m in METRICS]
    comps = [("Latest vs previous", [("Latest", last_col), ("Previous", prev_col)]),
             ("Latest vs best", [("Latest", last_col), ("Best ever", best_col)]),
             ("Latest vs last 5 average", [("Latest", last_col), ("Average of the 5 before", avg_col)])]
    for name, cols in comps:
        lines = [f"# {name}", "", f"Latest: {link(last)}" + (f" · previous: {link(prev)}" if prev else ""), "",
                 "Change in brackets is from the right-hand column to the latest session; ▲ better, ▼ worse.", ""]
        for g in GROUPS:
            t = compare_table([m.key for m in METRICS if m.group == g], cols, last_col)
            if len(t) > 2:
                lines += [f"## {g}", ""] + t + [""]
        write(folder / "Compare" / f"{name}.md", "\n".join(lines))
    if args.compare:
        a, b = args.compare
        if a in by_id and b in by_id:
            ca = {k: val(vals, a, k) for k in all_keys}
            cb = {k: val(vals, b, k) for k in all_keys}
            name = f"S{a:04d} vs S{b:04d}"
            lines = [f"# {by_id[a]['played_on']} vs {by_id[b]['played_on']}", "",
                     f"{link(by_id[a])} compared with {link(by_id[b])}; ▲ better, ▼ worse.", ""]
            for g in GROUPS:
                t = compare_table([m.key for m in METRICS if m.group == g],
                                  [(str(by_id[a]["played_on"]), ca), (str(by_id[b]["played_on"]), cb)], ca)
                if len(t) > 2:
                    lines += [f"## {g}", ""] + t + [""]
            write(folder / "Compare" / f"{name}.md", "\n".join(lines))
            print(f"Comparison written: Compare/{name}.md")
        else:
            print(f"Session {a} or {b} not found among your own sessions.")

    # Home note.
    home = ["# Tennis", "", f"Latest session: {link(last)}", ""]
    if lid in reviews and reviews[lid][1]:
        home += ["## Working on", ""] + [f"- {f}" for f in reviews[lid][1].splitlines() if f.strip()] + [""]
    home += ["## Latest at a glance", ""]
    home += compare_table(KEY, [("Latest", last_col), ("Previous", prev_col), ("Best ever", best_col)], last_col)
    home += ["", "## Records", "", "| Metric | Best | When |", "|---|---|---|"]
    for k in KEY:
        b = metrics.best(vals, k)
        if b:
            home.append(f"| {BY_KEY[k].label} | {fmt(k, b[1])} | {link(by_id[b[0]], True)} |")
    recent = sessions[-8:]
    home += ["", "## Trend, last sessions", "",
             "| Metric | " + " | ".join(str(s["played_on"])[5:] for s in recent) + " |",
             "|---" * (len(recent) + 1) + "|"]
    for k in KEY:
        row = [fmt(k, val(vals, s["session_id"], k)) if enough(vals, s["session_id"], k) else "–" for s in recent]
        if any(c != "–" for c in row):
            home.append(f"| {BY_KEY[k].label} | " + " | ".join(row) + " |")
    home += ["", "## More", "", "- [[Sessions.base|All sessions as a table]]",
             "- [[Compare/Latest vs previous]] · [[Compare/Latest vs best]] · [[Compare/Latest vs last 5 average]]",
             "- [[Metrics|What the metrics mean]]", ""]
    write(folder / "Tennis.md", "\n".join(home))
    write(folder / "Sessions.base", base_file())
    write(folder / "Metrics.md", metrics_note())
    print(f"Obsidian notes written: {folder} ({len(sessions)} sessions)")


if __name__ == "__main__":
    main()
