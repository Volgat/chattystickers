"""
ChattyStickers — TTS Engine
Converts text to speech using gTTS (free) with language auto-detection.
Produces MP3 + WAV output for use in animation assembly.
"""

import os
import re
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()


def detect_language(text: str) -> str:
    """Simple language detection based on common French words."""
    french_words = [
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "je",
        "tu",
        "il",
        "elle",
        "nous",
        "vous",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "son",
        "sa",
        "est",
        "sont",
        "dans",
        "avec",
        "pour",
        "sur",
        "du",
        "et",
        "ou",
        "dit",
        "salut",
        "bonjour",
        "merci",
        "oui",
        "non",
        "en",
        "dansant",
        "chante",
        "riant",
        "triste",
        "heureux",
        "chat",
    ]
    text_lower = text.lower()
    words = re.findall(r"\b\w+\b", text_lower)
    french_count = sum(1 for w in words if w in french_words)
    if french_count >= 1:
        return "fr"
    return "en"


def generate_voice(
    text: str,
    session_id: str,
    output_dir: str,
    speed_slow: bool = False,
) -> dict:
    """
    Generate a voice audio file from text using gTTS.

    Args:
        text: Speech text to synthesize
        session_id: Unique session ID
        output_dir: Directory to save output
        speed_slow: If True, use slow speech rate

    Returns:
        dict with keys: mp3_path, duration_estimate_s, language
    """
    os.makedirs(output_dir, exist_ok=True)

    language = detect_language(text)
    mp3_path = os.path.join(output_dir, f"{session_id}_voice.mp3")

    print(f"[TTS] Generating voice: lang={language}, text='{text[:60]}'")

    tts = gTTS(text=text, lang=language, slow=speed_slow)
    tts.save(mp3_path)

    # Estimate duration: average 150 words/min = 2.5 words/sec
    word_count = len(text.split())
    duration_estimate = max(1.5, word_count / 2.5)

    print(f"[TTS] Voice saved -> {mp3_path} (~{duration_estimate:.1f}s)")

    return {
        "mp3_path": mp3_path,
        "duration_estimate_s": duration_estimate,
        "language": language,
        "text": text,
    }
