"""실시간 미리보기 브로드캐스트 — 인프로세스 pub/sub.

이벤트 흐름: musicna-live(전사 프로세스) → POST /live/ingest → LiveBroadcaster
→ /ws/live 구독자(웹/iOS). 서버는 이벤트를 해석하지 않고 계약(LiveEvent)만 검증해 중계한다.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class LiveBroadcaster:
    """구독자별 asyncio 큐로 이벤트를 팬아웃한다. 느린 구독자는 이벤트를 잃는다(실시간 우선)."""

    def __init__(self, queue_size: int = 1000) -> None:
        self._queue_size = queue_size
        self._subscribers: set[asyncio.Queue[str]] = set()

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, payload: str) -> None:
        for q in self._subscribers:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("느린 실시간 구독자 — 이벤트 드롭")


broadcaster = LiveBroadcaster()
