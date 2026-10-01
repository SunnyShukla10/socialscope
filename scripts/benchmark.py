"""Offline benchmark planner/analyzer. No network or provider dependencies.

python scripts/benchmark.py plan --out benchmark-plan.json
python scripts/benchmark.py analyze --csv export.csv --runs runs.json --out report.json
Optional --review review.csv with columns id,relevant (yes/no/unsure).
The report's review_template contains a deterministic subset to label manually.
"""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def plan():
    cells = []
    for topic, query in [("broad", "public transit"), ("niche", "rural bus accessibility")]:
        for period, start, end in [("recent", "2026-08-01", "2026-08-31"), ("older", "2024-08-01", "2024-08-31")]:
            for platform in ["instagram", "tiktok", "facebook"]:
                cells.append(dict(id=f"{topic}-{period}-{platform}", query=query, platform=platform,
                    date_from=start, date_to=end, proposed_request_limit=2,
                    proposed_sociavault_credit_limit=2 if platform != "instagram" else None,
                    xpoz_query_estimate=12 if platform == "instagram" else None,
                    target_posts=100, approved=False))
    return {"status":"PROPOSAL ONLY: no live benchmark authorized", "cells":cells,
        "comparison":"Vendor credits are different units. Obtain account-specific dollar costs and approve an equal monetary cap per cell before execution.",
        "instagram":"SDK polling/retries are not a verified credit ceiling; obtain a provider-side spending bound before running.",
        "sequence":"Baseline first. Variations and researcher-supplied Facebook sources require a separate approved arm; never silently expand queries."}


def analyze(csv_path, runs=None, review=None):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    reviews = {}
    if review:
        with open(review, encoding="utf-8-sig", newline="") as f:
            reviews = {r["id"]:r["relevant"].strip().lower() for r in csv.DictReader(f)}
    jobs = {r["id"]:r for r in (runs or [])}
    groups = defaultdict(dict)
    for row in rows:
        for context in json.loads(row.get("collection_context") or "[]"):
            groups[(context["run_id"],row["platform"])][row["id"]] = (row,context)
    report = []
    for (run_id,platform), selected in sorted(groups.items()):
        weekly, monthly = Counter(), Counter()
        in_range, missing = [], 0
        for row, ctx in selected.values():
            if not row.get("published_at"):
                missing += 1
                continue
            dt = datetime.fromisoformat(row["published_at"].replace("Z", "+00:00"))
            day = dt.date().isoformat()
            if ctx.get("date_from") and day < ctx["date_from"][:10]: continue
            if ctx.get("date_to") and day > ctx["date_to"][:10]: continue
            in_range.append(row)
            year,week,_ = dt.isocalendar()
            weekly[f"{year}-W{week:02d}"] += 1
            monthly[day[:7]] += 1
        labels = [reviews[r["id"]] for r in in_range if reviews.get(r["id"]) in {"yes","no"}]
        job = jobs.get(run_id, {})
        state = job.get("platform_states", {}).get(platform, {})
        report.append({"run_id":run_id,"platform":platform,"unique_in_period":len(in_range),
            "missing_publication_date":missing,"by_week":dict(weekly),"by_month":dict(monthly),
            "reviewed_yes_no":len(labels),"relevance_fraction":labels.count("yes")/len(labels) if labels else None,
            "usage_cumulative_for_pull":job.get("usage",{}).get("platforms",{}).get(platform),
            "stop_reason":state.get("provider_stop_reason"),
            "page_metrics":state.get("provider_stop_details"),
            "review_template":[{"id":r["id"],"relevant":"", "body":r.get("body","")}
                for r in sorted(in_range,key=lambda r:hashlib.sha256(r["id"].encode()).hexdigest())[:30]]})
    return {"results":report,"limitations":["Offline analysis of exported observations only; no live requests.",
        "Run usage is cumulative for its pull: do not sum repeated snapshots. Use a separate pull per benchmark cell.",
        "Unreviewed relevance is null, not zero. Unsure labels are excluded from the yes/no denominator.",
        "Weekly/monthly counts describe observed coverage, not completeness. Missing page metrics stay unknown."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan"); p.add_argument("--out", required=True)
    a = sub.add_parser("analyze"); a.add_argument("--csv", required=True); a.add_argument("--runs"); a.add_argument("--review"); a.add_argument("--out", required=True)
    args = parser.parse_args()
    output = plan() if args.command == "plan" else analyze(args.csv,
        json.loads(Path(args.runs).read_text(encoding="utf-8")) if args.runs else [], args.review)
    Path(args.out).write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"Wrote offline {args.command}: {args.out}")

if __name__ == "__main__": main()
