"""코드 진행 추상화 — 상세 코드 흐름(chords.py) 위에 곡 전체 구조 파악용 계층을 추가한다.

코드 심볼을 트라이어드 품질로 단순화하고 곡 전체 key/mode 기준 로마자로 변환한다.
로마자 변환은 `roman.romanNumeralFromChord(...).figure`를 직접 쓰지 않는다 — 감화음이
1·4·5도에 오면 `.figure`가 일관성 없는 부가 기호("io5b3")를 붙이는 것을 실측으로 확인해,
scaleDegree + quality + frontAlterationAccidental을 조합해 직접 구성한다.
"""

from collections import defaultdict
from dataclasses import dataclass

from music21 import harmony, key as m21key, roman

from musicna_core.models import ChordEvent, ChordLoop, Section, SectionChordSummary

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


def _is_primitive(pattern: tuple[str, ...]) -> bool:
    """패턴 자체가 더 짧은 주기의 반복(부분적 반복 포함)이 아닌지 확인한다.

    예: (I, V, I, V)는 (I, V)가 2회 반복된 것이라 원시(primitive) 패턴이 아니다 — 이런 패턴을
    루프 후보로 받아들이면, 실제로는 더 짧은 주기가 반복되는 상황을 "긴 패턴이 적게 반복"하는
    것으로 잘못 보고하게 된다(4회 이상 반복 시 관찰된 버그).

    주기가 패턴 길이를 나누어떨어지게 하는 경우(온전한 정수배 반복)뿐 아니라, 예를 들어
    (I, V, vi, IV, I, V, vi)처럼 길이 7이 주기 4로 나누어떨어지지 않아도 앞쪽 주기가 그대로
    이어지는 "부분 반복" 역시 같은 종류의 버그를 재현하므로 함께 배제해야 한다. 이를 위해
    period가 length를 나눠떨어지게 하는지는 따지지 않고, 유효한 모든 위치에서
    pattern[i] == pattern[i + period]가 성립하는지만 확인한다(문자열 이론에서의 일반적인
    "주기" 정의).
    """
    n = len(pattern)
    for period in range(1, n):
        if all(pattern[i] == pattern[i + period] for i in range(n - period)):
            return False
    return True


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
            window = tuple(romans[start : start + length])
            if not _is_primitive(window):
                continue
            groups[window].append(start)

        for pattern, starts in groups.items():
            occurrence_starts: list[int] = []
            last_end = -1
            for start in starts:
                if any(claimed[start : start + length]):
                    continue
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
