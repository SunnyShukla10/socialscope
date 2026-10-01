import csv
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.services.export_service import (
    CSV_COLUMNS,
    EXISTING_CSV_COLUMNS,
    ExportService,
)


def post(**overrides):
    values = {
        "id": uuid.uuid4(),
        "platform": "twitter",
        "vendor":"socialvault", "excluded":False, "collected_at":datetime.now(timezone.utc),
        "author_username": "health_daily",
        "author_display_name": "Health Daily",
        "author_followers": 12000,
        "published_at": datetime(2026, 7, 1, 12, 30, tzinfo=timezone.utc),
        "body": "A normal post",
        "likes": 10,
        "shares": 2,
        "comments": 3,
        "views": 1000,
        "engagement_score": 1.9,
        "hashtags": ["#Health", "#News"],
        "url": "https://example.test/post/1",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def account(**overrides):
    values = {
        "account_label": "media_news",
        "account_label_confidence": 0.98,
        "account_label_reason": "The biography identifies a healthcare news publisher.",
        "account_label_source": "llm",
        "account_label_confirmed_by_human": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def test_csv_escaping_preserves_commas_quotes_line_breaks_and_unicode(tmp_path):
    csv_path = tmp_path / "export.csv"
    body = 'First line, with comma\nSecond line says "hello" — café 😀'
    reason = 'Evidence says "publisher",\nwith multilingual text: saúde 日本語'
    ExportService(db=None)._write_csv(
        csv_path,
        [
            (
                post(
                    author_display_name='Daily "Health", International',
                    body=body,
                    hashtags=["#saúde", "#日本語"],
                ),
                account(account_label_reason=reason),
            )
        ],
    )

    row = read_csv(csv_path)[0]
    assert row["author_display_name"] == 'Daily "Health", International'
    assert row["body"] == body
    assert row["hashtags"] == "#saúde,#日本語"


def test_existing_export_columns_and_values_remain_compatible(tmp_path):
    csv_path = tmp_path / "export.csv"
    existing_post = post()
    ExportService(db=None)._write_csv(csv_path, [(existing_post, account())])

    row = read_csv(csv_path)[0]
    assert list(row)[: len(EXISTING_CSV_COLUMNS)] == EXISTING_CSV_COLUMNS
    assert row["id"] == str(existing_post.id)
    assert row["platform"] == "twitter"
    assert row["author_username"] == "health_daily"
    assert row["published_at"] == "2026-07-01T12:30:00+00:00"
    assert row["body"] == "A normal post"
    assert row["likes"] == "10"
    assert row["hashtags"] == "#Health,#News"
    assert row["url"] == "https://example.test/post/1"


@pytest.mark.asyncio
async def test_generate_csv_includes_run_provenance(tmp_path, monkeypatch):
    import json
    row_post = post()
    run_id = uuid.uuid4()
    run = SimpleNamespace(id=run_id, pull_id=uuid.uuid4(), mode="collection", date_from=None,
        date_to=None, status="completed")
    class Result:
        def __init__(self, rows): self.rows = rows
        def all(self): return self.rows
    class Db:
        def __init__(self): self.statements = []
        async def execute(self, statement):
            self.statements.append(statement)
            return Result([(row_post, account())] if len(self.statements) == 1 else
                [(row_post.id, datetime.now(timezone.utc), run, "public transit")])
    db = Db()
    monkeypatch.setattr("app.services.export_service.EXPORTS_DIR", str(tmp_path))
    file_path, row_count = await ExportService(db)._generate_csv(uuid.uuid4(), uuid.uuid4())
    row = read_csv(file_path)[0]
    assert row_count == 1
    context = json.loads(row["collection_context"])[0]
    assert context["run_id"] == str(run_id)
    assert context["query"] == "public transit"
    assert row["analysis_scope"] == "included"
    assert "LEFT OUTER JOIN accounts" in str(db.statements[0])


def test_formula_looking_post_is_exported_as_text(tmp_path):
    path = tmp_path / "safe.csv"
    ExportService(None)._write_csv(path, [(post(body="=1+1"), None)])
    assert read_csv(path)[0]["body"] == "'=1+1"
