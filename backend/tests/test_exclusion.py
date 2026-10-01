from types import SimpleNamespace
import uuid

import pytest

from app.services.post_service import PostService


class _Result:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _Db:
    def __init__(self, post):
        self.post = post
        self.deleted = None
        self.flushed = False

    async def execute(self, _query):
        return _Result(scalar=self.post)

    async def delete(self, item):
        self.deleted = item

    async def flush(self):
        self.flushed = True


@pytest.mark.asyncio
async def test_exclusion_preserves_post():
    post = SimpleNamespace(id=uuid.uuid4())
    db = _Db(post)

    deleted = await PostService(db).set_exclusion(uuid.uuid4(), post.id, uuid.uuid4(), True)

    assert deleted is True
    assert db.deleted is None
    assert post.excluded is True
    assert db.flushed is True


@pytest.mark.asyncio
async def test_exclusion_returns_false_when_not_found():
    db = _Db(None)

    deleted = await PostService(db).set_exclusion(uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), True)

    assert deleted is False
    assert db.deleted is None
