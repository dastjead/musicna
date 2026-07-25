"""무드 태깅 단위 테스트 — laion_clap을 sys.modules 스텁으로 대체해 점수화 로직만 검증.

실제 CLAP 체크포인트 품질 검증은 macOS 스파이크로 수행했다 (docs/PROGRESS.md).
torch가 없는 최소 환경(base 의존성만 설치된 CI)에서는 건너뛴다.
"""

import sys
import types

import pytest

torch = pytest.importorskip("torch")

import musicna_core.analyze.moods as md  # noqa: E402


@pytest.fixture
def fake_clap(monkeypatch):
    clap_mod = types.ModuleType("laion_clap")

    class CLAP_Module:
        def __init__(self, enable_fusion=False, amodel=""):
            pass

        def load_ckpt(self, path):
            self.ckpt = path

        def get_text_embedding(self, prompts, use_tensor=True):
            return torch.eye(len(prompts))

        def get_audio_embedding_from_filelist(self, paths, use_tensor=True):
            v = torch.zeros(1, len(md.MOOD_TAGS))
            v[0, 2] = 1.0  # MOOD_TAGS[2]가 최상위
            v[0, 5] = 0.5  # MOOD_TAGS[5]가 차상위
            return v

    clap_mod.CLAP_Module = CLAP_Module
    hub_mod = types.ModuleType("huggingface_hub")
    hub_mod.hf_hub_download = lambda repo_id, filename: "/fake/ckpt.pt"
    monkeypatch.setitem(sys.modules, "laion_clap", clap_mod)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub_mod)
    monkeypatch.setattr(md, "_MODEL_CACHE", {})


def test_tag_moods_ranks_by_similarity(fake_clap, tmp_path):
    moods = md.tag_moods(tmp_path / "x.wav", top_k=3)
    assert [m.tag for m in moods[:2]] == [md.MOOD_TAGS[2], md.MOOD_TAGS[5]]
    assert moods[0].score > moods[1].score >= moods[2].score
    assert all(0.0 <= m.score <= 1.0 for m in moods)


def test_model_cache_reuses_instance(fake_clap, tmp_path):
    md.tag_moods(tmp_path / "a.wav")
    cached = md._MODEL_CACHE["clap"]
    md.tag_moods(tmp_path / "b.wav")
    assert md._MODEL_CACHE["clap"] is cached


def test_missing_clap_raises_helpful_error(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "laion_clap", None)  # import 실패 유도
    monkeypatch.setattr(md, "_MODEL_CACHE", {})
    with pytest.raises(ImportError, match="uv sync --extra mood"):
        md.tag_moods(tmp_path / "x.wav")
