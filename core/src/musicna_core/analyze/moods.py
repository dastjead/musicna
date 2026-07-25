"""CLAP zero-shot 무드 태깅 (laion-clap).

laion-clap은 optional extra: `uv sync --extra mood`
- music 특화 체크포인트(LAION 공식 배포) 사용 — 최초 호출 시 HF hub에서 다운로드(≈2.2GB, 캐시됨)
- 스파이크(2026-07-25, macOS 실캡처 2트랙): 업템포 곡 → energetic/happy, 저레벨 잔잔한 곡 →
  dreamy/calm으로 청감과 일치 확인. 체크포인트 로드 후 추론은 트랙당 수 초
- 이 모듈은 import 시점에 laion_clap을 요구하지 않는다 (지연 import)
"""

from pathlib import Path
from typing import Any

from musicna_core.models import MoodTag

# 스파이크에서 검증한 무드 태그 세트 — 변경 시 DB 축적 일관성을 위해 engine_versions와 함께 기록됨
MOOD_TAGS = [
    "happy", "sad", "energetic", "calm", "romantic", "melancholic",
    "dark", "uplifting", "relaxing", "aggressive", "nostalgic", "dreamy",
]
_PROMPT = "This music feels {tag}"
_CKPT_REPO = "lukewys/laion_clap"
_CKPT_FILE = "music_audioset_epoch_15_esc_90.14.pt"
_SOFTMAX_TEMPERATURE = 0.05  # 코사인 유사도(≈0.1~0.3 범위)를 대비 있는 분포로 변환
_TOP_K = 5

_MODEL_CACHE: dict[str, Any] = {}


def _load_model() -> Any:
    try:
        import laion_clap
    except ImportError as e:
        raise ImportError(
            "laion-clap이 설치되지 않았습니다. `uv sync --extra mood`로 설치하세요."
        ) from e

    if "clap" not in _MODEL_CACHE:
        from huggingface_hub import hf_hub_download

        ckpt = hf_hub_download(repo_id=_CKPT_REPO, filename=_CKPT_FILE)
        model = laion_clap.CLAP_Module(enable_fusion=False, amodel="HTSAT-base")
        model.load_ckpt(ckpt)
        _MODEL_CACHE["clap"] = model
    return _MODEL_CACHE["clap"]


def tag_moods(audio_path: Path, top_k: int = _TOP_K) -> list[MoodTag]:
    """오디오의 무드 태그 상위 top_k를 (태그, softmax 점수)로 돌려준다."""
    import torch

    model = _load_model()
    prompts = [_PROMPT.format(tag=t) for t in MOOD_TAGS]
    with torch.no_grad():
        text_emb = model.get_text_embedding(prompts, use_tensor=True)
        audio_emb = model.get_audio_embedding_from_filelist([str(audio_path)], use_tensor=True)
        sims = (audio_emb @ text_emb.T)[0]
        probs = torch.softmax(sims / _SOFTMAX_TEMPERATURE, dim=0)
    order = torch.argsort(probs, descending=True)[:top_k]
    return [MoodTag(tag=MOOD_TAGS[i], score=round(float(probs[i]), 4)) for i in order]
