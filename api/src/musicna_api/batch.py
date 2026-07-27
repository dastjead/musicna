"""배치 분석 오케스트레이터 — 캡처 산출물(WAV + TrackMeta 사이드카 JSON)을 일괄 분석해 DB에 축적.

실행: uv run musicna-analyze [--audio-dir data/audio] [--midi-dir data/midi] [--db data/musicna.db]

- MIDI가 없으면 muscriptor로 전사 (미설치 환경에서는 경고 후 MIDI 없이 분석 — 키/코드 제외)
- 이미 분석된 트랙(title/artist/captured_at 동일)은 건너뛴다 (--force로 재분석)
"""

import argparse
import logging
from pathlib import Path

from musicna_core.analyze import analyze_track
from musicna_core.models import TrackMeta
from musicna_core.store import create_session_factory, has_analysis, save_analysis

logger = logging.getLogger(__name__)


def analyze_captured(
    audio_dir: Path,
    midi_dir: Path,
    db_path: str,
    model_size: str = "large",
    force: bool = False,
) -> dict[str, int]:
    """audio_dir의 WAV+JSON 쌍을 분석해 DB에 저장하고 {analyzed, skipped, failed} 집계를 돌려준다."""
    factory = create_session_factory(db_path)
    counts = {"analyzed": 0, "skipped": 0, "failed": 0}
    transcribe_available = True

    for wav_path in sorted(audio_dir.glob("*.wav")):
        json_path = wav_path.with_suffix(".json")
        if not json_path.exists():
            logger.warning("사이드카 JSON 없음, 건너뜀: %s", wav_path.name)
            counts["skipped"] += 1
            continue
        meta = TrackMeta.model_validate_json(json_path.read_text(encoding="utf-8"))

        with factory() as session:
            if not force and has_analysis(session, meta):
                counts["skipped"] += 1
                continue

            midi_path = midi_dir / f"{wav_path.stem}.mid"
            try:
                if not midi_path.exists() and transcribe_available:
                    try:
                        from musicna_core.transcribe import transcribe_to_midi

                        transcribe_to_midi(wav_path, midi_path, model_size=model_size)
                    except ImportError as e:
                        logger.warning("%s — MIDI 없이 분석 진행 (키/코드 제외)", e)
                        transcribe_available = False

                result = analyze_track(wav_path, midi_path if midi_path.exists() else None, meta)
                save_analysis(session, result, audio_path=str(wav_path))
                counts["analyzed"] += 1
                try:
                    wav_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("WAV 삭제 실패(무시, 디스크에 남음): %s", wav_path.name)
                logger.info("분석 완료: %s — key=%s %s, 코드 %d개, 구간 %d개",
                            meta.title, result.key, result.mode, len(result.chords), len(result.sections))
            except Exception:
                logger.exception("분석 실패: %s", wav_path.name)
                counts["failed"] += 1

    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="캡처된 트랙 일괄 분석 → SQLite 축적")
    parser.add_argument("--audio-dir", type=Path, default=Path("data/audio"))
    parser.add_argument("--midi-dir", type=Path, default=Path("data/midi"))
    parser.add_argument("--db", default="data/musicna.db")
    parser.add_argument("--model-size", default="large", choices=["small", "medium", "large"])
    parser.add_argument("--force", action="store_true", help="이미 분석된 트랙도 재분석")
    args = parser.parse_args()

    args.midi_dir.mkdir(parents=True, exist_ok=True)
    counts = analyze_captured(args.audio_dir, args.midi_dir, args.db, args.model_size, args.force)
    print(f"완료: 분석 {counts['analyzed']}, 건너뜀 {counts['skipped']}, 실패 {counts['failed']}")
