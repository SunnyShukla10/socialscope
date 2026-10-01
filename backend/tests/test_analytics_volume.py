from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from app.services.analytics_service import AnalyticsService


class _Result:
    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar

    def all(self):
        return self._rows


class _Db:
    def __init__(self, results):
        self.results = list(results)

    async def execute(self, _query):
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_volume_returns_complete_platform_date_grid():
    project_id = uuid.uuid4()
    org_id = uuid.uuid4()
    db = _Db(
        [
            _Result(scalar=SimpleNamespace(id=project_id)),
            _Result(
                rows=[
                    (datetime(2026, 1, 1, tzinfo=timezone.utc), "twitter"),
                    (datetime(2026, 1, 3, tzinfo=timezone.utc), "twitter"),
                    (datetime(2026, 1, 3, tzinfo=timezone.utc), "reddit"),
                ]
            ),
        ]
    )

    response = await AnalyticsService(db).get_volume(project_id, org_id)

    assert response.platforms == ["reddit", "twitter"]
    counts = {(point.date, point.platform): point.count for point in response.data}
    assert counts[("2026-01-01", "twitter")] == 1
    assert counts[("2026-01-01", "reddit")] == 0
    assert counts[("2026-01-02", "twitter")] == 0
    assert counts[("2026-01-02", "reddit")] == 0
    assert counts[("2026-01-03", "twitter")] == 1
    assert counts[("2026-01-03", "reddit")] == 1
