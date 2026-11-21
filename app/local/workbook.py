"""Builds the Excel workbook: one sheet per model (in the order first used) plus a comparison sheet."""
import io
import json
import re

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

COLUMNS = [
    ("#", 5), ("Model", 18), ("Model id", 22), ("Date", 17), ("Message", 44), ("Context", 24),
    ("Intended sentiment", 12), ("Polarity (-1..1)", 10), ("Confidence (0..1)", 10), ("Sarcasm/irony", 10),
    ("Ambiguous", 10), ("Words-only sentiment", 12), ("Surface differs from intent", 12),
    ("Text/emoji relationship", 14), ("Emojis (meaning · function)", 46), ("Emotions (1-5)", 30),
    ("What it really means", 46), ("Explanation", 60), ("Other readings", 40), ("Would settle it", 30),
    ("Audience sensitivity", 40), ("Human sentiment", 12), ("Human polarity", 12), ("Human sarcasm", 12),
    ("Notes", 24), ("Full JSON", 40),
]
HEADER_FILL = PatternFill("solid", fgColor="E3E6F2")


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0


def _yn(v):
    return "yes" if v else "no"


def _row(i, rec, label):
    r = rec.get("response") or {}
    v = r.get("final_verdict") or {}
    t = r.get("text_emoji_interaction") or {}
    a = r.get("ambiguity") or {}
    return [
        i, label, rec.get("model") or "", (rec.get("createdAt") or "").replace("T", " ")[:16],
        rec.get("sentence", ""), rec.get("context") or "",
        v.get("intended_sentiment", ""), _num(v.get("polarity_score")), _num(v.get("confidence")),
        _yn(t.get("sarcasm_or_irony_detected")), _yn(a.get("is_ambiguous")),
        (r.get("text_only_analysis") or {}).get("sentiment", ""), _yn(v.get("surface_vs_intended_differs")),
        t.get("relationship", ""),
        "\n".join(f"{e.get('emoji', '')} {e.get('contextual_meaning', '')} · {e.get('function', '')}" for e in r.get("emoji_breakdown") or []),
        ", ".join(f"{e.get('emotion', '')} {e.get('intensity', '')}" for e in r.get("emotions") or []),
        v.get("one_line_summary", ""), t.get("explanation", ""),
        "\n".join(f"{x.get('reading', '')} ({round(_num(x.get('likelihood')) * 100)}%)" for x in a.get("alternative_interpretations") or []),
        a.get("context_that_would_resolve_it", ""), a.get("audience_sensitivity", ""),
        "", "", "", "", json.dumps(r, ensure_ascii=False),
    ]


def _sheet_name(label, used):
    name = re.sub(r"[\[\]:*?/\\]", "", label)[:31] or "Sheet"
    base, k = name, 2
    while name in used:
        name = f"{base[:28]} {k}"
        k += 1
    used.add(name)
    return name


def _style(ws, widths):
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    for idx, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"


def build(rows, label_for):
    """rows: oldest first. label_for(rec) -> sheet label for the model that answered."""
    wb = Workbook()
    wb.remove(wb.active)
    used = set()
    by_model = {}
    for rec in rows:
        by_model.setdefault(label_for(rec), []).append(rec)

    if not by_model:
        ws = wb.create_sheet("Analyses")
        ws.append([c for c, _ in COLUMNS])
        _style(ws, [w for _, w in COLUMNS])

    for label, recs in by_model.items():
        ws = wb.create_sheet(_sheet_name(label, used))
        ws.append([c for c, _ in COLUMNS])
        for i, rec in enumerate(recs, start=1):
            ws.append(_row(i, rec, label))
        _style(ws, [w for _, w in COLUMNS])

    if len(by_model) > 1:
        labels = list(by_model)
        by_sentence = {}
        for rec in rows:
            key = (rec.get("sentence", ""), rec.get("context") or "")
            entry = by_sentence.setdefault(key, {})
            r = rec.get("response") or {}
            v = r.get("final_verdict") or {}
            # The most recent analysis per model wins if a message was run more than once.
            entry[label_for(rec)] = (
                v.get("intended_sentiment", ""), _num(v.get("polarity_score")), _num(v.get("confidence")),
                _yn((r.get("text_emoji_interaction") or {}).get("sarcasm_or_irony_detected")),
            )
        ws = wb.create_sheet(_sheet_name("Comparison", used))
        header = ["Message", "Context"]
        for l in labels:
            header += [f"{l}: verdict", f"{l}: polarity", f"{l}: confidence", f"{l}: sarcasm"]
        header.append("Models agree")
        ws.append(header)
        for (sentence, context), entry in by_sentence.items():
            line = [sentence, context]
            for l in labels:
                line += list(entry.get(l, ("", "", "", "")))
            verdicts = {entry[l][0] for l in labels if l in entry and entry[l][0]}
            n = sum(1 for l in labels if l in entry)
            line.append("" if n < 2 else ("yes" if len(verdicts) == 1 else "no"))
            ws.append(line)
        _style(ws, [44, 20] + [14] * (len(header) - 3) + [12])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
