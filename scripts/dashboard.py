"""Session dashboard: one HTML file that compares any two sessions.

    python scripts/dashboard.py            -> outputs/dashboard.html

Pick a session and what to compare it with (the previous session, your best
ever, the average of the last five, or any other session). Click a metric for
its trend over all sessions. The file is self-contained: open it in any
browser, copy it anywhere. Pro footage ('reference' sessions) is left out.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mytenniscoach import db, metrics  # noqa: E402

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tennis Sessions</title>
<style>
:root{color-scheme:light;--bg:#f4f3ef;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--grid:#e1e0d9;
--a:#2a78d6;--b:#eb6834;--good:#0ca30c;--bad:#d03b3b;--hover:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#121211;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c86;--grid:#2c2c2a;--a:#3987e5;--b:#d95926;--hover:#232322}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#121211;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8d8c86;
--grid:#2c2c2a;--a:#3987e5;--b:#d95926;--hover:#232322}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1000px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 4px}p.sub{color:var(--ink2);margin:0 0 18px}
.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin-bottom:16px}
label{display:flex;flex-direction:column;font-size:12px;color:var(--ink2);gap:4px}
select{font:inherit;padding:6px 8px;border:1px solid var(--grid);border-radius:6px;background:var(--surface);color:var(--ink);max-width:100%}
.card{background:var(--surface);border:1px solid var(--grid);border-radius:10px;padding:14px;margin-bottom:16px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:12px;color:var(--ink2);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--grid)}
td{padding:6px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
td.num{text-align:right;white-space:nowrap}th.num{text-align:right}
tr.metric{cursor:pointer}tr.metric:hover{background:var(--hover)}tr.sel{background:var(--hover)}
tr.group td{font-weight:700;padding-top:14px;border-bottom:none}
.few{color:var(--muted)}.est{color:var(--muted);font-size:12px}
.chg{white-space:nowrap}.better{color:var(--good)}.worse{color:var(--bad)}
.key{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
#chart{width:100%;height:260px;display:block}#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);
border:1px solid var(--grid);border-radius:6px;padding:6px 8px;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.15);display:none}
.legend{font-size:13px;color:var(--ink2);margin-top:6px}.legend span{margin-right:14px}
.empty{color:var(--ink2)}
@media (max-width:600px){.bo,.chg .est{display:none}td,th{padding:6px 4px}main{padding:16px}}
</style></head><body><main>
<h1>Tennis sessions</h1>
<p class="sub" id="sub"></p>
<div class="controls">
 <label>Session<select id="selA"></select></label>
 <label>Compare with<select id="selB"></select></label>
 <label>Show<select id="kind"><option value="">all sessions</option><option value="match">matches</option><option value="training">trainings</option></select></label>
 <label>Metrics<select id="grp"></select></label>
</div>
<div class="card"><div id="trendTitle" style="font-weight:600"></div><svg id="chart" role="img"></svg>
<div class="legend" id="legend"></div></div>
<div class="card"><table id="tbl"></table></div>
<p class="est">~ estimate from one camera: compare sessions recorded from the same camera position.
Grey values rest on fewer strokes than the metric needs and are not compared. ▲ better, ▼ worse.</p>
</main><div id="tip"></div>
<script>
const D = __DATA__;
const M = D.metrics, BY = Object.fromEntries(M.map(m => [m.key, m]));
let selKey = D.default_metric;
const $ = id => document.getElementById(id);
const sessName = s => `${s.played_on} ${s.kind}${s.opponent ? " vs " + s.opponent : ""} (S${String(s.session_id).padStart(4, "0")})`;
function sessions() { const k = $("kind").value; return D.sessions.filter(s => !k || s.kind === k); }
function v(sid, key) { const d = (D.values[sid] || {})[key]; return d ? d[0] : null; }
function enough(sid, key) { const d = (D.values[sid] || {})[key]; return d && (d[2] === "coach" || d[1] >= BY[key].min_n); }
function fmt(key, x) {
  if (x === null || x === undefined || Number.isNaN(x)) return "–";
  const u = BY[key].unit;
  if (u === "%") return Math.round(x) + " %";
  if ((u === "count" || u === "shots") && Number.isInteger(x)) return String(x);
  if (["km/h", "rpm", "deg"].includes(u)) return Math.round(x) + " " + u;
  if (u === "m" || u === "s") return x.toFixed(2) + " " + u;
  return x.toFixed(1);
}
function best(key, pool) {
  const m = BY[key]; if (!m.better) return null;
  let out = null;
  for (const s of pool) { if (!enough(s.session_id, key)) continue; const x = v(s.session_id, key);
    if (out === null || (m.better === "high" ? x > out.x : x < out.x)) out = { x, s }; }
  return out;
}
function avg(key, pool) {
  const xs = pool.filter(s => enough(s.session_id, key)).map(s => v(s.session_id, key));
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
}
function fill() {
  const ss = sessions(), A = $("selA"), B = $("selB"), keepA = A.value, keepB = B.value;
  A.innerHTML = ss.slice().reverse().map(s => `<option value="${s.session_id}">${sessName(s)}</option>`).join("");
  if ([...A.options].some(o => o.value === keepA)) A.value = keepA;
  B.innerHTML = `<option value="prev">the previous session</option><option value="best">my best ever</option>
    <option value="avg5">average of the 5 before</option><option value="avg">average of all</option>` +
    ss.slice().reverse().map(s => `<option value="${s.session_id}">${sessName(s)}</option>`).join("");
  if ([...B.options].some(o => o.value === keepB)) B.value = keepB;
}
function compareValue(key, aid, mode, pool) {
  const i = pool.findIndex(s => s.session_id === aid), before = pool.slice(0, Math.max(i, 0));
  if (mode === "prev") { const p = before[before.length - 1]; return p && enough(p.session_id, key) ? { x: v(p.session_id, key), label: p.played_on } : null; }
  if (mode === "best") { const b = best(key, pool); return b ? { x: b.x, label: b.s.played_on } : null; }
  if (mode === "avg5") { const x = avg(key, before.slice(-5)); return x === null ? null : { x, label: "avg" }; }
  if (mode === "avg") { const x = avg(key, pool); return x === null ? null : { x, label: "avg" }; }
  const sid = +mode; return enough(sid, key) ? { x: v(sid, key), label: (D.sessions.find(s => s.session_id === sid) || {}).played_on } : null;
}
function render() {
  const pool = sessions();
  if (!pool.length) { $("tbl").innerHTML = '<tr><td class="empty">No sessions of this kind yet.</td></tr>'; $("chart").innerHTML = ""; return; }
  const aid = +$("selA").value, mode = $("selB").value, grp = $("grp").value;
  const bName = $("selB").selectedOptions[0].text;
  let rows = `<tr><th>Metric</th><th class="num"><span class="key" style="background:var(--a)"></span>Session</th>
    <th class="num"><span class="key" style="background:var(--b)"></span>Compared</th><th class="num">Change</th><th class="num bo">Based on</th></tr>`;
  for (const g of D.groups) {
    if (grp && g !== grp) continue;
    const keys = M.filter(m => m.group === g && v(aid, m.key) !== null);
    if (!keys.length) continue;
    rows += `<tr class="group"><td colspan="5">${g}</td></tr>`;
    for (const m of keys) {
      const a = v(aid, m.key), ok = enough(aid, m.key), c = compareValue(m.key, aid, mode, pool);
      let chg = "";
      if (ok && c && c.x !== null) {
        const d = a - c.x;
        if (Math.abs(d) < 1e-9) chg = "=";
        else {
          const unit = m.unit, mag = ["%", "km/h", "rpm", "deg"].includes(unit) ? Math.round(Math.abs(d)) : Math.abs(d).toFixed(unit === "m" || unit === "s" ? 2 : 1);
          const sign = d > 0 ? "+" : "−";
          if (m.better) { const good = (d > 0) === (m.better === "high");
            chg = `<span class="${good ? "better" : "worse"}">${good ? "▲" : "▼"} ${sign}${mag}<span class="est"> ${good ? "better" : "worse"}</span></span>`; }
          else chg = `${sign}${mag}`;
        }
      }
      const d = D.values[aid][m.key];
      const based = d[2] === "coach" ? "told to coach" : `${d[1]}`;
      rows += `<tr class="metric${m.key === selKey ? " sel" : ""}" data-k="${m.key}"><td>${m.label}${m.how === "estimate" ? ' <span class="est">~</span>' : ""}</td>
        <td class="num${ok ? "" : " few"}">${fmt(m.key, a)}</td><td class="num">${c ? fmt(m.key, c.x) : "–"}</td>
        <td class="num chg">${chg}</td><td class="num est bo">${based}</td></tr>`;
    }
  }
  $("tbl").innerHTML = rows;
  $("tbl").querySelectorAll("tr.metric").forEach(tr => tr.onclick = () => { selKey = tr.dataset.k; render(); });
  $("sub").textContent = `${pool.length} session${pool.length === 1 ? "" : "s"} · compared with ${bName}`;
  trend(pool, aid, mode);
}
function trend(pool, aid, mode) {
  const svg = $("chart"), key = selKey, m = BY[key];
  const pts = pool.filter(s => enough(s.session_id, key)).map(s => ({ s, x: v(s.session_id, key) }));
  $("trendTitle").textContent = `${m.label}${m.unit && !["count", "shots", "ratio"].includes(m.unit) ? " (" + m.unit + ")" : ""} over time`
    + (m.better ? (m.better === "high" ? " · higher is better" : " · lower is better") : "");
  const W = svg.clientWidth || 700, H = 260, L = 52, R = 16, T = 14, B = 34;
  if (!pts.length) { svg.innerHTML = `<text x="${L}" y="40" fill="var(--ink2)">Not enough data for this metric yet.</text>`; $("legend").innerHTML = ""; return; }
  let lo = Math.min(...pts.map(p => p.x)), hi = Math.max(...pts.map(p => p.x));
  if (m.unit === "%") { lo = Math.min(lo, 0); hi = Math.max(hi, 100); }
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08; lo -= m.unit === "%" ? 0 : pad; hi += m.unit === "%" ? 0 : pad;
  const X = i => pts.length === 1 ? (L + W - R) / 2 : L + i * (W - L - R) / (pts.length - 1);
  const Y = x => T + (hi - x) * (H - T - B) / (hi - lo);
  let g = "";
  for (let k = 0; k <= 4; k++) { const val = lo + k * (hi - lo) / 4, y = Y(val);
    g += `<line x1="${L}" x2="${W - R}" y1="${y}" y2="${y}" stroke="var(--grid)" stroke-width="1"/>
      <text x="${L - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="var(--ink2)">${fmt(key, val).replace(" " + m.unit, "")}</text>`; }
  const step = Math.ceil(pts.length / 8);
  pts.forEach((p, i) => { if (i % step === 0 || i === pts.length - 1)
    g += `<text x="${X(i)}" y="${H - 12}" text-anchor="middle" font-size="11" fill="var(--ink2)">${p.s.played_on.slice(5)}</text>`; });
  if (pts.length > 1) g += `<polyline fill="none" stroke="var(--a)" stroke-width="2" points="${pts.map((p, i) => X(i) + "," + Y(p.x)).join(" ")}"/>`;
  const c = compareValue(key, aid, mode, pool);
  if (c && ["best", "avg", "avg5"].includes(mode))
    g += `<line x1="${L}" x2="${W - R}" y1="${Y(c.x)}" y2="${Y(c.x)}" stroke="var(--b)" stroke-width="2" stroke-dasharray="5 4"/>`;
  const bId = mode === "prev" ? (() => { const i = pool.findIndex(s => s.session_id === aid); return i > 0 ? pool[i - 1].session_id : null; })() : +mode;
  pts.forEach((p, i) => {
    const isA = p.s.session_id === aid, isB = p.s.session_id === bId;
    const col = isB && !isA ? "var(--b)" : "var(--a)", r = isA || isB ? 6 : 4;
    g += `<circle cx="${X(i)}" cy="${Y(p.x)}" r="${r}" fill="${col}" stroke="var(--surface)" stroke-width="2"/>
      <circle class="hit" data-i="${i}" cx="${X(i)}" cy="${Y(p.x)}" r="14" fill="transparent"/>`;
  });
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = g;
  svg.querySelectorAll(".hit").forEach(h => {
    h.onmousemove = e => { const p = pts[+h.dataset.i], t = $("tip");
      t.innerHTML = `<b>${sessName(p.s)}</b><br>${fmt(key, p.x)}`; t.style.display = "block";
      t.style.left = Math.min(e.clientX + 12, innerWidth - 220) + "px"; t.style.top = e.clientY + 12 + "px"; };
    h.onmouseleave = () => $("tip").style.display = "none";
    h.onclick = () => { $("selA").value = pts[+h.dataset.i].s.session_id; render(); };
  });
  $("legend").innerHTML = `<span><span class="key" style="background:var(--a)"></span>each session (larger dot: selected)</span>` +
    (c ? `<span><span class="key" style="background:var(--b)"></span>${$("selB").selectedOptions[0].text}</span>` : "");
}
$("grp").innerHTML = '<option value="">all</option>' + D.groups.map(g => `<option>${g}</option>`).join("");
["selA", "selB", "grp"].forEach(id => $(id).onchange = render);
$("kind").onchange = () => { fill(); render(); };
addEventListener("resize", () => render());
fill(); render();
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(db.DEFAULT_DB))
    ap.add_argument("--out", default=str(ROOT / "outputs" / "dashboard.html"))
    args = ap.parse_args()
    con = db.connect(args.db)
    sessions, vals = metrics.table(con)
    con.close()
    data = {
        "sessions": [{"session_id": s["session_id"], "played_on": str(s["played_on"]), "kind": s["kind"],
                      "opponent": s["opponent"], "surface": s["surface"]} for s in sessions],
        "values": {str(k): v for k, v in vals.items()},
        "metrics": [{"key": m.key, "group": m.group, "label": m.label, "unit": m.unit, "better": m.better,
                     "how": m.how, "min_n": m.min_n} for m in metrics.METRICS],
        "groups": metrics.GROUPS,
        "default_metric": "fh_in_pct",
    }
    html = PAGE.replace("__DATA__", json.dumps(data, default=float))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"Dashboard written: {args.out} ({len(sessions)} sessions)")


if __name__ == "__main__":
    main()
