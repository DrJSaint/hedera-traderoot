"""
Generate an HTML report of offcuts by county from traderoot.db.

Usage:
    python scripts/pipeline/offcuts_report.py "London"
  python scripts/pipeline/offcuts_report.py "London" "Surrey" "Kent" "Hertfordshire"
    python scripts/pipeline/offcuts_report.py "London" --output scripts/pipeline/reports/offcuts_london.html
"""

from __future__ import annotations

import argparse
import html
import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "database" / "traderoot.db"


def fetch_offcuts(county: str) -> tuple[list[sqlite3.Row], dict[str, int]]:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            id,
            original_id,
            name,
            type,
            website,
            phone,
            email,
            address,
            offcut_reason,
            inferred_area,
            archived_at
        FROM offcuts
        WHERE LOWER(original_county) = LOWER(?)
        ORDER BY archived_at DESC, name ASC
        """,
        (county,),
    ).fetchall()

    summary_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN offcut_reason = 'london' THEN 1 ELSE 0 END) AS london_count,
            SUM(CASE WHEN offcut_reason = 'out_of_county' THEN 1 ELSE 0 END) AS out_count
        FROM offcuts
        WHERE LOWER(original_county) = LOWER(?)
        """,
        (county,),
    ).fetchone()

    conn.close()

    summary = {
        "total": int(summary_row["total"] or 0),
        "london": int(summary_row["london_count"] or 0),
        "out_of_county": int(summary_row["out_count"] or 0),
    }
    return rows, summary


def render_rows_html(rows: list[sqlite3.Row]) -> str:
    row_html_parts: list[str] = []
    for r in rows:
        reason = r["offcut_reason"] or ""
        reason_badge = "reason-london" if reason == "london" else "reason-out"
        reason_label = "London" if reason == "london" else "Out of county"

        row_html_parts.append(
            "<tr>"
            f"<td>{r['id']}</td>"
            f"<td>{r['original_id']}</td>"
            f"<td>{html.escape(r['name'] or '')}</td>"
            f"<td>{html.escape(r['type'] or '')}</td>"
            f"<td>{html.escape(r['address'] or '')}</td>"
            f"<td><span class='reason {reason_badge}'>{reason_label}</span></td>"
            f"<td>{html.escape(r['inferred_area'] or '')}</td>"
            f"<td>{html.escape(r['archived_at'] or '')}</td>"
            "</tr>"
        )

    rows_html = "\n".join(row_html_parts) if row_html_parts else (
        "<tr><td colspan='8' class='empty'>No offcuts found for this county.</td></tr>"
    )
    return rows_html


def render_html(counties_data: list[dict]) -> str:
    county_names = [c["county"] for c in counties_data]
    escaped_county_list = ", ".join(html.escape(c) for c in county_names)
    title = "Offcuts Report"

    total = sum(c["summary"]["total"] for c in counties_data)
    london = sum(c["summary"]["london"] for c in counties_data)
    out_of_county = sum(c["summary"]["out_of_county"] for c in counties_data)

    toc_html = "".join(
        f"<a class='toc-link' href='#{html.escape(c['anchor'])}'>{html.escape(c['county'])}</a>"
        for c in counties_data
    )

    sections_html = []
    for county_data in counties_data:
        county = county_data["county"]
        summary = county_data["summary"]
        rows_html = render_rows_html(county_data["rows"])
        anchor = county_data["anchor"]

        sections_html.append(
            f"""
    <section id="{html.escape(anchor)}" class="county-section">
      <div class="section-head">
        <h2>{html.escape(county)}</h2>
        <div class="meta">total={summary['total']}, london={summary['london']}, out_of_county={summary['out_of_county']}</div>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th>Offcut ID</th>
              <th>Original ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Address</th>
              <th>Reason</th>
              <th>Inferred Area</th>
              <th>Archived At</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
            """
        )

    sections_joined = "\n".join(sections_html)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #f6f8fa;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #6b7280;
      --border: #e5e7eb;
      --accent: #0f766e;
      --warn: #b45309;
      --danger: #b91c1c;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Segoe UI, Arial, sans-serif;
    }}
    .wrap {{
      max-width: 1200px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .header {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 24px;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
    }}
    .toc {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .toc-link {{
      display: inline-block;
      text-decoration: none;
      color: var(--accent);
      background: #ecfeff;
      border: 1px solid #a5f3fc;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .stat {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
    }}
    .stat .label {{
      color: var(--muted);
      font-size: 13px;
    }}
    .stat .value {{
      font-size: 22px;
      font-weight: 700;
      margin-top: 4px;
    }}
    .table-card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}
    .county-section {{
      margin-top: 18px;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
      margin: 0 0 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    thead th {{
      text-align: left;
      background: #f3f4f6;
      color: #111827;
      padding: 10px;
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tbody td {{
      padding: 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    tbody tr:hover {{
      background: #f9fafb;
    }}
    .reason {{
      display: inline-block;
      font-size: 12px;
      font-weight: 600;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid transparent;
    }}
    .reason-london {{
      color: var(--warn);
      background: #fff7ed;
      border-color: #fed7aa;
    }}
    .reason-out {{
      color: var(--danger);
      background: #fef2f2;
      border-color: #fecaca;
    }}
    .empty {{
      color: var(--muted);
      text-align: center;
      padding: 18px;
    }}
    @media (max-width: 900px) {{
      .stats {{ grid-template-columns: 1fr; }}
      .table-card {{ overflow-x: auto; }}
      table {{ min-width: 950px; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <h1>{title}</h1>
      <div class="meta">Generated from database/offcuts for original county set: <strong>{escaped_county_list}</strong></div>
      <div class="toc">{toc_html}</div>
    </div>

    <div class="stats">
      <div class="stat">
        <div class="label">Total Offcuts (Selected Counties)</div>
        <div class="value">{total}</div>
      </div>
      <div class="stat">
        <div class="label">London Relabelled (Selected Counties)</div>
        <div class="value">{london}</div>
      </div>
      <div class="stat">
        <div class="label">Out Of County (Selected Counties)</div>
        <div class="value">{out_of_county}</div>
      </div>
    </div>

    {sections_joined}
  </div>
</body>
</html>
"""


def default_output_path(counties: list[str]) -> Path:
    root = Path(__file__).resolve().parents[2]
    if len(counties) == 1:
        safe = counties[0].strip().lower().replace(" ", "_")
        return root / "scripts" / "pipeline" / "reports" / f"offcuts_{safe}.html"
    return root / "scripts" / "pipeline" / "reports" / "offcuts_combined.html"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate county offcuts HTML report")
    parser.add_argument("counties", nargs="+", help="One or more county names, e.g. London Surrey Kent")
    parser.add_argument("--output", help="Optional output path for HTML report")
    args = parser.parse_args()

    counties_data = []
    for county in args.counties:
        rows, summary = fetch_offcuts(county)
        anchor = county.strip().lower().replace(" ", "-")
        counties_data.append({
            "county": county,
            "anchor": anchor,
            "rows": rows,
            "summary": summary,
        })

    out_path = Path(args.output) if args.output else default_output_path(args.counties)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report_html = render_html(counties_data)
    out_path.write_text(report_html, encoding="utf-8")

    print(f"Report written: {out_path}")
    for county_data in counties_data:
        county = county_data["county"]
        summary = county_data["summary"]
        print(
            f"Summary for {county}: total={summary['total']}, "
            f"london={summary['london']}, out_of_county={summary['out_of_county']}"
        )


if __name__ == "__main__":
    main()
