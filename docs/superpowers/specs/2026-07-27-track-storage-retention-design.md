# 트랙 저장·보존 정책: MIDI 영구 보관 + WAV 즉시 삭제 + 단건 조회/MIDI 서빙 API

> Phase 4(DB 저장)·Phase 8.5(중앙 배포) 확장. 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.
> 코드 진행 추상화 구조(2026-07-26)와는 독립된 기능 — 별도 브랜치로 진행.

## 배경·목적

캡처 파이프라인은 지금 WAV(원본 오디오)와 MIDI(전사 결과)를 둘 다 `data/`에 파일로 영구 보관한다. WAV는 트랙당 수십 MB 수준으로 용량 부담이 크고, 저작권 있는 캡처 음원이라 "사적 이용 한정, 저장소 미커밋"이 이미 원칙으로 정해져 있다(CLAUDE.md). 반면 MIDI는 수십~수백 KB 수준으로 작고, 분석이 끝난 뒤에도 피아노롤 확인·향후 재분석의 기반 자료로 계속 쓸모가 있다.

이 설계는 ① WAV는 분석 완료 직후 삭제하고(개발 중 한시적 보관이 아니라 즉시 삭제로 확정) ② MIDI는 `data/midi/`에 파일로 계속 영구 보관하며 ③ Phase 8.5의 "모든 클라이언트는 api만 호출" 원칙에 맞춰 원격 클라이언트도 파일시스템 접근 없이 MIDI를 받을 수 있도록 API에 단건 조회 + MIDI 서빙 엔드포인트를 추가한다.

## 핵심 결정 사항

- **WAV: 분석 완료 직후 삭제** — `musicna-analyze`가 트랙 하나의 `save_analysis()`에 성공한 직후 해당 WAV 파일만 삭제. JSON 메타데이터 사이드카는 유지(삭제하면 향후 재분석 스캔 대상에서 완전히 빠지므로)
- **알려진 트레이드오프(사용자 확인 완료)**: WAV가 없으면 이후 `musicna-analyze --force` 재분석 시 오디오(chroma) 기반 코드 교차 검증·CLAP 무드 태깅은 더 이상 재수행할 수 없다(MIDI 기반 키/코드만 재생성 가능). 기존 문서화된 dev 워크플로(재분석으로 새 엔진 검증)에 영향이 있다는 걸 인지한 상태로 감수하기로 함
- **MIDI: DB BLOB이 아니라 기존과 동일하게 파일로 보관**(`data/midi/`, `Track.midi_path`) — 최초 제안은 SQLite BLOB 저장이었으나, 사용자가 별도 디렉토리·별도 파일 유지로 확정
- **원격 클라이언트를 위한 MIDI 서빙 엔드포인트 추가** — 현재 API는 트랙 ID 자체를 응답에 노출하지 않고 단건 조회 라우트도 없음. 이를 보완해 `GET /tracks/{id}` + `GET /tracks/{id}/midi`를 신설

## 논의 과정 (결정에 이른 배경)

- 처음 제안은 "MIDI도 중앙 저장소에 저장"을 SQLite BLOB으로 해석해 제시했으나(원격 클라이언트가 파일 접근 없이 API만으로 받을 수 있다는 이점 때문), 사용자가 재검토 후 파일 기반 보관으로 확정 — DB 크기 비대화 방지, 기존 `data/midi/` 관례 유지가 이유로 추정됨(명시적으로 묻지 않았으나 파일 방식이 이미 Phase 2부터 확립된 패턴이라 자연스러운 선택)
- WAV 삭제 시점은 "분석 완료 직후"와 "N일 후 자동 정리" 중 전자를 선택 — 개발 중 재분석 편의보다 용량 절약을 우선한 것으로 판단되며, 이 트레이드오프는 옵션 설명에 명시한 상태로 사용자가 인지하고 선택함
- MIDI가 파일로 남게 되면서, "중앙 저장소" 요구를 충족하려면 원격 클라이언트가 그 파일에 접근할 방법이 필요하다는 점이 드러남 → 현재 `/tracks`가 단건 조회조차 지원하지 않는다는 기존 갭(Phase 8.5 최종 리뷰에서 이미 한 번 언급됐던 사항)과 만나, 이번 기회에 `GET /tracks/{id}` + `GET /tracks/{id}/midi`를 함께 추가하기로 함

## 아키텍처

```
api/batch.py: analyze_captured()
    for wav_path in audio_dir.glob("*.wav"):
        ... 기존 분석 로직(무수정) ...
        save_analysis(session, result, audio_path=str(wav_path))
        wav_path.unlink()   # ← 신규: 저장 성공 직후 WAV만 삭제(JSON 사이드카는 유지)

core/store: Track.midi_path  (무수정 — 이미 존재)
core/store: Track.id          (기존 PK, 지금까지 API에 노출 안 됐음)

core/models.py: TrackMeta 또는 AnalysisResult에 id 필드 추가(신규)
core/store/repository.py: id로 단건 조회하는 함수 신규 추가

api/main.py:
    GET /tracks/{track_id}        (신규) — 단건 조회, 없으면 404
    GET /tracks/{track_id}/midi   (신규) — Track.midi_path 파일을 바이너리로 서빙, 파일 없으면 404
```

## 컴포넌트별 상세

### `core/models.py`

`AnalysisResult`에 `id: int | None = None` 필드 추가(신규 트랙 저장 전에는 아직 DB id가 없을 수 있어 optional). 기존 `/tracks` 목록 응답에 자동으로 포함됨(별도 라우트 변경 없이 필드 추가만으로 충분).

### `core/store/repository.py`

- `save_analysis()`가 반환하는 `Track` 객체의 `id`를 `_to_result()`에서 `AnalysisResult(id=track.id, ...)`로 채우도록 확장
- `get_track_by_id(session, track_id: int) -> AnalysisResult | None`(신규): id로 단건 조회, 없으면 None. 트랙의 최신 분석 1건을 `_to_result()`로 변환해 반환(기존 `list_latest_analyses()`와 동일한 "최신 분석" 선택 로직 재사용)

### `api/main.py`

- `GET /tracks/{track_id}` → `get_track_by_id()` 호출, 없으면 `HTTPException(404)`
- `GET /tracks/{track_id}/midi` → 먼저 트랙 조회(없으면 404) → `midi_path`가 None이거나 파일이 실제로 없으면 404(무음 캡처 등 MIDI가 애초에 없는 경우) → 있으면 `FileResponse(midi_path, media_type="audio/midi")`

### `api/batch.py`

`analyze_captured()`의 `save_analysis(session, result, audio_path=str(wav_path))` 호출 직후:

```python
wav_path.unlink(missing_ok=True)
```

실패(분석 예외 발생) 시에는 WAV를 지우지 않는다 — 이미 있는 `try/except` 블록의 성공 경로(정상 저장 완료 후)에만 추가.

## 테스트 전략

- `core/tests/test_repository.py`: `get_track_by_id()` — 존재하는 id 조회 성공, 없는 id는 None
- `core/tests/test_scaffold.py` 또는 `test_repository.py`: `AnalysisResult.id`가 저장 후 채워지는지 라운드트립 확인
- `api/tests/test_tracks_endpoint.py`(기존 파일 확장): `GET /tracks/{id}` 200/404 케이스, `GET /tracks/{id}/midi` — 파일 있을 때 바이너리 응답·Content-Type 확인, 파일 없을 때(또는 트랙 자체가 없을 때) 404
- `api/tests/test_batch.py`(기존 파일 확장): 분석 성공 후 WAV 파일이 실제로 삭제됐는지(`wav_path.exists() is False`), JSON 사이드카는 남아있는지 확인. 분석 실패 케이스에서는 WAV가 그대로 남아있는지도 확인(실패 시 삭제 안 함 회귀 방지)

## 범위 밖 / 백로그

- WAV 삭제로 인한 `--force` 재분석 시 오디오 기반 코드/무드 재추출 불가 — 이미 인지·수용된 트레이드오프, 별도 해결 과제 없음(필요해지면 재검토)
- MIDI 파일 자체의 정리(보존 기간 제한)는 이번 범위 밖 — MIDI는 영구 보관이 기본 방침
- `GET /tracks/{id}`의 캐싱·ETag 등 HTTP 최적화는 이번 범위 밖(개인용 저트래픽 서버 특성상 불필요 판단)
