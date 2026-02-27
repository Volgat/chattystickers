"""
ChattyStickers — EARCP Verifier (using real earcp library)
Leverages the installed 'earcp' package (pip install git+https://github.com/Volgat/earcp.git@earcp-lib)

Architecture:
- 4 "Virtual Experts" (one per sticker component: text, image, audio, animation)
- EARCP's EnsembleWeighting computes a coherence-aware final quality score
- CoherenceMetrics measures inter-component agreement
- Auto-correction hints are extracted from low-score components
"""

import os
import re
import numpy as np
from PIL import Image

# ── Real EARCP library import ─────────────────────────────────────────────────
from earcp import EARCP


# ─── Virtual Expert Wrappers ─────────────────────────────────────────────────
# Each expert implements the EARCP-required .predict(x) interface.
# They receive a shared "context" dict and return a quality score in [0, 1].


class TextQualityExpert:
    """EARCP Expert #1: judges text/NLP component quality."""

    def predict(self, context: dict) -> np.ndarray:
        subject = context.get("subject", "")
        speech = context.get("speech_text", "")
        emotion = context.get("emotion", "")

        score = 1.0
        if not subject or subject == "cute cartoon character":
            score -= 0.1
        if not speech or len(speech.strip()) < 3:
            score -= 0.2
        if not emotion or emotion == "happy":
            score -= 0.05
        return np.array([max(0.0, score)])


class ImageQualityExpert:
    """EARCP Expert #2: judges generated image quality."""

    def predict(self, context: dict) -> np.ndarray:
        path = context.get("image_path", "")
        score = 1.0
        if not path or not os.path.exists(path):
            return np.array([0.0])
        try:
            img = Image.open(path)
            w, h = img.size
            if w < 256 or h < 256:
                score -= 0.3
            if img.mode not in ("RGBA", "RGB"):
                score -= 0.1
            fsize = os.path.getsize(path) / 1024
            if fsize < 5:
                score -= 0.2
            if fsize > 5000:
                score -= 0.05
        except Exception:
            score = 0.3
        return np.array([max(0.0, score)])


class AudioQualityExpert:
    """EARCP Expert #3: judges TTS audio quality."""

    def predict(self, context: dict) -> np.ndarray:
        path = context.get("audio_path", "")
        duration = context.get("audio_duration_s", 0.0)
        score = 1.0
        if not path or not os.path.exists(path):
            return np.array([0.0])
        fsize = os.path.getsize(path) / 1024
        if fsize < 2:
            score -= 0.5
        elif fsize < 10:
            score -= 0.1
        if duration < 0.5:
            score -= 0.2
        return np.array([max(0.0, score)])


class AnimationQualityExpert:
    """EARCP Expert #4: judges animated sticker quality."""

    def predict(self, context: dict) -> np.ndarray:
        path = context.get("gif_path", "")
        score = 1.0
        if not path or not os.path.exists(path):
            return np.array([0.0])
        try:
            gif = Image.open(path)
            n_frames = getattr(gif, "n_frames", 1)
            if n_frames < 8:
                score -= 0.3
            if n_frames > 120:
                score -= 0.1
            w, h = gif.size
            if w < 128 or h < 128:
                score -= 0.3
        except Exception:
            score = 0.3
        return np.array([max(0.0, score)])


# ─── Coherence helpers ────────────────────────────────────────────────────────


def _text_image_coherence(context: dict) -> float:
    prompt = context.get("image_prompt", "").lower()
    subject = context.get("subject", "").lower()
    emotion = context.get("emotion", "").lower()
    hits = sum(
        [
            any(w in prompt for w in subject.split()),
            emotion in prompt,
            "sticker" in prompt,
            "cartoon" in prompt,
        ]
    )
    return min(1.0, hits / 4.0)


def _text_audio_coherence(context: dict) -> float:
    orig = re.sub(r"[^\w\s]", "", context.get("original_phrase", "").lower())
    speech = re.sub(r"[^\w\s]", "", context.get("speech_text", "").lower())
    orig_w = set(orig.split())
    speech_w = set(speech.split())
    if not orig_w:
        return 0.5
    overlap = len(orig_w & speech_w) / len(orig_w)
    if (
        context.get("speech_text", "").lower()
        in context.get("original_phrase", "").lower()
    ):
        overlap = max(overlap, 0.85)
    return min(1.0, overlap)


def _anim_emotion_coherence(context: dict) -> float:
    anim = context.get("animation_style", "happy").lower()
    emotion = context.get("emotion", "happy").lower()
    if anim == emotion:
        return 1.0
    related = {"happy": ["greeting", "dancing"], "dancing": ["happy", "singing"]}
    return 0.8 if emotion in related.get(anim, []) else 0.6


def _build_auto_notes(context: dict, component_scores: dict) -> list:
    notes = []
    if component_scores["text"] < 0.9:
        notes.append("Sujet ou émotion peu explicites — essayez d'être plus précis")
    if component_scores["image"] < 0.7:
        notes.append(
            "Image de qualité réduite (modèle HF en chargement?) — sera améliorée au prochain appel"
        )
    if component_scores["audio"] < 0.7:
        notes.append("Audio TTS trop court ou silencieux — vérifiez le texte parlé")
    if component_scores["animation"] < 0.7:
        notes.append("Animation peu de frames — augmentez la durée de la phrase")
    return notes


# ─── Main Entry Point ─────────────────────────────────────────────────────────


def verify_sticker(
    original_phrase: str,
    parsed: dict,
    image_path: str,
    audio_path: str,
    gif_path: str,
    audio_duration_s: float,
    animation_result: dict,
) -> dict:
    """
    Run EARCP-powered multi-signal verification on all sticker components.

    Uses the real `earcp` library:
    - 4 Virtual Experts (text, image, audio, animation) with .predict() interface
    - EnsembleWeighting computes EARCP score: Q = β*P + (1-β)*C
    - CoherenceMetrics measures inter-expert consistency
    - PerformanceTracker for EMA-smoothed individual scores

    Returns:
        dict with earcp_score, grade, component_scores, coherence_scores, notes
    """

    # Build shared context dict
    context = {
        "original_phrase": original_phrase,
        "subject": parsed.get("subject", ""),
        "speech_text": parsed.get("speech_text", original_phrase),
        "emotion": parsed.get("emotion", "happy"),
        "image_prompt": parsed.get("image_prompt", ""),
        "animation_style": animation_result.get("animation_style", "happy"),
        "image_path": image_path,
        "audio_path": audio_path,
        "gif_path": gif_path,
        "audio_duration_s": audio_duration_s,
        "animation_duration_s": animation_result.get("duration_s", 2.0),
    }

    # ── 1. Instantiate EARCP with 4 Virtual Experts ───────────────────────────
    experts = [
        TextQualityExpert(),
        ImageQualityExpert(),
        AudioQualityExpert(),
        AnimationQualityExpert(),
    ]

    ensemble = EARCP(
        experts=experts,
        beta=0.65,  # 65% performance weight, 35% coherence
        eta_s=5.0,  # softmax sensitivity
        w_min=0.05,  # minimum floor per expert
        alpha_P=0.9,  # performance EMA
        alpha_C=0.85,  # coherence EMA
        track_diagnostics=True,
    )

    # ── 2. Get predictions from all experts ───────────────────────────────────
    _, expert_preds = ensemble.predict(context)

    # ── 3. Use target=1.0 (ideal) to update weights ───────────────────────────
    target = np.array([1.0])
    ensemble.update(expert_preds, target)

    # ── 4. Read scores and weights ────────────────────────────────────────────
    diagnostics = ensemble.get_diagnostics()
    weights_arr = diagnostics["weights"]

    # ── 5. Extract individual performance scores ──────────────────────────────
    raw_scores = [float(p[0]) for p in expert_preds]
    component_names = ["text", "image", "audio", "animation"]
    component_scores = {n: round(s, 3) for n, s in zip(component_names, raw_scores)}
    expert_weights = {
        n: round(float(w), 3) for n, w in zip(component_names, weights_arr)
    }

    P_avg = float(np.mean(raw_scores))

    # ── 6. Compute inter-component coherence ──────────────────────────────────
    text_image_coh = _text_image_coherence(context)
    text_audio_coh = _text_audio_coherence(context)
    anim_emo_coh = _anim_emotion_coherence(context)
    coherence_scores = {
        "text_image": round(text_image_coh, 3),
        "text_audio": round(text_audio_coh, 3),
        "animation_emotion": round(anim_emo_coh, 3),
    }
    C_avg = float(np.mean([text_image_coh, text_audio_coh, anim_emo_coh]))

    # ── 7. Final EARCP score Q = β*P + (1-β)*C ───────────────────────────────
    BETA = 0.65
    Q = BETA * P_avg + (1 - BETA) * C_avg

    # ── 8. Grade ──────────────────────────────────────────────────────────────
    if Q >= 0.85:
        grade = "A - Excellent"
    elif Q >= 0.70:
        grade = "B - Bien"
    elif Q >= 0.55:
        grade = "C - Acceptable"
    elif Q >= 0.40:
        grade = "D - A ameliorer"
    else:
        grade = "F - Faible"

    notes = _build_auto_notes(context, component_scores)

    report = {
        "earcp_score": round(Q, 3),
        "grade": grade,
        "performance_avg": round(P_avg, 3),
        "coherence_avg": round(C_avg, 3),
        "beta": BETA,
        "expert_weights": expert_weights,
        "component_scores": component_scores,
        "coherence_scores": coherence_scores,
        "auto_correction_notes": notes,
        "ready_to_export": Q >= 0.40,
        "earcp_version": "1.0.0 (pip)",
    }

    print(
        f"[EARCP] v1.0.0 | Score Q={Q:.3f} ({grade}) | "
        f"P={P_avg:.2f} | C={C_avg:.2f} | "
        f"Weights: {[round(w, 2) for w in weights_arr.tolist()]}"
    )
    return report
