"""musicna 분석 코어.

플랫폼 독립 파이프라인: 오디오 파일 경로를 입력받아 구조화된 분석 결과를 돌려준다.
macOS 전용 코드(캡처, AppleScript)는 이 패키지에 두지 않는다 — capture-macos/와 api 측 세션 매니저 담당.
"""

from musicna_core.models import AnalysisResult, ChordEvent, MoodTag, Section, TrackMeta

__all__ = ["AnalysisResult", "ChordEvent", "MoodTag", "Section", "TrackMeta"]
