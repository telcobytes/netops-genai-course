"""
nb_viz.py — small HTML renderers for the Colab notebooks.

Notebooks can render real HTML, which is the one thing a terminal can't do. These
helpers exist so the notebooks stay about the lesson rather than about markup, and
so every notebook renders the same way.

Nothing here is required to run the course — the scripts in the module folders
print the same information as text.
"""

from html import escape


def _wrap(inner: str) -> str:
    return (
        "<div style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;font-size:13px;"
        "line-height:1.45;color:#0B1F3A\">" + inner + "</div>"
    )


def table(rows, columns=None, highlight=None, caption=""):
    """Render a list of dicts as a table. `highlight` is fn(row, col) -> bool."""
    if not rows:
        return _wrap("<em>no rows</em>")
    columns = columns or list(rows[0].keys())
    head = "".join(
        f"<th style='text-align:left;padding:6px 10px;border-bottom:2px solid #12B4C4;"
        f"white-space:nowrap'>{escape(str(c))}</th>" for c in columns)
    body = []
    for r in rows:
        cells = []
        for c in columns:
            hot = highlight(r, c) if highlight else False
            style = ("padding:5px 10px;border-bottom:1px solid #E3E8EF;" +
                     ("background:#FDE8E8;color:#B42318;font-weight:600" if hot else ""))
            cells.append(f"<td style='{style}'>{escape(str(r.get(c, '')))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    cap = (f"<div style='margin:0 0 6px;font-weight:600'>{escape(caption)}</div>"
           if caption else "")
    return _wrap(cap + "<table style='border-collapse:collapse;width:100%'>"
                 f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>")


def score_bars(pairs, caption="Similarity to the query"):
    """pairs: [(label, score_0_to_1, snippet)] — shows WHY a chunk ranked where it did."""
    if not pairs:
        return _wrap("<em>nothing to show</em>")
    top = max(s for _, s, _ in pairs) or 1.0
    rows = []
    for i, (label, score, snippet) in enumerate(pairs):
        pct = max(2.0, 100.0 * score / top)
        colour = "#12B4C4" if i == 0 else "#9AA7B8"
        rows.append(
            f"<div style='margin:0 0 10px'>"
            f"<div style='display:flex;justify-content:space-between;font-weight:600'>"
            f"<span>{escape(label)}</span><span>{score:.3f}</span></div>"
            f"<div style='background:#EEF1F5;border-radius:3px;height:8px;margin:3px 0'>"
            f"<div style='width:{pct:.1f}%;background:{colour};height:8px;border-radius:3px'></div></div>"
            f"<div style='color:#5B6B80;font-size:12px'>{escape(snippet[:130])}…</div></div>")
    return _wrap(f"<div style='margin:0 0 8px;font-weight:600'>{escape(caption)}</div>"
                 + "".join(rows))


def trace(steps, caption="Agent trace"):
    """steps: [{'thought':..,'action':..,'observation':..}] as a readable timeline."""
    blocks = []
    for i, s in enumerate(steps, 1):
        blocks.append(
            f"<div style='border-left:3px solid #12B4C4;padding:0 0 10px 12px;margin:0 0 4px'>"
            f"<div style='font-weight:700;color:#12B4C4'>STEP {i}</div>"
            + (f"<div><b>Thought</b> {escape(str(s['thought']))}</div>" if s.get('thought') else "")
            + (f"<div><b>Action</b> <code style='background:#EEF1F5;padding:1px 5px;"
               f"border-radius:3px'>{escape(str(s['action']))}</code></div>" if s.get('action') else "")
            + (f"<div style='color:#5B6B80'><b>Observation</b> "
               f"{escape(str(s['observation'])[:220])}</div>" if s.get('observation') else "")
            + "</div>")
    return _wrap(f"<div style='margin:0 0 8px;font-weight:600'>{escape(caption)}</div>"
                 + "".join(blocks))
