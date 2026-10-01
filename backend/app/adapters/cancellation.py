import asyncio
import inspect
from typing import Awaitable, TypeVar


T = TypeVar("T")


class CollectionCancelled(Exception):
    """Internal control-flow signal for a user-requested collection cancellation."""


class CancellationSignal:
    """Process-local signal shared by every platform coroutine in one job."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise CollectionCancelled("Collection cancelled by user")

    async def run(self, awaitable: Awaitable[T]) -> T:
        """
        Await work until it finishes or cancellation is signalled.

        If both finish together, keep the completed response so an adapter can
        normalize and preserve that page before it stops pagination.
        """
        if self.is_cancelled:
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            raise CollectionCancelled("Collection cancelled by user")
        operation_task = asyncio.ensure_future(awaitable)
        cancellation_task = asyncio.create_task(self._event.wait())
        try:
            done, _ = await asyncio.wait(
                {operation_task, cancellation_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if operation_task in done:
                return await operation_task

            operation_task.cancel()
            await asyncio.gather(operation_task, return_exceptions=True)
            raise CollectionCancelled("Collection cancelled by user")
        finally:
            cancellation_task.cancel()
            await asyncio.gather(cancellation_task, return_exceptions=True)

    async def wait(self, seconds: float) -> None:
        await self.run(asyncio.sleep(max(0.0, seconds)))
