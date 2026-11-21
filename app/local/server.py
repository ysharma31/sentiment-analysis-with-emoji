"""Emoji Sentiment Lab, local edition.

Run:  python app/local/server.py   then open http://127.0.0.1:5000

Analyses are stored in app/local/data/analyses.json, and app/local/data/analyses.xlsx is
rewritten after every change (one sheet per model, plus a comparison sheet).
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

import providers
import workbook

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DATA = HERE / "data"
ROWS_FILE = DATA / "analyses.json"
XLSX_FILE = DATA / "analyses.xlsx"

load_dotenv(HERE / ".env")
CONFIG = json.loads((HERE / "models.json").read_text(encoding="utf-8"))
PROVIDERS = CONFIG["providers"]
MODELS = {m["id"]: m for m in CONFIG["models"]}

_prompt_md = (ROOT / "prompts" / "sentiment_analysis_prompt.md").read_text(encoding="utf-8")
SYSTEM_PROMPT = re.search(r"## System Prompt\s*```\n(.*?)\n```", _prompt_md, re.S).group(1)

app = Flask(__name__)
_lock = threading.Lock()


# ---------- storage ----------

def _seed_rows():
    """Start the sheet with the 25 test-set analyses already in the repo (written by Claude Opus 5.5)."""
    src = ROOT / "evaluation" / "results" / "responses.jsonl"
    rows = []
    if src.exists():
        for line in src.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            rows.append({
                "id": f"seed-{r['id']:02d}", "sentence": r["response"]["input"], "context": "",
                "createdAt": f"2026-11-21T09:{r['id']:02d}:00.000Z", "source": "seed", "category": r["category"],
                "model": "claude-opus-5-5", "modelRequested": "claude-opus-5-5", "response": r["response"],
            })
    return rows


def load_rows():
    if not ROWS_FILE.exists():
        DATA.mkdir(exist_ok=True)
        save_rows(_seed_rows())
    return json.loads(ROWS_FILE.read_text(encoding="utf-8"))


def label_for(rec):
    m = MODELS.get(rec.get("model"))
    return m["label"] if m else (rec.get("model") or "Unknown model")


def save_rows(rows):
    DATA.mkdir(exist_ok=True)
    tmp = ROWS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ROWS_FILE)
    try:
        XLSX_FILE.write_bytes(workbook.build(_oldest_first(rows), label_for))
    except PermissionError:
        # Usually means the workbook is open in Excel. The data is safe in analyses.json;
        # the xlsx catches up on the next save or via the Download button.
        app.logger.warning("analyses.xlsx is open elsewhere; it will be updated on the next save.")


def _oldest_first(rows):
    return sorted(rows, key=lambda r: r.get("createdAt", ""))


# ---------- analysis ----------

def parse_json(text):
    t = re.sub(r"^```(?:json)?\s*|```\s*$", "", text.strip(), flags=re.I)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b < a:
        raise providers.ProviderError("The reply didn't contain JSON.", "bad_reply")
    try:
        data = json.loads(t[a:b + 1])
    except json.JSONDecodeError:
        raise providers.ProviderError("The reply wasn't valid JSON.", "bad_reply")
    if not isinstance(data, dict) or "final_verdict" not in data:
        raise providers.ProviderError("The reply didn't match the expected format.", "bad_reply")
    return data


@app.post("/api/analyze")
def analyze():
    body = request.get_json(force=True)
    sentence = (body.get("sentence") or "").strip()
    context = (body.get("context") or "").strip()
    model = MODELS.get(body.get("model"))
    if not sentence:
        return jsonify(error="Type a message to analyze."), 400
    if not model:
        return jsonify(error="Unknown model. Pick one from the list."), 400
    user = (
        "Analyze the sentiment of the following message.\n\n"
        f'Message: "{sentence}"\n\n'
        f"Optional context (leave blank if none): {context}\n\n"
        "Respond with only the JSON object."
    )
    try:
        text = providers.complete(PROVIDERS[model["provider"]], model["id"], SYSTEM_PROMPT, user)
        response = parse_json(text)
    except providers.ProviderError as e:
        return jsonify(error=str(e), code=e.code), 502
    response.setdefault("input", sentence)
    return jsonify(response=response, model=model["id"], modelRequested=model["id"], modelTier="")


# ---------- rows ----------

@app.get("/api/rows")
def get_rows():
    with _lock:
        rows = load_rows()
    return jsonify(sorted(rows, key=lambda r: r.get("createdAt", ""), reverse=True))


@app.post("/api/rows")
def add_row():
    rec = request.get_json(force=True)
    rec["id"] = uuid.uuid4().hex[:12]
    rec.setdefault("createdAt", datetime.now(timezone.utc).isoformat())
    with _lock:
        rows = load_rows()
        rows.append(rec)
        save_rows(rows)
    return jsonify(id=rec["id"])


@app.delete("/api/rows/<row_id>")
def delete_row(row_id):
    with _lock:
        rows = [r for r in load_rows() if r.get("id") != row_id]
        save_rows(rows)
    return jsonify(ok=True)


@app.get("/api/export.xlsx")
def export():
    with _lock:
        rows = load_rows()
    data = workbook.build(_oldest_first(rows), label_for)
    name = f"emoji-sentiment-analyses-{datetime.now():%Y-%m-%d}.xlsx"
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- models ----------

@app.get("/api/config")
def config():
    return jsonify(models=[
        {"id": m["id"], "label": m["label"], "provider": m["provider"],
         "providerLabel": PROVIDERS[m["provider"]]["label"], "available": providers.has_key(PROVIDERS[m["provider"]])}
        for m in CONFIG["models"]
    ])


@app.get("/api/check")
def check():
    results, cache = [], {}
    for m in CONFIG["models"]:
        p = PROVIDERS[m["provider"]]
        item = {"id": m["id"], "label": m["label"]}
        if not providers.has_key(p):
            item.update(status="no_key", message=f"no key ({p['key_env']} is empty)")
        else:
            if m["provider"] not in cache:
                try:
                    cache[m["provider"]] = providers.list_model_ids(p)
                except Exception as e:  # report any provider failure in the list instead of crashing
                    cache[m["provider"]] = e
            ids = cache[m["provider"]]
            if isinstance(ids, Exception):
                item.update(status="error", message=f"couldn't list models: {ids}")
            elif m["id"] in ids:
                item.update(status="ok", message="available")
            else:
                close = sorted(i for i in ids if m["id"].split("-")[0] in i)[:6]
                hint = f" Similar IDs: {', '.join(close)}" if close else ""
                item.update(status="missing", message=f"not found for this key.{hint}")
        results.append(item)
    return jsonify(results)


# ---------- page ----------

@app.get("/")
def index():
    html = (ROOT / "app" / "index.template.html").read_text(encoding="utf-8")
    html = html.replace("__SYSTEM_PROMPT__", json.dumps(SYSTEM_PROMPT, ensure_ascii=False))
    head = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' \
           '<style>body{margin:0}[hidden]{display:none!important}</style><script>window.LOCAL_API=true</script></head><body>'
    return Response(head + html + "</body></html>", mimetype="text/html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    keys = [p["label"] for p in PROVIDERS.values() if providers.has_key(p)]
    print(f"Emoji Sentiment Lab: http://127.0.0.1:{port}")
    print("API keys found for: " + (", ".join(keys) if keys else "none yet (copy .env.example to .env and add keys)"))
    app.run(host="127.0.0.1", port=port, debug=False)
