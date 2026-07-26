# 코드 진행 추상화 구조 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 상세 코드 진행(`ChordEvent` 타임라인)은 그대로 둔 채, 곡 전체 구조를 한눈에 파악할 수 있도록 ① allin1 섹션 단위 로마자 진행 요약(`SectionChordSummary`, 동일 진행을 쓰는 섹션끼리 연결) ② 섹션과 무관한 반복 패턴(루프) 탐지(`ChordLoop`, 최소 4코드)를 배치 분석 파이프라인에 추가한다.

**Architecture:** 신규 모듈 `core/analyze/chord_structure.py`가 코드 심볼을 트라이어드 품질로 단순화 → 곡 전체 key/mode 기준 로마자로 변환 → 연속 동일 로마자를 병합한 "로마자 이벤트 시퀀스"를 만든다. 이 시퀀스 위에서 섹션 요약과 반복 패턴 탐지를 수행한다. 새 ML/외부 의존성 없음 — music21(이미 base 의존성)과 순수 알고리즘만 사용. `analyze_track()`이 이 모듈을 호출해 `AnalysisResult`에 두 신규 필드를 채우고, DB에도 신규 테이블 2개로 저장한다.

**Tech Stack:** Python 3.12, music21(base 의존성, 신규 없음), Pydantic, SQLAlchemy.

## Global Constraints

- 기존 워크스페이스 테스트(현재 161 passed, `uv run pytest core/tests api/tests tui/tests`)는 전 과정에서 계속 통과해야 한다.
- `core/`는 macOS API를 일절 import하지 않는다(기존 원칙 유지) — 이 작업은 전부 `core/`에서 이뤄지므로 특히 준수.
- 신규 의존성 없음 — `music21`은 이미 base 의존성(`core/pyproject.toml`)이라 optional extra 지연 import 불필요, `chords.py`/`keys.py`와 동일하게 모듈 최상단에서 바로 import한다.
- **로마자 변환은 `roman.romanNumeralFromChord(...).figure`를 직접 신뢰하지 말고 수동 조합할 것** — 사전 조사 결과, 감화음(diminished)이 특정 스케일 디그리(1·4·5도)에 오면 `.figure`가 `"io5b3"`처럼 일관성 없는 부가 기호를 붙인다(같은 화음이라도 위치에 따라 표기가 달라짐). 대신 `rn.scaleDegree`(1~7) + `cs.quality`(대소문자·품질 접미사 결정) + `rn.frontAlterationAccidental`(임시표 접두사)을 조합해 `"I"`, `"vii°"`, `"bVII"`, `"#iv"` 같은 일관된 표기를 직접 만든다(아래 Task 2에 정확한 코드 제공, 사전에 실측 검증 완료).
- 코드 심볼의 플랫 표기는 이 프로젝트 전체에서 `music21` 고유 표기("-"가 flat, "b"는 사용 안 함, 예: "B-")를 따른다 — `chords.py`의 기존 관례와 동일. 테스트 픽스처도 이 표기를 따를 것.
- 기존 `sections`/`chords`/`moods`와 동일하게, 신규 필드도 `AnalysisResult`에 플랫 리스트로 추가한다(중첩 컨테이너 도입 안 함).

---

## Task 1: `core/models.py`에 `SectionChordSummary`/`ChordLoop` 모델 추가

**Files:**
- Modify: `core/src/musicna_core/models.py`
- Test: `core/tests/test_scaffold.py` (기존 파일에 라운드트립 케이스 추가 — 신규 파일 만들 필요 없음, 아래 참조)

**Interfaces:**
- Produces: `SectionChordSummary(section_label: str, start_s: float, end_s: float, roman_progression: list[str], repeats_of: int | None = None)`, `ChordLoop(pattern: list[str], occurrences: list[tuple[float, float]])`. `AnalysisResult`에 `section_chord_summaries: list[SectionChordSummary] = []`, `chord_loops: list[ChordLoop] = []` 필드 추가. Task 2~5가 이 두 모델을 그대로 사용한다.

- [ ] **Step 1: 기존 스캐폴드 테스트에 신규 필드 기본값 검증을 추가하는 실패 테스트 작성**

`core/tests/test_scaffold.py`의 최상단 import 줄을 아래로 교체:

```python
from musicna_core.models import (
    AnalysisResult,
    ChordEvent,
    ChordLoop,
    ChordSource,
    MoodTag,
    Section,
    SectionChordSummary,
    TrackMeta,
)
```

그리고 파일 끝에 아래 테스트를 추가한다:

```python
def test_analysis_result_defaults_new_chord_structure_fields_to_empty():
    result = AnalysisResult(track=TrackMeta(title="X"))
    assert result.section_chord_summaries == []
    assert result.chord_loops == []


def test_section_chord_summary_and_chord_loop_round_trip():
    summary = SectionChordSummary(
        section_label="verse", start_s=0.0, end_s=10.0,
        roman_progression=["I", "V", "vi", "IV"], repeats_of=None,
    )
    loop = ChordLoop(pattern=["I", "V", "vi", "IV"], occurrences=[(0.0, 4.0), (4.0, 8.0)])
    result = AnalysisResult(
        track=TrackMeta(title="X"),
        section_chord_summaries=[summary],
        chord_loops=[loop],
    )
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_scaffold.py -v`
Expected: FAIL — `ImportError: cannot import name 'SectionChordSummary'` (또는 `ChordLoop`)

- [ ] **Step 3: `core/src/musicna_core/models.py`에 모델 추가**

`class MoodTag(BaseModel): ...` 바로 다음, `# ── 실시간 미리보기 ...` 주석 앞에 추가:

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
    occurrences: list[tuple[float, float]]       # 각 등장의 (start_s, end_s)
```

그리고 `AnalysisResult` 클래스 안, `moods: list[MoodTag] = []` 바로 다음 줄에 추가:

```python
    section_chord_summaries: list[SectionChordSummary] = []
    chord_loops: list[ChordLoop] = []
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_scaffold.py -v`
Expected: PASS — 전부

- [ ] **Step 5: 전체 core 테스트 스위트로 회귀 확인**

Run: `uv run pytest core/tests -v`
Expected: PASS — 전부(기존 `test_repository.py`의 라운드트립 테스트도 새 필드가 기본값 `[]`라 그대로 통과해야 함)

- [ ] **Step 6: 커밋**

```bash
git add core/src/musicna_core/models.py core/tests/test_scaffold.py
git commit -m "feat: SectionChordSummary/ChordLoop 모델 추가"
```

---

## Task 2: `core/analyze/chord_structure.py` — 코드 단순화·로마자 변환·시퀀스 생성

**Files:**
- Create: `core/src/musicna_core/analyze/chord_structure.py`
- Test: `core/tests/test_chord_structure.py`

**Interfaces:**
- Consumes: `SectionChordSummary`/`ChordLoop`(Task 1), `ChordEvent`(기존 `musicna_core.models`)
- Produces: `simplify_chord(chord_symbol: str) -> str | None`, `to_roman(chord_symbol: str, key_tonic: str, mode: str) -> str | None`, `RomanEvent`(내부 dataclass: `roman: str, start_s: float, end_s: float`), `build_roman_sequence(chords: list[ChordEvent], key_tonic: str, mode: str) -> list[RomanEvent]`. Task 3이 `RomanEvent`/`to_roman`을 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트를 작성**

`core/tests/test_chord_structure.py` 생성:

```python
"""코드 단순화·로마자 변환·시퀀스 생성 테스트 — 실측 검증된 music21 동작 기준."""

from musicna_core.analyze.chord_structure import RomanEvent, build_roman_sequence, simplify_chord, to_roman
from musicna_core.models import ChordEvent, ChordSource


def test_simplify_chord_strips_extensions_to_triad_quality():
    assert simplify_chord("Am7") == "Am"
    assert simplify_chord("Cmaj7") == "C"
    assert simplify_chord("G7") == "G"
    assert simplify_chord("Bdim") == "Bdim"


def test_simplify_chord_returns_none_for_unparseable_input():
    assert simplify_chord("not-a-chord-symbol-###") is None


def test_to_roman_major_key_diatonic_triads():
    assert to_roman("C", "C", "major") == "I"
    assert to_roman("Dm", "C", "major") == "ii"
    assert to_roman("Em", "C", "major") == "iii"
    assert to_roman("F", "C", "major") == "IV"
    assert to_roman("G", "C", "major") == "V"
    assert to_roman("Am", "C", "major") == "vi"
    assert to_roman("Bdim", "C", "major") == "vii°"


def test_to_roman_extensions_reduce_to_triad_roman():
    assert to_roman("Am7", "C", "major") == "vi"
    assert to_roman("G7", "C", "major") == "V"


def test_to_roman_chromatic_chords_get_accidental_prefix():
    assert to_roman("B-", "C", "major") == "bVII"
    assert to_roman("F#", "C", "major") == "#IV"


def test_to_roman_minor_key():
    assert to_roman("Am", "A", "minor") == "i"
    assert to_roman("G", "A", "minor") == "VII"
    assert to_roman("F", "A", "minor") == "VI"


def test_to_roman_unparseable_returns_none():
    assert to_roman("garbage", "C", "major") is None


def test_build_roman_sequence_merges_consecutive_identical_romans():
    chords = [
        ChordEvent(chord="C", start_s=0.0, end_s=1.0, source=ChordSource.MIDI),
        ChordEvent(chord="Cmaj7", start_s=1.0, end_s=2.0, source=ChordSource.MIDI),  # 같은 로마자(I)로 병합돼야 함
        ChordEvent(chord="F", start_s=2.0, end_s=3.0, source=ChordSource.MIDI),
    ]
    sequence = build_roman_sequence(chords, "C", "major")
    assert sequence == [
        RomanEvent(roman="I", start_s=0.0, end_s=2.0),
        RomanEvent(roman="IV", start_s=2.0, end_s=3.0),
    ]


def test_build_roman_sequence_skips_unparseable_chords():
    chords = [
        ChordEvent(chord="C", start_s=0.0, end_s=1.0, source=ChordSource.MIDI),
        ChordEvent(chord="garbage", start_s=1.0, end_s=2.0, source=ChordSource.MIDI),
        ChordEvent(chord="F", start_s=2.0, end_s=3.0, source=ChordSource.MIDI),
    ]
    sequence = build_roman_sequence(chords, "C", "major")
    assert [e.roman for e in sequence] == ["I", "IV"]
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_chord_structure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'musicna_core.analyze.chord_structure'`

- [ ] **Step 3: `chord_structure.py` 구현**

`core/src/musicna_core/analyze/chord_structure.py` 생성:

```python
"""코드 진행 추상화 — 상세 코드 흐름(chords.py) 위에 곡 전체 구조 파악용 계층을 추가한다.

코드 심볼을 트라이어드 품질로 단순화하고 곡 전체 key/mode 기준 로마자로 변환한다.
로마자 변환은 `roman.romanNumeralFromChord(...).figure`를 직접 쓰지 않는다 — 감화음이
1·4·5도에 오면 `.figure`가 일관성 없는 부가 기호("io5b3")를 붙이는 것을 실측으로 확인해,
scaleDegree + quality + frontAlterationAccidental을 조합해 직접 구성한다.
"""

from dataclasses import dataclass

from music21 import harmony, key as m21key, roman

from musicna_core.models import ChordEvent

_ROMAN_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"]
_TRIAD_SUFFIX = {"major": "", "minor": "m", "diminished": "dim", "augmented": "aug"}
_QUALITY_SUFFIX = {"major": "", "minor": "", "diminished": "°", "augmented": "+"}
_ACCIDENTAL_PREFIX = {"sharp": "#", "flat": "b", "double-sharp": "##", "double-flat": "bb"}


def simplify_chord(chord_symbol: str) -> str | None:
    """코드 심볼을 트라이어드 품질(장/단/감/증)만 남긴 표기로 단순화한다. 파싱 불가 시 None."""
    try:
        cs = harmony.ChordSymbol(chord_symbol)
    except Exception:
        return None
    suffix = _TRIAD_SUFFIX.get(cs.quality)
    if suffix is None:
        return None
    return f"{cs.root().name}{suffix}"


def to_roman(chord_symbol: str, key_tonic: str, mode: str) -> str | None:
    """코드 심볼을 곡 전체 key/mode 기준 로마자(트라이어드 품질만)로 변환한다. 판정 불가 시 None."""
    simplified = simplify_chord(chord_symbol)
    if simplified is None:
        return None
    try:
        cs = harmony.ChordSymbol(simplified)
        rn = roman.romanNumeralFromChord(cs, m21key.Key(key_tonic, mode))
    except Exception:
        return None

    numeral = _ROMAN_NUMERALS[rn.scaleDegree - 1]
    if cs.quality in ("minor", "diminished"):
        numeral = numeral.lower()
    numeral += _QUALITY_SUFFIX[cs.quality]
    if rn.frontAlterationAccidental is not None:
        numeral = _ACCIDENTAL_PREFIX.get(rn.frontAlterationAccidental.name, "") + numeral
    return numeral


@dataclass
class RomanEvent:
    """로마자 이벤트 — 연속 동일 로마자를 병합한 곡 전체 시퀀스의 원소. API/DB 계약에는 노출 안 함."""

    roman: str
    start_s: float
    end_s: float


def build_roman_sequence(chords: list[ChordEvent], key_tonic: str, mode: str) -> list[RomanEvent]:
    """병합된 코드 타임라인 전체를 로마자 이벤트로 변환한다(연속 동일 로마자는 병합, 판정 불가 이벤트는 건너뜀)."""
    events: list[RomanEvent] = []
    for chord_event in sorted(chords, key=lambda c: c.start_s):
        numeral = to_roman(chord_event.chord, key_tonic, mode)
        if numeral is None:
            continue
        if events and events[-1].roman == numeral:
            events[-1] = RomanEvent(roman=numeral, start_s=events[-1].start_s, end_s=chord_event.end_s)
        else:
            events.append(RomanEvent(roman=numeral, start_s=chord_event.start_s, end_s=chord_event.end_s))
    return events
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_chord_structure.py -v`
Expected: PASS — 전부(11개)

- [ ] **Step 5: 커밋**

```bash
git add core/src/musicna_core/analyze/chord_structure.py core/tests/test_chord_structure.py
git commit -m "feat: chord_structure.py — 코드 단순화·로마자 변환·시퀀스 생성"
```

---

## Task 3: 섹션 요약 + 반복 패턴(루프) 탐지

**Files:**
- Modify: `core/src/musicna_core/analyze/chord_structure.py`
- Test: `core/tests/test_chord_structure.py` (Task 2에서 만든 파일에 추가)

**Interfaces:**
- Consumes: `RomanEvent`(Task 2), `SectionChordSummary`/`ChordLoop`(Task 1), `Section`(기존 `musicna_core.models`)
- Produces: `summarize_sections(roman_sequence: list[RomanEvent], sections: list[Section]) -> list[SectionChordSummary]`, `find_chord_loops(roman_sequence: list[RomanEvent], min_length: int = 4) -> list[ChordLoop]`. Task 4가 이 두 함수를 `analyze_track()`에서 호출한다.

- [ ] **Step 1: 실패하는 테스트를 `test_chord_structure.py`에 추가**

파일 상단 import를 아래로 교체(기존 줄 확장):

```python
from musicna_core.analyze.chord_structure import (
    RomanEvent,
    build_roman_sequence,
    find_chord_loops,
    simplify_chord,
    summarize_sections,
    to_roman,
)
from musicna_core.models import ChordEvent, ChordSource, Section
```

파일 끝에 추가:

```python
def test_summarize_sections_links_repeated_progressions():
    sequence = [
        RomanEvent(roman="I", start_s=0.0, end_s=1.0),
        RomanEvent(roman="V", start_s=1.0, end_s=2.0),
        RomanEvent(roman="vi", start_s=2.0, end_s=3.0),
        RomanEvent(roman="IV", start_s=3.0, end_s=4.0),
        RomanEvent(roman="ii", start_s=4.0, end_s=5.0),
        RomanEvent(roman="V", start_s=5.0, end_s=6.0),
        RomanEvent(roman="I", start_s=6.0, end_s=7.0),
        RomanEvent(roman="V", start_s=7.0, end_s=8.0),
        RomanEvent(roman="vi", start_s=8.0, end_s=9.0),
        RomanEvent(roman="IV", start_s=9.0, end_s=10.0),
    ]
    sections = [
        Section(label="verse", start_s=0.0, end_s=4.0),
        Section(label="chorus", start_s=4.0, end_s=6.0),
        Section(label="verse", start_s=6.0, end_s=10.0),
    ]
    summaries = summarize_sections(sequence, sections)

    assert [s.roman_progression for s in summaries] == [
        ["I", "V", "vi", "IV"],
        ["ii", "V"],
        ["I", "V", "vi", "IV"],
    ]
    assert summaries[0].repeats_of is None  # 첫 등장
    assert summaries[1].repeats_of is None  # 다른 진행
    assert summaries[2].repeats_of == 0     # 0번 구간(verse)과 동일 진행


def test_summarize_sections_empty_section_has_no_repeats_of():
    sequence = [RomanEvent(roman="I", start_s=5.0, end_s=6.0)]
    sections = [Section(label="silence", start_s=0.0, end_s=1.0)]  # 겹치는 이벤트 없음
    [summary] = summarize_sections(sequence, sections)
    assert summary.roman_progression == []
    assert summary.repeats_of is None


def test_find_chord_loops_detects_repeated_four_chord_pattern():
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(["I", "V", "vi", "IV", "I", "V", "vi", "IV"])
    ]
    loops = find_chord_loops(sequence, min_length=4)
    assert len(loops) == 1
    assert loops[0].pattern == ["I", "V", "vi", "IV"]
    assert loops[0].occurrences == [(0.0, 4.0), (4.0, 8.0)]


def test_find_chord_loops_ignores_repeats_shorter_than_min_length():
    sequence = [
        RomanEvent(roman=r, start_s=float(i), end_s=float(i + 1))
        for i, r in enumerate(["I", "V", "vi", "I", "V", "vi", "IV"])
    ]
    assert find_chord_loops(sequence, min_length=4) == []


def test_find_chord_loops_empty_sequence_returns_empty():
    assert find_chord_loops([], min_length=4) == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_chord_structure.py -v`
Expected: FAIL — `ImportError: cannot import name 'summarize_sections'`

- [ ] **Step 3: `chord_structure.py`에 두 함수 추가**

파일 상단 import에 `from collections import defaultdict`와 `from musicna_core.models import ChordEvent, Section`(Section 추가) 반영:

```python
from collections import defaultdict
from dataclasses import dataclass

from music21 import harmony, key as m21key, roman

from musicna_core.models import ChordEvent, ChordLoop, Section, SectionChordSummary
```

(주의: `ChordLoop`/`SectionChordSummary`는 Task 1에서 `musicna_core.models`에 추가됐으므로 여기서 import한다.)

파일 끝에 추가:

```python
def summarize_sections(roman_sequence: list[RomanEvent], sections: list[Section]) -> list[SectionChordSummary]:
    """섹션 경계마다 로마자 진행을 슬라이스하고, 동일 진행을 쓰는 앞선 섹션과 연결한다."""
    summaries: list[SectionChordSummary] = []
    first_seen: dict[tuple[str, ...], int] = {}
    for index, section in enumerate(sections):
        progression = [
            event.roman
            for event in roman_sequence
            if event.start_s < section.end_s and event.end_s > section.start_s
        ]
        key_tuple = tuple(progression)
        repeats_of: int | None = None
        if progression:
            if key_tuple in first_seen:
                repeats_of = first_seen[key_tuple]
            else:
                first_seen[key_tuple] = index
        summaries.append(
            SectionChordSummary(
                section_label=section.label,
                start_s=section.start_s,
                end_s=section.end_s,
                roman_progression=progression,
                repeats_of=repeats_of,
            )
        )
    return summaries


def find_chord_loops(roman_sequence: list[RomanEvent], min_length: int = 4) -> list[ChordLoop]:
    """구간과 무관하게 로마자 시퀀스에서 반복되는 부분수열(최소 min_length)을 탐지한다.

    긴 패턴부터 탐지하고, 이미 발견된 패턴에 포함된 위치는 더 짧은 하위 패턴으로 재보고하지 않는다.
    겹치지 않는 등장이 2회 이상이어야 채택된다.
    """
    romans = [event.roman for event in roman_sequence]
    n = len(romans)
    claimed = [False] * n
    loops: list[ChordLoop] = []

    for length in range(n // 2, min_length - 1, -1):
        groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for start in range(n - length + 1):
            if any(claimed[start : start + length]):
                continue
            groups[tuple(romans[start : start + length])].append(start)

        for pattern, starts in groups.items():
            occurrence_starts: list[int] = []
            last_end = -1
            for start in starts:
                if start >= last_end:
                    occurrence_starts.append(start)
                    last_end = start + length
            if len(occurrence_starts) < 2:
                continue
            for start in occurrence_starts:
                for i in range(start, start + length):
                    claimed[i] = True
            occurrences = [
                (roman_sequence[start].start_s, roman_sequence[start + length - 1].end_s)
                for start in occurrence_starts
            ]
            loops.append(ChordLoop(pattern=list(pattern), occurrences=occurrences))

    loops.sort(key=lambda loop: (-len(loop.pattern), loop.occurrences[0][0]))
    return loops
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_chord_structure.py -v`
Expected: PASS — 전부(16개)

- [ ] **Step 5: 커밋**

```bash
git add core/src/musicna_core/analyze/chord_structure.py core/tests/test_chord_structure.py
git commit -m "feat: chord_structure.py — 섹션 요약(summarize_sections) + 반복 패턴 탐지(find_chord_loops)"
```

---

## Task 4: `analyze_track()` 파이프라인 연결

**Files:**
- Modify: `core/src/musicna_core/analyze/__init__.py`
- Test: `core/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `build_roman_sequence`, `summarize_sections`, `find_chord_loops`(Task 2·3)
- Produces: `analyze_track()`가 반환하는 `AnalysisResult`에 `section_chord_summaries`/`chord_loops`가 채워짐(key/mode 없거나 sections 없으면 빈 리스트).

- [ ] **Step 1: 실패하는 테스트를 `test_pipeline.py`에 추가**

파일 끝에 추가(기존 import에 이미 `AnalysisResult` 등이 있음, 추가 import 불필요 — `result.section_chord_summaries`/`result.chord_loops` 접근만 하면 됨):

```python
def test_analyze_track_fills_chord_structure_when_key_and_sections_present(monkeypatch, tmp_path):
    """key/mode와 sections가 모두 있으면 섹션 요약·루프 탐지가 채워져야 한다."""
    fake = types.ModuleType("allin1")
    seg = types.SimpleNamespace(label="verse", start=0.0, end=8.0)
    fake.analyze = lambda path, **kw: types.SimpleNamespace(bpm=120.0, segments=[seg])
    monkeypatch.setitem(sys.modules, "allin1", fake)
    monkeypatch.setattr(analyze_mod, "pkg_version", lambda name: "0.0-test")

    s = stream.Stream()
    for name in ["C4 E4 G4", "G3 B3 D4", "A3 C4 E4", "F3 A3 C4"]:
        c = m21chord.Chord(name)
        c.quarterLength = 4.0  # 120bpm → 2초씩, 4개 = 8초 = 섹션 길이와 일치
        s.append(c)
    midi = tmp_path / "track.mid"
    s.write("midi", fp=str(midi))

    result = analyze_track(tmp_path / "missing.wav", midi, TrackMeta(title="Structured"))

    assert (result.key, result.mode) == ("C", "major")
    assert len(result.section_chord_summaries) == 1
    assert result.section_chord_summaries[0].section_label == "verse"
    assert result.section_chord_summaries[0].roman_progression == ["I", "V", "vi", "IV"]
    # 루프 탐지는 min_length=4 기본값 — 이 픽스처는 4개뿐이라 반복이 없으므로 빈 리스트가 정상
    assert result.chord_loops == []


def test_analyze_track_chord_structure_empty_without_key(tmp_path):
    """key가 없으면(예: 노트 없는 MIDI) 크래시 없이 빈 리스트여야 한다."""
    result = analyze_track(tmp_path / "missing.wav", None, TrackMeta(title="NoKey"))
    assert result.section_chord_summaries == []
    assert result.chord_loops == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_pipeline.py -k chord_structure -v`
Expected: FAIL — `AttributeError: 'AnalysisResult' object has no attribute 'section_chord_summaries'`(이미 Task 1에서 필드 자체는 생겼으므로, 실제로는 `result.section_chord_summaries == []`가 항상 참이라 이 특정 assert는 실패하지 않을 수 있음 — 대신 `roman_progression == ["I","V","vi","IV"]` assert가 `[] == [...]`로 실패해야 정상. 실패 메시지가 다르더라도 "테스트가 실패한다"는 것만 확인하면 된다)

- [ ] **Step 3: `analyze_track()`에 코드 구조 분석 호출 추가**

`core/src/musicna_core/analyze/__init__.py` 상단 import에 추가:

```python
from musicna_core.analyze.chord_structure import build_roman_sequence, find_chord_loops, summarize_sections
```

그리고 `analyze_track()` 함수 안, `moods, clap_ver = _analyze_moods(audio_path)` 다음 줄부터 `return AnalysisResult(...)` 사이에 추가:

```python
    section_chord_summaries: list = []
    chord_loops: list = []
    if key is not None and sections:
        roman_sequence = build_roman_sequence(chords, key, mode)
        section_chord_summaries = summarize_sections(roman_sequence, sections)
        chord_loops = find_chord_loops(roman_sequence, min_length=4)
```

`return AnalysisResult(...)` 호출의 `midi_path=...,` 줄 앞에 추가:

```python
        section_chord_summaries=section_chord_summaries,
        chord_loops=chord_loops,
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_pipeline.py -v`
Expected: PASS — 전부(기존 6개 + 신규 2개 = 8개)

- [ ] **Step 5: 전체 core 테스트로 회귀 확인**

Run: `uv run pytest core/tests -v`
Expected: PASS — 전부

- [ ] **Step 6: 커밋**

```bash
git add core/src/musicna_core/analyze/__init__.py core/tests/test_pipeline.py
git commit -m "feat: analyze_track()에 코드 구조 추상화(섹션 요약·루프 탐지) 연결"
```

---

## Task 5: DB 저장 — 신규 테이블 2개 + 저장소 왕복

**Files:**
- Modify: `core/src/musicna_core/store/db.py`
- Modify: `core/src/musicna_core/store/repository.py`
- Modify: `core/src/musicna_core/store/__init__.py`
- Test: `core/tests/test_repository.py`

**Interfaces:**
- Consumes: `SectionChordSummary`/`ChordLoop`(Task 1)
- Produces: `SectionChordSummaryRow`, `ChordLoopRow`(SQLAlchemy 모델, `musicna_core.store`에서 import 가능). `save_analysis`/`list_latest_analyses`가 이 두 리스트를 왕복 저장·복원.

- [ ] **Step 1: 실패하는 왕복 테스트를 `test_repository.py`에 추가**

파일 상단 import를 아래로 교체:

```python
from musicna_core.models import (
    AnalysisResult,
    CaptureSource,
    ChordEvent,
    ChordLoop,
    ChordSource,
    MoodTag,
    Section,
    SectionChordSummary,
    TrackMeta,
)
from musicna_core.store import create_session_factory, list_latest_analyses, save_analysis
```

`_result()` 헬퍼 함수의 `moods=[MoodTag(tag="energetic", score=0.8)],` 줄 다음에 추가:

```python
        section_chord_summaries=[
            SectionChordSummary(
                section_label="chorus", start_s=30.0, end_s=60.0,
                roman_progression=["I", "V", "vi", "IV"], repeats_of=None,
            )
        ],
        chord_loops=[
            ChordLoop(pattern=["I", "V", "vi", "IV"], occurrences=[(30.0, 34.0), (34.0, 38.0)])
        ],
```

(이렇게 하면 기존 `test_save_and_list_roundtrip`이 신규 필드까지 포함해 왕복 검증하게 된다 — 별도 신규 테스트 함수 불필요, 기존 라운드트립 테스트가 이미 `assert loaded == original`로 전체 필드를 비교하기 때문.)

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `uv run pytest core/tests/test_repository.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChordLoop'`(또는 `SectionChordSummary`)

- [ ] **Step 3: `db.py`에 신규 테이블 2개 추가**

`core/src/musicna_core/store/db.py` 상단 import를 아래로 교체:

```python
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, create_engine
```

`class Analysis(Base): ...`의 관계 필드 목록(`moods: Mapped[list["Mood"]] = relationship(back_populates="analysis")` 다음 줄)에 추가:

```python
    section_chord_summaries: Mapped[list["SectionChordSummaryRow"]] = relationship(back_populates="analysis")
    chord_loops: Mapped[list["ChordLoopRow"]] = relationship(back_populates="analysis")
```

`class Mood(Base): ...` 클래스 정의 다음, `def create_session_factory(...)` 앞에 추가:

```python
class SectionChordSummaryRow(Base):
    __tablename__ = "section_chord_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    section_label: Mapped[str] = mapped_column(String)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    roman_progression: Mapped[str] = mapped_column(String)  # JSON 리스트 문자열
    repeats_of: Mapped[int | None] = mapped_column(Integer, nullable=True)

    analysis: Mapped[Analysis] = relationship(back_populates="section_chord_summaries")


class ChordLoopRow(Base):
    __tablename__ = "chord_loops"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analyses.id"))
    pattern: Mapped[str] = mapped_column(String)      # JSON 리스트 문자열
    occurrences: Mapped[str] = mapped_column(String)  # JSON 리스트[[start,end],...] 문자열

    analysis: Mapped[Analysis] = relationship(back_populates="chord_loops")
```

- [ ] **Step 4: `repository.py`에 저장·복원 로직 추가**

`core/src/musicna_core/store/repository.py` 상단 import를 아래로 교체:

```python
from musicna_core.models import (
    AnalysisResult,
    ChordEvent,
    ChordLoop,
    MoodTag,
    Section,
    SectionChordSummary,
    TrackMeta,
)
from musicna_core.store.db import Analysis, Chord, ChordLoopRow, Mood, SectionChordSummaryRow, SectionRow, Track
```

`save_analysis()` 안, `analysis.moods = [Mood(tag=m.tag, score=m.score) for m in result.moods]` 다음 줄에 추가:

```python
    analysis.section_chord_summaries = [
        SectionChordSummaryRow(
            section_label=s.section_label, start_s=s.start_s, end_s=s.end_s,
            roman_progression=json.dumps(s.roman_progression), repeats_of=s.repeats_of,
        )
        for s in result.section_chord_summaries
    ]
    analysis.chord_loops = [
        ChordLoopRow(pattern=json.dumps(loop.pattern), occurrences=json.dumps(loop.occurrences))
        for loop in result.chord_loops
    ]
```

`_to_result()` 안, `moods=[MoodTag(tag=m.tag, score=m.score) for m in analysis.moods],` 다음 줄에 추가:

```python
        section_chord_summaries=[
            SectionChordSummary(
                section_label=s.section_label, start_s=s.start_s, end_s=s.end_s,
                roman_progression=json.loads(s.roman_progression), repeats_of=s.repeats_of,
            )
            for s in analysis.section_chord_summaries
        ],
        chord_loops=[
            ChordLoop(pattern=json.loads(loop.pattern), occurrences=json.loads(loop.occurrences))
            for loop in analysis.chord_loops
        ],
```

- [ ] **Step 5: `core/src/musicna_core/store/__init__.py`에 신규 클래스 export 추가**

파일을 아래 내용으로 교체:

```python
"""SQLite 영속 계층 (SQLAlchemy)."""

from musicna_core.store.db import (
    Analysis,
    Base,
    Chord,
    ChordLoopRow,
    Mood,
    SectionChordSummaryRow,
    SectionRow,
    Track,
    create_session_factory,
)
from musicna_core.store.repository import has_analysis, list_latest_analyses, save_analysis

__all__ = [
    "Analysis",
    "Base",
    "Chord",
    "ChordLoopRow",
    "Mood",
    "SectionChordSummaryRow",
    "SectionRow",
    "Track",
    "create_session_factory",
    "has_analysis",
    "list_latest_analyses",
    "save_analysis",
]
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `uv run pytest core/tests/test_repository.py -v`
Expected: PASS — 전부(3개, 기존 라운드트립 테스트가 신규 필드까지 포함해 통과)

- [ ] **Step 7: 전체 워크스페이스 테스트로 최종 회귀 확인**

Run: `uv run pytest core/tests api/tests tui/tests -v`
Expected: PASS — 전부(기존 161 + 이 계획에서 추가한 테스트 수만큼 늘어남)

- [ ] **Step 8: 커밋**

```bash
git add core/src/musicna_core/store/db.py core/src/musicna_core/store/repository.py core/src/musicna_core/store/__init__.py core/tests/test_repository.py
git commit -m "feat: SectionChordSummary/ChordLoop DB 저장 — 신규 테이블 2개 + 저장소 왕복"
```

---

## Task 6: 문서 갱신

**Files:**
- Modify: `docs/PROGRESS.md`

**Interfaces:** 없음.

- [ ] **Step 1: `docs/PROGRESS.md`의 Phase 3 체크리스트에 항목 추가**

"### Phase 3 — 배치 분석" 섹션의 마지막 체크리스트 항목 다음에 추가:

```markdown
- [x] 코드 진행 추상화 구조(2026-07-26 추가) — `core/analyze/chord_structure.py`: 섹션 단위 로마자 진행 요약(`SectionChordSummary`, 동일 진행 섹션 연결)·구간 무관 반복 패턴 탐지(`ChordLoop`, 최소 4코드). 설계: [2026-07-26-chord-structure-abstraction-design.md](superpowers/specs/2026-07-26-chord-structure-abstraction-design.md), 계획: [2026-07-26-chord-structure-abstraction.md](superpowers/plans/2026-07-26-chord-structure-abstraction.md)
```

- [ ] **Step 2: 작업 로그 표에 한 줄 추가**

`## 작업 로그` 표의 마지막 행 다음에 추가(실제 실행 시점의 테스트 총계로 숫자를 갱신할 것):

```markdown
| 2026-07-26 | 코드 진행 추상화 구조 구현 — `chord_structure.py`(단순화·로마자 변환·섹션 요약·루프 탐지), `analyze_track()` 연결, DB 신규 테이블 2개(`section_chord_summaries`, `chord_loops`) | 신규 ML 의존성 없음(music21 base 의존성만 활용). 전조 대응·기능적 유사 진행 매칭은 백로그(설계 스펙 참조) |
```

- [ ] **Step 3: 커밋**

```bash
git add docs/PROGRESS.md
git commit -m "docs: 코드 진행 추상화 구조 구현 완료 반영"
```

---

## Self-Review 메모

- **스펙 커버리지**: 설계 스펙의 6개 컴포넌트(단순화·로마자 변환, 데이터 모델, 루프 탐지, DB 저장, 파이프라인 연결, 백로그 항목 명시)가 Task 1~5에 전부 매핑됨. 무드 태그 확장은 설계 스펙 자체가 범위 밖으로 명시했으므로 이 계획에도 없음 — 별도 계획.
- **플레이스홀더 스캔**: 없음.
- **타입 일관성**: `RomanEvent`(Task 2)가 Task 3의 `summarize_sections`/`find_chord_loops` 시그니처와 일치. `SectionChordSummary`/`ChordLoop`(Task 1)가 Task 3(생성)·Task 4(파이프라인 채움)·Task 5(DB 왕복) 전체에서 동일 필드명으로 일관되게 쓰임. `to_roman`의 반환값 검증(로마자 표기)은 사전에 실제 music21 실행으로 검증 완료(계획 작성 중 sandbox 테스트로 확인, Global Constraints에 근거 기록).
