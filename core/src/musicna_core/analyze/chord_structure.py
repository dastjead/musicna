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
