# 트랙 저장·보존 정책 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WAV는 분석 성공 직후 삭제하고(용량 절약), MIDI는 기존처럼 `data/midi/`에 파일로 영구 보관하며, 트랙 id를 API에 노출해 원격 클라이언트가 파일시스템 접근 없이 단건 조회(`GET /tracks/{id}`)와 MIDI 파일 서빙(`GET /tracks/{id}/midi`)을 받을 수 있게 한다.

**Architecture:** `core/models.py`의 `AnalysisResult`에 `id` 필드를 추가하고 저장소 계층(`repository.py`)이 이를 채운다. `repository.py`에 id 단건 조회 함수를 추가하고, `api/main.py`가 이를 이용해 두 개의 신규 REST 라우트를 노출한다. `api/batch.py`는 분석 저장 성공 직후 원본 WAV만 삭제한다(JSON 사이드카는 유지).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Pydantic — 신규 의존성 없음.

## Global Constraints

- 기존 워크스페이스 테스트(현재 185 passed, `uv run pytest core/tests api/tests tui/tests`)는 Task 3에서 **의도적으로 변경하는 단 하나의 기존 assert**(`test_batch_analyzes_and_skips_on_rerun`의 재실행 부분, 아래 Task 3 참조)를 제외하고 전 과정에서 계속 통과해야 한다.
- `core/`는 macOS API를 일절 import하지 않는다(기존 원칙 유지).
- 신규 의존성 없음.
- **알려진 트레이드오프(사용자 확인 완료, 구현 중 다시 논의하지 말 것)**: WAV가 분석 직후 삭제되므로, `musicna-analyze --force` 재분석 시 오디오(chroma) 기반 코드 교차 검증·CLAP 무드 태깅은 더 이상 재수행되지 않는다(MIDI가 있으면 MIDI 기반 키/코드 재추출만 가능). 이 트레이드오프를 "해결"하려는 시도(예: WAV 백업 등)를 하지 말 것 — 설계상 의도된 동작이다.
- WAV 삭제는 `save_analysis()` 저장이 **성공한 직후에만** 수행한다 — 분석 실패 시(예외 발생) WAV는 그대로 남겨 재시도 가능하게 한다.

---

## Task 1: `AnalysisResult.id` 필드 + 저장소 단건 조회

**Files:**
- Modify: `core/src/musicna_core/models.py`
- Modify: `core/src/musicna_core/store/repository.py`
- Test: `core/tests/test_repository.py`

**Interfaces:**
- Produces: `AnalysisResult.id: int | None = None`(신규 필드). `get_track_by_id(session: Session, track_id: int) -> AnalysisResult | None`(신규 함수, `musicna_core.store`에서 import 가능해야 함 — Task 2가 API 라우트에서 이 함수를 쓴다).

- [ ] **Step 1: 실패하는 테스트를 작성**

`core/tests/test_repository.py`의 기존 `test_save_and_list_roundtrip` 테스트를 아래로 교체(신규 `id` 필드 때문에 저장 전/후 객체가 더 이상 완전히 동일하지 않음 — 저장된 쪽만 실제 id를 가지므로):

```python
def test_save_and_list_roundtrip(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    original = _result(captured_at=datetime(2026, 7, 25, 10, 0))
    with factory() as session:
        save_analysis(session, original, audio_path="data/audio/a.wav")
    with factory() as session:
        [loaded] = list_latest_analyses(session)
    assert loaded.id is not None
    assert loaded.model_copy(update={"id": None}) == original
```

파일 끝에 아래 테스트 2개를 추가(상단 import에 `get_track_by_id` 추가 필요 — `from musicna_core.store import create_session_factory, get_track_by_id, list_latest_analyses, save_analysis`로 교체):

```python
def test_get_track_by_id_returns_result(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    with factory() as session:
        track = save_analysis(session, _result(captured_at=datetime(2026, 7, 25, 10, 0)))
        track_id = track.id

    with factory() as session:
        result = get_track_by_id(session, track_id)
    assert result is not None
    assert result.id == track_id
    assert result.track.title == "Song A"


def test_get_track_by_id_returns_none_when_missing(tmp_path):
    factory = create_session_factory(str(tmp_path / "t.db"))
    with factory() as session:
        result = get_track_by_id(session, 999)
    assert result is None
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_track_by_id'`(또는 `AttributeError`/`AssertionError` — 신규 필드·함수가 아직 없어 여러 형태로 실패할 수 있음, "실패한다"는 사실만 확인하면 됨)

- [ ] **Step 3: `core/src/musicna_core/models.py`에 `id` 필드 추가**

`AnalysisResult` 클래스의 첫 줄(`"""한 곡에 대한 배치 분석의 최종 산출물. DB 저장과 API 응답의 원천."""` 바로 다음, `track: TrackMeta` 앞)에 추가:

```python
    id: int | None = None  # DB 저장 전에는 None, 저장 후 조회 시 실제 트랙 id로 채워짐
```

- [ ] **Step 4: `core/src/musicna_core/store/repository.py`에 `id` 채우기 + 단건 조회 함수 추가**

`_to_result()` 함수의 `return AnalysisResult(` 바로 다음 줄에 추가:

```python
        id=track.id,
```

`list_latest_analyses()` 함수 바로 위에 헬퍼 함수를 추가(코드 중복 방지 — `get_track_by_id`와 `list_latest_analyses`가 동일한 "최신 분석 선택" 로직을 공유):

```python
def _latest_analysis(track: Track) -> Analysis:
    return max(track.analyses, key=lambda a: (a.analyzed_at or datetime.min, a.id))


def get_track_by_id(session: Session, track_id: int) -> AnalysisResult | None:
    """id로 트랙을 조회해 최신 분석 결과를 돌려준다. 트랙이 없거나 분석 이력이 없으면 None."""
    track = session.get(Track, track_id)
    if track is None or not track.analyses:
        return None
    return _to_result(_latest_analysis(track))
```

그리고 `list_latest_analyses()`의 본문 중 `latest = max(track.analyses, key=lambda a: (a.analyzed_at or datetime.min, a.id))` 줄을 `latest = _latest_analysis(track)`로 교체.

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_repository.py -v`
Expected: PASS — 전부(5개: 기존 3개 + 신규 2개)

- [ ] **Step 6: 전체 core 테스트 스위트로 회귀 확인**

Run: `uv run pytest core/tests -v`
Expected: PASS — 전부

- [ ] **Step 7: 커밋**

```bash
git add core/src/musicna_core/models.py core/src/musicna_core/store/repository.py core/tests/test_repository.py
git commit -m "feat: AnalysisResult.id 필드 + get_track_by_id 단건 조회 추가"
```

---

## Task 2: `GET /tracks/{id}` + `GET /tracks/{id}/midi` API 엔드포인트

**Files:**
- Modify: `api/src/musicna_api/main.py`
- Test: `api/tests/test_tracks_endpoint.py`

**Interfaces:**
- Consumes: `get_track_by_id`(Task 1)
- Produces: `GET /tracks/{track_id}` → `AnalysisResult` 또는 404. `GET /tracks/{track_id}/midi` → MIDI 파일 바이너리(`audio/midi`) 또는 404(트랙 없음·MIDI 경로 없음·파일이 디스크에 없음 세 경우 모두 404).

- [ ] **Step 1: 실패하는 테스트를 작성**

`api/tests/test_tracks_endpoint.py`의 기존 import(`AnalysisResult`, `TrackMeta`, `create_session_factory`, `save_analysis` 등)로 아래 테스트가 전부 커버되므로 import 변경은 불필요하다. 파일 끝에 아래 테스트를 추가:

```python
def test_get_track_by_id_returns_analysis(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Song", artist="Tester", captured_at=datetime(2026, 7, 25, 10, 0)),
            key="C", mode="major",
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == track_id
    assert body["track"]["title"] == "Song"


def test_get_track_by_id_404_when_missing(client):
    r = client.get("/tracks/999")
    assert r.status_code == 404


def test_get_track_midi_serves_file(client, tmp_path):
    midi_path = tmp_path / "song.mid"
    midi_path.write_bytes(b"MThd fake midi bytes")
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Song", captured_at=datetime(2026, 7, 25, 10, 0)),
            midi_path=str(midi_path),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 200
    assert r.content == b"MThd fake midi bytes"
    assert r.headers["content-type"] == "audio/midi"


def test_get_track_midi_404_when_no_midi_path(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="NoMidi", captured_at=datetime(2026, 7, 25, 10, 0)),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 404


def test_get_track_midi_404_when_file_missing_on_disk(client, tmp_path):
    factory = create_session_factory(str(tmp_path / "api.db"))
    missing_midi = tmp_path / "gone.mid"  # 저장은 됐지만 실제 파일은 없는 상황(재분석 도중 삭제된 경우 등)
    with factory() as session:
        track = save_analysis(session, AnalysisResult(
            track=TrackMeta(title="Ghost", captured_at=datetime(2026, 7, 25, 10, 0)),
            midi_path=str(missing_midi),
        ))
        track_id = track.id

    r = client.get(f"/tracks/{track_id}/midi")
    assert r.status_code == 404


def test_get_track_midi_404_when_track_missing(client):
    r = client.get("/tracks/999/midi")
    assert r.status_code == 404
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_tracks_endpoint.py -v`
Expected: FAIL — `404`가 아니라 다른 상태 코드(라우트 자체가 없어 FastAPI가 405 또는 404를 다르게 반환하거나, 웹 정적 서빙 마운트에 걸림) — "테스트가 실패한다"는 사실만 확인하면 됨

- [ ] **Step 3: `api/src/musicna_api/main.py`에 두 라우트 추가**

상단 import를 아래로 교체:

```python
import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from musicna_api import player, remote_capture, system
from musicna_api.live import broadcaster
from musicna_core.models import AnalysisResult, LiveEvent, live_event_adapter
from musicna_core.store import create_session_factory, get_track_by_id, list_latest_analyses
```

`@app.get("/tracks", ...)` 함수 정의 바로 다음에 추가:

```python
@app.get("/tracks/{track_id}", response_model=AnalysisResult)
def get_track(track_id: int, db: Session = Depends(get_db)) -> AnalysisResult:
    """트랙 단건 조회 — 없으면 404."""
    result = get_track_by_id(db, track_id)
    if result is None:
        raise HTTPException(status_code=404, detail="track not found")
    return result


@app.get("/tracks/{track_id}/midi")
def get_track_midi(track_id: int, db: Session = Depends(get_db)) -> FileResponse:
    """트랙의 MIDI 파일을 바이너리로 서빙 — 트랙이 없거나, MIDI 경로가 없거나, 파일이 디스크에 없으면 404."""
    result = get_track_by_id(db, track_id)
    if result is None or result.midi_path is None:
        raise HTTPException(status_code=404, detail="midi not found")
    midi_path = Path(result.midi_path)
    if not midi_path.exists():
        raise HTTPException(status_code=404, detail="midi file missing on disk")
    return FileResponse(midi_path, media_type="audio/midi", filename=midi_path.name)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests/test_tracks_endpoint.py -v`
Expected: PASS — 전부(기존 2개 + 신규 6개 = 8개)

- [ ] **Step 5: 전체 api 테스트로 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add api/src/musicna_api/main.py api/tests/test_tracks_endpoint.py
git commit -m "feat: GET /tracks/{id} 단건 조회 + GET /tracks/{id}/midi MIDI 서빙 엔드포인트 추가"
```

---

## Task 3: WAV 삭제 — 분석 성공 직후

**Files:**
- Modify: `api/src/musicna_api/batch.py`
- Test: `api/tests/test_batch.py`

**Interfaces:** 없음(외부에서 호출하는 함수 시그니처 변경 없음, `analyze_captured()`의 부작용만 추가됨).

- [ ] **Step 1: 실패하는 테스트를 작성 + 기존 테스트의 재실행 부분 수정**

`api/tests/test_batch.py`의 기존 `test_batch_analyzes_and_skips_on_rerun` 함수를 아래로 교체 — **WAV가 분석 직후 삭제되므로, 두 번째 실행 시 "이미 분석됨을 감지해 건너뜀"이 아니라 "스캔할 WAV 자체가 없어 아무 것도 처리 안 함"이 된다(의도된 동작 변화)**:

```python
def test_batch_analyzes_and_skips_on_rerun(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 1, "skipped": 0, "failed": 0}

    with create_session_factory(db)() as session:
        [result] = list_latest_analyses(session)
    assert result.track.title == "Song"
    assert result.key == "C" and len(result.chords) >= 2

    # WAV는 분석 성공 직후 삭제되므로, 재실행 시 스캔 대상 자체가 없어 아무 것도 처리되지 않는다
    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 0, "skipped": 0, "failed": 0}
```

파일 끝에 아래 테스트 2개를 추가:

```python
def test_batch_deletes_wav_after_successful_analysis(tmp_path):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)
    wav_path = audio_dir / "001 - Tester - Song.wav"
    json_path = audio_dir / "001 - Tester - Song.json"

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 1, "skipped": 0, "failed": 0}
    assert not wav_path.exists()  # 분석 성공 직후 WAV 삭제
    assert json_path.exists()     # 사이드카 JSON은 유지(재스캔 무의미 판단·디버깅용)


def test_batch_keeps_wav_when_analysis_fails(tmp_path, monkeypatch):
    audio_dir, midi_dir = tmp_path / "audio", tmp_path / "midi"
    db = str(tmp_path / "b.db")
    _prepare_capture(audio_dir, midi_dir)
    wav_path = audio_dir / "001 - Tester - Song.wav"

    import musicna_api.batch as batch_mod

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(batch_mod, "analyze_track", _raise)

    counts = analyze_captured(audio_dir, midi_dir, db)
    assert counts == {"analyzed": 0, "skipped": 0, "failed": 1}
    assert wav_path.exists()  # 분석 실패 시 WAV는 삭제하지 않는다(재시도 가능하도록)
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest api/tests/test_batch.py -v`
Expected: FAIL — `test_batch_analyzes_and_skips_on_rerun`은 두 번째 `assert`에서 `{"analyzed": 0, "skipped": 1, "failed": 0} != {"analyzed": 0, "skipped": 0, "failed": 0}`로 실패, `test_batch_deletes_wav_after_successful_analysis`는 `assert not wav_path.exists()`에서 실패(아직 삭제 로직이 없어 파일이 존재함)

- [ ] **Step 3: `api/src/musicna_api/batch.py`에 WAV 삭제 추가**

`analyze_captured()` 함수 안, `save_analysis(session, result, audio_path=str(wav_path))` 바로 다음 줄에 추가:

```python
                wav_path.unlink(missing_ok=True)
```

(즉 아래 두 줄이 되도록: `save_analysis(...)` → `wav_path.unlink(missing_ok=True)` → `counts["analyzed"] += 1`. `try` 블록 안, `except Exception:` 절 이전에 위치하므로 분석 실패 시(예외가 `save_analysis` 이전 단계에서 발생) 이 줄에 도달하지 않아 WAV가 자동으로 보존된다.)

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest api/tests/test_batch.py -v`
Expected: PASS — 전부(기존 2개 중 1개 수정 + 신규 2개 = 4개)

- [ ] **Step 5: 전체 워크스페이스 테스트로 최종 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add api/src/musicna_api/batch.py api/tests/test_batch.py
git commit -m "feat: 분석 성공 직후 원본 WAV 삭제(JSON 사이드카는 유지)"
```

---

## Task 4: 문서 갱신

**Files:**
- Modify: `docs/PROGRESS.md`

**Interfaces:** 없음.

- [ ] **Step 1: `docs/PROGRESS.md`의 Phase 4 체크리스트에 항목 추가**

"### Phase 4 — DB 저장" 섹션 마지막 체크리스트 항목 다음에 추가:

```markdown
- [x] 트랙 저장·보존 정책(2026-07-27 추가) — WAV는 분석 성공 직후 삭제(용량 절약, JSON 사이드카는 유지), MIDI는 `data/midi/` 파일로 영구 보관. `AnalysisResult.id` 노출 + `GET /tracks/{id}`(단건 조회)·`GET /tracks/{id}/midi`(MIDI 서빙) 신설 — 원격 클라이언트가 파일시스템 접근 없이 API만으로 MIDI를 받을 수 있음. 설계: [2026-07-27-track-storage-retention-design.md](superpowers/specs/2026-07-27-track-storage-retention-design.md), 계획: [2026-07-27-track-storage-retention.md](superpowers/plans/2026-07-27-track-storage-retention.md). **알려진 트레이드오프**: WAV 삭제로 `--force` 재분석 시 오디오 기반 코드/무드 재추출 불가(MIDI 기반 재추출만 가능)
```

- [ ] **Step 2: 작업 로그 표에 한 줄 추가**

`## 작업 로그` 표의 마지막 행 다음에 추가(실제 실행 시점의 테스트 총계로 숫자를 갱신할 것):

```markdown
| 2026-07-27 | 트랙 저장·보존 정책 구현 — WAV 분석 성공 직후 삭제(`api/batch.py`), `AnalysisResult.id` 노출 + `GET /tracks/{id}`·`GET /tracks/{id}/midi` 신설(`api/main.py`, `core/store/repository.py`) | 신규 의존성 없음. `--force` 재분석 시 오디오 기반 재검증이 안 되는 트레이드오프는 이미 인지·수용됨(설계 스펙 참조) |
```

- [ ] **Step 3: 커밋 및 푸시**

```bash
git add docs/PROGRESS.md
git commit -m "docs: 트랙 저장·보존 정책 구현 완료 반영"
git push
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙의 4개 컴포넌트(id 노출, 단건 조회, MIDI 서빙, WAV 삭제)가 Task 1~3에 전부 매핑됨.
- **플레이스홀더 스캔**: 없음.
- **타입 일관성**: `get_track_by_id`(Task 1에서 정의)가 Task 2의 API 라우트에서 쓰는 시그니처와 일치. `AnalysisResult.id`가 Task 1(정의)·Task 2(API 응답 검증)에서 일관되게 쓰임.
- **기존 테스트 변경 사항 명시**: `test_batch_analyzes_and_skips_on_rerun`의 재실행 기대값 변경(Task 3)과 `test_save_and_list_roundtrip`의 비교 방식 변경(Task 1)은 새 필드/동작 때문에 필요한 의도된 변경이며, 각 Task 안에 정확한 이유와 새 코드를 명시했다.
