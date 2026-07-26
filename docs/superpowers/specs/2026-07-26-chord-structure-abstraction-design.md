# 코드 진행 추상화 구조 설계

> Phase 3(배치 분석) 확장 — 기존 상세 코드 흐름(`core/analyze/chords.py`, `chords_audio.py`)은 무수정, 그 위에 곡 전체 구조 파악용 추상화 계층을 추가한다.
> 마스터 로드맵은 [PLAN.md](../../PLAN.md), 진행 상황은 [PROGRESS.md](../../PROGRESS.md) 참조.
> 무드 태그 체계 확장은 별도 설계(사용자 요청에 따라 이 설계 다음에 진행) — 이 문서 범위 밖.

## 배경·목적

Phase 3에서 구현한 코드 진행 추출(`ChordEvent` 타임라인)은 초 단위로 상세하지만, 그 상세함 때문에 오히려 **곡 전체의 구조**(어느 구간이 어떤 진행을 쓰는지, 같은 진행이 어디서 반복되는지)를 한눈에 파악하기 어렵다는 피드백을 받았다. 이 설계는 기존 상세 흐름은 그대로 둔 채, 그 위에 ① 구간(섹션) 단위 코드 진행 요약 ② 구간과 무관한 반복 패턴(루프) 탐지라는 두 가지 추상화를 추가한다.

## 핵심 결정 사항

- **기존 상세 코드 흐름은 무수정** — `ChordEvent`(확장 화음 포함, 예: Am7·G7)는 그대로 유지. 추상화는 별도 계층에서 수행
- **로마자 변환은 music21 그대로 활용** — `music21.roman.romanNumeralFromChord` 등 기존 의존성 안에서 해결, 신규 라이브러리 불필요
- **기준 키는 곡 전체 단일 key/mode**(기존 Krumhansl-Schmuckler 추정 결과) 그대로 사용 — **전조(modulation) 대응은 백로그**(사용자 확인: "추후 관찰 후 필요시 추가")
- **구간 요약 + 독립 루프 탐지 둘 다 구현**(택일 아님) — allin1 섹션 경계 기준 요약과, 섹션과 무관한 반복 부분수열 탐지를 모두 제공
- **매칭은 정확 일치, 최소 길이 4코드부터 반복 인정**(확정) — 기능적 유사 진행(대리코드) 퍼지 매칭은 **백로그**
- **신규 ML/외부 의존성 없음** — 순수 알고리즘(문자열 반복 패턴 탐지)으로 구현, 곡당 코드 변화 이벤트가 수십~백여 개 수준이라 성능 문제 없음

## 논의 과정 (결정에 이른 배경)

- 사용자가 처음 제시한 요청은 "코드 진행"과 "무드 태그"라는 서로 다른 모듈(코드 계열 vs `moods.py`)에 걸친 두 가지 요구였음 → 각각 독립 설계로 분리하기로 하고, 이 문서는 코드 진행 추상화만 다룸(무드는 후속 설계)
- 추상화 방식으로 "섹션 기반 요약"과 "섹션 무관 독립 루프 탐지" 중 택일할지 물었으나, 사용자가 **둘 다** 원한다고 확정 — 섹션 요약은 기존 allin1 구조 라벨과 연결되는 직관적 뷰를, 루프 탐지는 섹션 경계가 실제 반복 단위와 어긋날 수 있는 경우까지 포착
- 로마자 변환 기준 키를 곡 전체 단일 키로 할지 구간별 재추정할지 물었을 때, 사용자는 **단순함(1번, 전체 단일 키)을 택하되 전조 대응은 나중에 실측 후 필요하면 추가**하는 쪽으로 결정 — 이번 설계 범위를 실용적으로 좁힘
- 루프 탐지의 최소 인정 길이는 **4코드**로 확정

## 아키텍처

```
core/analyze/chords.py, chords_audio.py   (기존, 무수정)
    └→ 병합된 ChordEvent 타임라인 (source=midi/audio/merged)
              │
              ▼
core/analyze/chord_structure.py  (신규)
    ├─ simplify_chord(chord_symbol) -> 트라이어드 품질 단순화 (music21 파싱)
    ├─ to_roman(chord_symbol, key, mode) -> 로마자 문자열 (music21 roman 변환)
    ├─ build_roman_sequence(chords, key, mode) -> 곡 전체 로마자 이벤트 목록(연속 동일값 병합)
    ├─ summarize_sections(roman_sequence, sections) -> list[SectionChordSummary]
    │      (섹션 경계로 슬라이스 + 동일 진행 구간끼리 repeats_of로 연결)
    └─ find_chord_loops(roman_sequence, min_length=4) -> list[ChordLoop]
              │
              ▼
core/analyze/__init__.py: analyze_track()  (확장) — key/mode·sections 계산 후 위 모듈 호출,
    결과를 AnalysisResult.section_chord_summaries / .chord_loops 에 채움
    (key/mode 없음 또는 sections 없음 → 조용히 건너뜀, 기존 graceful degradation과 동일 패턴)
              │
              ▼
core/store/db.py, repository.py  (확장) — SectionChordSummary/ChordLoop용 신규 테이블 저장
```

## 컴포넌트별 상세

### `core/analyze/chord_structure.py` (신규)

- `simplify_chord(chord_symbol: str) -> str | None`: music21로 코드 심볼을 파싱해 트라이어드 품질(장/단/감/증)만 남긴 단순 표기로 변환. 파싱 실패 시 None(호출 측이 해당 이벤트를 건너뜀)
- `to_roman(chord_symbol: str, key: str, mode: str) -> str | None`: 위 단순화 결과를 곡 전체 key/mode 기준 로마자(I, V, vi, IV 등)로 변환. music21의 로마자 변환기 활용
- `build_roman_sequence(chords: list[ChordEvent], key: str, mode: str) -> list[RomanEvent]`: 병합된 코드 타임라인 전체를 로마자 이벤트로 변환하고 연속 동일 로마자를 하나로 합침(실시간 코드 트래커의 "변화 시점만 산출" 방식과 동일 원리). `RomanEvent`는 내부 전용 dataclass(roman, start_s, end_s) — DB/API 계약에는 노출 안 함
- `summarize_sections(roman_sequence, sections: list[Section]) -> list[SectionChordSummary]`: 각 섹션 구간에 겹치는 로마자 이벤트를 슬라이스해 `roman_progression` 리스트로 만들고, 이전에 나온 섹션 중 동일한 `roman_progression`을 가진 것이 있으면 그 인덱스를 `repeats_of`에 기록
- `find_chord_loops(roman_sequence, min_length: int = 4) -> list[ChordLoop]`: 로마자 시퀀스에서 길이 4 이상의 반복 부분수열을 탐지. 긴 패턴부터 탐지해 이미 발견된 패턴에 완전히 포함되는 더 짧은 하위 패턴은 별도 보고하지 않음(중복 방지). 각 패턴의 모든 등장 위치를 `occurrences`로 기록

### `core/models.py` (확장)

```python
class SectionChordSummary(BaseModel):
    """구간(섹션) 단위 코드 진행 요약 — 로마자 표기, 곡 전체 key/mode 기준."""
    section_label: str
    start_s: float
    end_s: float
    roman_progression: list[str]       # 예: ["I", "V", "vi", "IV"]
    repeats_of: int | None = None      # 동일 진행을 쓰는 첫 구간의 sections 인덱스, 없으면 None


class ChordLoop(BaseModel):
    """구간 경계와 무관하게 곡 전체에서 반복되는 코드 패턴(최소 4개 코드)."""
    pattern: list[str]                          # 예: ["I", "V", "vi", "IV"]
    occurrences: list[tuple[float, float]]      # 각 등장의 (start_s, end_s)
```

`AnalysisResult`에 필드 추가(기존 `sections`/`chords`/`moods`와 동일하게 플랫 리스트, 기본값 빈 리스트):

```python
section_chord_summaries: list[SectionChordSummary] = []
chord_loops: list[ChordLoop] = []
```

### `core/analyze/__init__.py: analyze_track()` (확장)

코드 진행(`chords`)·구간(`sections`)·키(`key`/`mode`) 계산이 끝난 뒤:

```python
if key is not None and sections:
    roman_sequence = build_roman_sequence(chords, key, mode)
    section_chord_summaries = summarize_sections(roman_sequence, sections)
    chord_loops = find_chord_loops(roman_sequence, min_length=4)
else:
    section_chord_summaries, chord_loops = [], []
```

key가 없거나(무음 캡처 등) allin1 미설치로 sections가 비어 있으면 조용히 빈 리스트 — 기존 파이프라인의 graceful degradation 원칙과 동일.

### `core/store/db.py`, `repository.py` (확장)

`sections`/`chords` 테이블과 동일한 패턴으로 신규 테이블 2개:

- `section_chord_summaries`: id, analysis_id(FK), section_label, start_s, end_s, roman_progression(JSON 텍스트), repeats_of(nullable int)
- `chord_loops`: id, analysis_id(FK), pattern(JSON 텍스트), occurrences(JSON 텍스트)

`save_analysis`/`list_latest_analyses`(repository.py)를 확장해 위 두 리스트를 함께 저장·조회하도록 한다. API 응답(`AnalysisResult`)에는 이미 필드가 추가돼 있으므로 `/tracks` 엔드포인트는 자동으로 포함(별도 라우트 변경 불필요).

## 테스트 전략

- `core/tests/test_chord_structure.py`(신규): 합성 `ChordEvent`+`Section` 픽스처로
  - `simplify_chord`/`to_roman` 단위 테스트(알려진 코드 심볼 → 알려진 로마자)
  - 두 섹션이 동일 로마자 진행을 갖도록 구성한 픽스처로 `repeats_of` 연결 검증
  - 4개 이상 반복되는 패턴을 심어둔 합성 시퀀스로 `find_chord_loops`가 정확히 탐지·중복 없이 보고하는지 검증(3개짜리 반복은 인정 안 됨도 함께 검증)
  - key/mode가 None이거나 sections가 빈 경우 `analyze_track()`이 크래시 없이 빈 리스트를 반환하는지(기존 견고성 테스트 패턴과 동일)

## 범위 밖 / 백로그

- **전조(modulation) 대응** — 현재는 곡 전체 단일 key/mode로만 로마자 변환. 구간별 키 재추정은 실제 데이터로 관찰 후 필요성이 확인되면 추가 검토
- **기능적 유사 진행 퍼지 매칭** — 대리코드(예: IV↔ii) 등 음악 이론적으로 유사한 진행을 "같은 패턴"으로 묶는 것은 이번 범위 밖, 정확 일치만 지원
- **무드 태그 체계 확장** — 별도 브레인스토밍·설계 문서로 후속 진행
