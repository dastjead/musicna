"""api 서버와 통신하는 얇은 REST 클라이언트 — TUI 위젯은 이것만 통해 api와 통신한다.

직접 서브프로세스나 파일에 접근하지 않는다 (docs/PLAN.md 코어 분리 전략: 클라이언트는
api만 호출).
"""

import httpx


class ApiClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=5.0, transport=transport)

    def health(self) -> bool:
        try:
            r = self._http.get("/health")
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def player_status(self) -> dict | None:
        r = self._http.get("/player/status")
        r.raise_for_status()
        if not r.content:
            return None
        return r.json()

    def player_play(self) -> None:
        self._http.post("/player/play").raise_for_status()

    def player_pause(self) -> None:
        self._http.post("/player/pause").raise_for_status()

    def player_next(self) -> None:
        self._http.post("/player/next").raise_for_status()

    def player_previous(self) -> None:
        self._http.post("/player/previous").raise_for_status()

    def player_volume(self, percent: int) -> None:
        self._http.post("/player/volume", params={"percent": percent}).raise_for_status()

    def system_start(self) -> dict:
        r = self._http.post("/system/start")
        r.raise_for_status()
        return r.json()

    def system_status(self) -> dict:
        r = self._http.get("/system/status")
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
