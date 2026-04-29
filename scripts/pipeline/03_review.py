"""
Stage 3 — Review enriched results and approve for import.

Usage:
    python scripts/pipeline/03_review.py             # show summary + write MD report
    python scripts/pipeline/03_review.py "Surrey"    # one county
    python scripts/pipeline/03_review.py approve     # approve all relevant + confident (>=0.7)
    python scripts/pipeline/03_review.py approve "Surrey"

Writes a markdown report to scripts/pipeline/review_<county>.md for easy reading.
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from scripts.pipeline.staging_db import init_db, get_connection

CONFIDENCE_THRESHOLD = 0.7
REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def show(county: str | None = None):
    init_db()
    conn = get_connection()

    query = """
        SELECT r.name, r.address, r.website,
               e.relevant, e.supplier_type, e.trade_only, e.trade_only_haiku,
               e.categories, e.confidence, e.notes, e.approved,
               r.search_county
        FROM enriched e
        JOIN raw_places r ON r.place_id = e.place_id
        WHERE 1=1
    """
    params = []
    if county:
        query += " AND r.search_county = ?"
        params.append(county)
    query += " ORDER BY e.relevant DESC, e.confidence DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No enriched records found.")
        return

    relevant   = [r for r in rows if r["relevant"]]
    irrelevant = [r for r in rows if not r["relevant"]]
    approved   = [r for r in rows if r["approved"]]
    trade_yes  = [r for r in relevant if r["trade_only"]]
    trade_no   = [r for r in relevant if not r["trade_only"]]
    flipped    = [r for r in relevant if r["trade_only_haiku"] is not None and r["trade_only"] != r["trade_only_haiku"]]

    # ── Terminal summary ──────────────────────────────────────────────────────
    print(f"\n{'-'*80}")
    print(f"  Total: {len(rows)}   Relevant: {len(relevant)}   "
          f"Irrelevant: {len(irrelevant)}   Approved: {len(approved)}")
    trade_pct = round(100 * len(trade_yes) / len(relevant)) if relevant else 0
    print(f"  Trade yes: {len(trade_yes)}   Trade no: {len(trade_no)}   ({trade_pct}% trade)   Sonnet flips: {len(flipped)}")
    print(f"{'-'*80}")
    type_counts = Counter(r["supplier_type"] for r in relevant if r["supplier_type"])
    for stype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        t_yes = sum(1 for r in relevant if r["supplier_type"] == stype and r["trade_only"])
        t_no  = count - t_yes
        print(f"  {stype:<22} {count}   (trade: {t_yes} yes / {t_no} no)")
    print(f"{'-'*80}\n")

    # ── HTML report ───────────────────────────────────────────────────────────
    label     = (county or "all").replace(" ", "_").lower()
    html_path = os.path.join(REPORT_DIR, f"review_{label}.html")

    TYPE_COLOURS = {
        "nursery":          "#2d9e4e",
        "garden_centre":    "#e63f8a",
        "hard_landscaper":  "#d23232",
        "soils_aggregates": "#c8860a",
        "timber":           "#7b4f2e",
        "furniture":        "#4169e1",
        "tools":            "#e07b00",
        "lighting":         "#8a2be2",
        "other":            "#888888",
    }

    def type_badge(stype):
        colour = TYPE_COLOURS.get(stype, "#888")
        return f'<span style="background:{colour};color:#fff;padding:2px 8px;border-radius:10px;font-size:0.8em;white-space:nowrap">{stype}</span>'

    def conf_bar(conf):
        pct   = int(conf * 100)
        colour = "#2d9e4e" if pct >= 80 else "#c8860a" if pct >= 60 else "#d23232"
        return (f'<div style="display:flex;align-items:center;gap:6px">'
                f'<div style="width:60px;background:#eee;border-radius:4px;height:8px">'
                f'<div style="width:{pct}%;background:{colour};height:8px;border-radius:4px"></div></div>'
                f'<span style="font-size:0.85em">{pct}%</span></div>')

    def row_html(i, r, relevant=True):
        name    = (r["name"] or "").replace("<", "&lt;")
        stype   = r["supplier_type"] or "other"
        trade   = "yes" if r["trade_only"] else "no"
        addr    = (r["address"] or "").replace("<", "&lt;")
        notes   = (r["notes"] or "").replace("<", "&lt;")
        website = r["website"] or ""
        appr    = "&#10003;" if r["approved"] else ""
        name_td = f'<a href="{website}" target="_blank">{name}</a>' if website else name
        bg      = "#fff" if i % 2 == 0 else "#f9f9f9"
        if not relevant:
            bg = "#fff8f8"
        conf_val = int(r["confidence"] * 100)

        haiku = r["trade_only_haiku"]
        flipped = haiku is not None and r["trade_only"] != haiku
        if flipped:
            if r["trade_only"]:
                flip_badge = ' <span title="Haiku said no-trade" style="background:#2d9e4e;color:#fff;font-size:0.7em;padding:1px 5px;border-radius:8px;vertical-align:middle">+trade</span>'
            else:
                flip_badge = ' <span title="Haiku said trade" style="background:#c0392b;color:#fff;font-size:0.7em;padding:1px 5px;border-radius:8px;vertical-align:middle">-trade</span>'
        else:
            flip_badge = ""

        data_flip = "true" if flipped else "false"
        return (f'<tr style="background:{bg}" data-type="{stype}" data-trade="{trade}" data-conf="{conf_val}" data-flip="{data_flip}">'
                f'<td style="color:#999;width:36px">{i}</td>'
                f'<td>{name_td}</td>'
                f'<td>{type_badge(stype)}</td>'
                f'<td style="text-align:center;color:{"#2d9e4e" if trade=="yes" else "#999"}">{trade}{flip_badge}</td>'
                f'<td data-val="{conf_val}">{conf_bar(r["confidence"])}</td>'
                f'<td style="text-align:center;color:#2d9e4e;font-size:1.1em">{appr}</td>'
                f'<td style="color:#666;font-size:0.85em">{addr}</td>'
                f'<td style="color:#555;font-size:0.85em">{notes}</td>'
                f'</tr>\n')

    summary_rows = "".join(
        f'<tr><td>{type_badge(t)}</td><td style="text-align:right;padding-left:12px">{c}</td></tr>'
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    )

    relevant_rows   = "".join(row_html(i, r, True)  for i, r in enumerate(relevant, 1))
    irrelevant_rows = "".join(row_html(i, r, False) for i, r in enumerate(irrelevant, 1))

    all_types = sorted(set(r["supplier_type"] or "other" for r in relevant))
    type_options = '<option value="">All types</option>' + "".join(
        f'<option value="{t}">{t}</option>' for t in all_types
    )
    th = 'style="background:#2c3e50;color:#fff;padding:8px 12px;text-align:left;font-weight:600;cursor:pointer;user-select:none"'
    irrelevant_section = ""
    if irrelevant:
        irrelevant_section = f"""
        <h2 style="margin-top:40px;color:#c0392b">Irrelevant — not imported ({len(irrelevant)})</h2>
        <table style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:0.9em">
          <thead><tr>
            <th {th}>#</th><th {th}>Name</th><th {th}>Type</th>
            <th {th}>Conf</th><th {th}>Address</th><th {th}>Notes</th>
          </tr></thead>
          <tbody>{''.join(row_html(i, r, False) for i, r in enumerate(irrelevant, 1))}</tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Review — {county or 'All Counties'}</title>
  <style>
    body {{ font-family: sans-serif; max-width: 1400px; margin: 0 auto; padding: 24px; color: #333; }}
    h1 {{ color: #2c3e50; }} h2 {{ color: #2c3e50; }}
    table {{ border-collapse: collapse; width: 100%; }}
    td, th {{ padding: 8px 12px; vertical-align: middle; }}
    tr:hover {{ background: #f0f4ff !important; }}
    a {{ color: #2980b9; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
    .stat {{ display:inline-block;background:#f0f0f0;border-radius:6px;padding:8px 16px;margin:4px;font-size:0.95em; }}
    .stat strong {{ font-size:1.4em;display:block; }}
    .filters {{ display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0;padding:12px 16px;background:#f8f9fa;border-radius:8px; }}
    .filters label {{ font-size:0.9em;color:#555; }}
    .filters select {{ padding:5px 10px;border:1px solid #ddd;border-radius:4px;font-size:0.9em; }}
    .filters .count {{ margin-left:auto;font-size:0.85em;color:#888; }}
    th.sortable:after {{ content:" ↕";opacity:0.4;font-size:0.8em; }}
    th.sort-asc:after {{ content:" ↑";opacity:1; }}
    th.sort-desc:after {{ content:" ↓";opacity:1; }}
  </style>
</head>
<body>
  <h1>Pipeline Review &mdash; {county or 'All Counties'}</h1>
  <p style="color:#888">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

  <div>
    <div class="stat"><strong>{len(rows)}</strong>Total</div>
    <div class="stat" style="background:#e8f5e9"><strong style="color:#2d9e4e">{len(relevant)}</strong>Relevant</div>
    <div class="stat" style="background:#fff3e0"><strong style="color:#c8860a">{len(irrelevant)}</strong>Irrelevant</div>
    <div class="stat" style="background:#e3f2fd"><strong style="color:#1565c0">{len(approved)}</strong>Approved</div>
    <div class="stat" style="background:#f3e5f5"><strong style="color:#6a1b9a">{len(trade_yes)}</strong>Trade yes</div>
    <div class="stat" style="background:#fce4ec"><strong style="color:#880e4f">{len(trade_no)}</strong>Trade no</div>
    <div class="stat" style="background:#ede7f6"><strong style="color:#4527a0">{round(100*len(trade_yes)/len(relevant)) if relevant else 0}%</strong>Trade rate</div>
    <div class="stat" style="background:#fff8e1"><strong style="color:#e65100">{len(flipped)}</strong>Sonnet flips</div>
  </div>

  <h2 style="margin-top:32px">By Type</h2>
  <table style="width:auto;border-collapse:collapse;font-family:sans-serif">
    <tbody>{summary_rows}</tbody>
  </table>

  <h2 style="margin-top:32px">Relevant Suppliers ({len(relevant)})</h2>

  <div class="filters">
    <label>Type <select id="filter-type" onchange="applyFilters()">{type_options}</select></label>
    <label>Trade <select id="filter-trade" onchange="applyFilters()">
      <option value="">All</option>
      <option value="yes">Trade yes</option>
      <option value="no">Trade no</option>
    </select></label>
    <label>Sonnet flips <select id="filter-flip" onchange="applyFilters()">
      <option value="">All</option>
      <option value="true">Flipped only</option>
    </select></label>
    <span class="count" id="filter-count"></span>
  </div>

  <table id="relevant-table" style="width:100%;border-collapse:collapse;font-family:sans-serif;font-size:0.9em">
    <thead><tr>
      <th {th}>#</th>
      <th {th} class="sortable" data-col="1">Name</th>
      <th {th} class="sortable" data-col="2">Type</th>
      <th {th} class="sortable" data-col="3">Trade</th>
      <th {th} class="sortable" data-col="4">Confidence</th>
      <th {th}>Approved</th>
      <th {th}>Address</th>
      <th {th}>Notes</th>
    </tr></thead>
    <tbody id="relevant-tbody">{relevant_rows}</tbody>
  </table>

  {irrelevant_section}

<script>
  function applyFilters() {{
    const typeVal  = document.getElementById('filter-type').value;
    const tradeVal = document.getElementById('filter-trade').value;
    const flipVal  = document.getElementById('filter-flip').value;
    const rows     = document.querySelectorAll('#relevant-tbody tr');
    let visible = 0;
    rows.forEach(r => {{
      const show = (!typeVal  || r.dataset.type  === typeVal) &&
                   (!tradeVal || r.dataset.trade === tradeVal) &&
                   (!flipVal  || r.dataset.flip  === flipVal);
      r.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    document.getElementById('filter-count').textContent =
      visible === rows.length ? '' : visible + ' of ' + rows.length + ' shown';
  }}

  // Sortable columns
  let sortCol = null, sortDir = 1;
  document.querySelectorAll('th.sortable').forEach(th => {{
    th.addEventListener('click', () => {{
      const col = +th.dataset.col;
      if (sortCol === col) {{ sortDir *= -1; }}
      else {{ sortCol = col; sortDir = 1; }}
      document.querySelectorAll('th.sortable').forEach(h => {{
        h.classList.remove('sort-asc','sort-desc');
      }});
      th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');

      const tbody = document.getElementById('relevant-tbody');
      const rows  = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((a, b) => {{
        let av = a.cells[col].innerText.trim().toLowerCase();
        let bv = b.cells[col].innerText.trim().toLowerCase();
        // Confidence column — sort by numeric data-val
        if (col === 4) {{
          av = +a.cells[col].dataset.val;
          bv = +b.cells[col].dataset.val;
          return (av - bv) * sortDir;
        }}
        return av < bv ? -sortDir : av > bv ? sortDir : 0;
      }});
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});
</script>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report written to: {html_path}\n")


def approve(county: str | None = None):
    init_db()
    conn = get_connection()

    query = """
        UPDATE enriched SET approved = 1
        WHERE relevant = 1
          AND confidence >= ?
          AND approved  = 0
          AND place_id IN (SELECT place_id FROM raw_places WHERE 1=1
    """
    params = [CONFIDENCE_THRESHOLD]
    if county:
        query += " AND search_county = ?"
        params.append(county)
    query += ")"

    cur = conn.execute(query, params)
    conn.commit()
    print(f"Approved {cur.rowcount} records (confidence >= {CONFIDENCE_THRESHOLD:.0%}).")
    conn.close()


if __name__ == "__main__":
    cmd    = sys.argv[1] if len(sys.argv) > 1 else "show"
    county = sys.argv[2] if len(sys.argv) > 2 else (sys.argv[1] if cmd not in ("show", "approve") else None)

    if cmd == "approve":
        county = sys.argv[2] if len(sys.argv) > 2 else None
        approve(county)
    else:
        show(cmd if cmd != "show" else None)
