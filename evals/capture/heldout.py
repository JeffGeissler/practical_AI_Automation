"""Held-out capture evaluation through the app's real capture code (parser + gateway).

Runs each configuration over heldout.json: the parser alone, then each model via the
Ollama adapter, REPEATS times. Uses a temporary database; never pulls models or reads
personal data. Writes a JSON result file to evals/results/.

    .venv/bin/python evals/capture/heldout.py qwen3:0.6b llama3.2:latest
    .venv/bin/python evals/capture/heldout.py --suite final qwen3:0.6b
"""

import json
import statistics
import sys
import tempfile
import time
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from productivity_assistant import capture, tasks
from productivity_assistant.ai import Gateway, OllamaProvider
from productivity_assistant.db import connect, migrate

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
REPEATS = 3
FIELDS = ["due_date", "project", "effort_minutes", "importance"]
TARGETS = {"schema_valid": 1.0, "title": 0.90, "project": 0.90, "effort_minutes": 0.85, "warm_p95_s": 2.0}


def unload(model):
    body = json.dumps({"model": model, "keep_alive": 0}).encode()
    request = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
    urllib.request.urlopen(request, timeout=30).read()


def score(task, names, gold):
    title = (task["title"] or "").lower()
    result = {"title": all(k.lower() in title for k in gold["title_keywords"])
              and not any(k.lower() in title for k in gold.get("title_forbidden", []))}
    final = {"due_date": task["due_date"].isoformat() if task["due_date"] else None,
             "project": names.get(task["project_id"]), "effort_minutes": task["effort_minutes"],
             "importance": task["importance"]}
    for field in FIELDS:
        result[field] = final[field] in gold[field]
    return result


def run(config, suite, connection, now):
    model = None if config == "parser" else config
    gateway = Gateway(OllamaProvider(model) if model else None)
    if model:
        unload(model)
        time.sleep(2)
    names = {row["id"]: row["name"] for row in tasks.list_projects(connection)}
    rows, first = [], True
    for repeat in range(REPEATS if model else 1):
        for case in suite["cases"]:
            started = time.perf_counter()
            draft = capture.draft(connection, case["text"], now, gateway)
            seconds = time.perf_counter() - started
            rows.append({"id": case["id"], "kind": case["kind"], "repeat": repeat, "cold": first and bool(model),
                         "seconds": round(seconds, 3), "ai": draft["ai"],
                         "title": draft["task"]["title"], "sources": draft["sources"],
                         "score": score(draft["task"], names, case["gold"])})
            first = False
    return {"config": config, "rows": rows, "summary": summarize(rows, bool(model), connection, config)}


def summarize(rows, uses_model, connection, config):
    total = len(rows)
    rate = {f: round(sum(r["score"][f] for r in rows) / total, 3) for f in ["title"] + FIELDS}
    summary = {"drafts": total, "all_fields": round(sum(all(r["score"].values()) for r in rows) / total, 3), **rate}
    for kind in ("explicit", "ambiguous", "adversarial"):
        subset = [r for r in rows if r["kind"] == kind]
        summary[f"{kind}_all_fields"] = f"{sum(all(r['score'].values()) for r in subset)}/{len(subset)}"
    if uses_model:
        outcomes = [row[0] for row in connection.execute(
            "SELECT outcome FROM ai_calls WHERE model = ? ORDER BY id", (config,))]
        warm = sorted(r["seconds"] for r in rows if not r["cold"])
        summary.update(
            schema_valid=round(outcomes.count("ok") / len(outcomes), 3), outcomes={o: outcomes.count(o) for o in
                                                                                  set(outcomes)},
            model_titles=sum(r["sources"].get("title") == "model" for r in rows),
            model_projects=sum(r["sources"].get("project_id") == "model" for r in rows),
            model_efforts=sum(r["sources"].get("effort_minutes") == "model" for r in rows),
            warm_p50_s=round(statistics.median(warm), 2), warm_p95_s=round(warm[int(len(warm) * 0.95) - 1], 2),
            cold_s=next(r["seconds"] for r in rows if r["cold"]))
        summary["meets_targets"] = {
            "schema_valid": summary["schema_valid"] >= TARGETS["schema_valid"],
            "title": rate["title"] >= TARGETS["title"], "project": rate["project"] >= TARGETS["project"],
            "effort_minutes": rate["effort_minutes"] >= TARGETS["effort_minutes"],
            "warm_p95_s": summary["warm_p95_s"] <= TARGETS["warm_p95_s"]}
    return summary


def main(models, name="heldout"):
    suite = json.loads((HERE / f"{name}.json").read_text())
    now = datetime.fromisoformat(suite["today"] + "T09:00:00").replace(tzinfo=timezone.utc)
    report = {"suite": name, "repeats": REPEATS, "targets": TARGETS, "prompt": capture.SYSTEM,
              "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": []}
    with tempfile.TemporaryDirectory() as folder, closing(connect(Path(folder) / "eval.sqlite")) as connection:
        migrate(connection)
        for project in suite["projects"]:
            tasks.create_project(connection, tasks.ProjectIn(name=project), now)
        for config in ["parser", *models]:
            print(config, flush=True)
            result = run(config, suite, connection, now)
            report["results"].append(result)
            print(" ", json.dumps(result["summary"]), flush=True)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    args = sys.argv[1:]
    suite_name = "heldout"
    if args[:1] == ["--suite"]:
        suite_name, args = args[1], args[2:]
    main(args or ["qwen3:0.6b"], suite_name)
