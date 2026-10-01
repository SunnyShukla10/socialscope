import csv
import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location("scope_benchmark",Path(__file__).resolve().parents[2]/"scripts"/"benchmark.py")
benchmark=importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)

def test_benchmark_plan_has_no_approved_spending():
    plan=benchmark.plan()
    assert len(plan["cells"])==12
    assert all(c["approved"] is False for c in plan["cells"])

def test_offline_analysis_deduplicates_and_leaves_unreviewed_unknown(tmp_path):
    path=tmp_path/"posts.csv"
    context=json.dumps([{"run_id":"run1","date_from":"2026-08-01","date_to":"2026-08-31"}])
    with path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["id","platform","published_at","body","collection_context"])
        writer.writeheader()
        for identity,dt in [("a","2026-08-05T12:00:00Z"),("a","2026-08-05T12:00:00Z"),("b","2024-08-05T12:00:00Z")]:
            writer.writerow(dict(id=identity,platform="tiktok",published_at=dt,body="Transit",collection_context=context))
    result=benchmark.analyze(path)["results"][0]
    assert result["unique_in_period"]==1
    assert result["by_month"]=={"2026-08":1}
    assert result["relevance_fraction"] is None
    review=tmp_path/"review.csv";review.write_text("id,relevant\na,yes\n")
    assert benchmark.analyze(path,review=review)["results"][0]["relevance_fraction"]==1.0
