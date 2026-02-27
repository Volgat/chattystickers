import os
import re
import requests
import time
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
# Bark is excellent for expressive audio
BARK_MODEL = "suno/bark-small"
HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{BARK_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}


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
        "joyeux",
        "anniversaire",
    ]
    text_lower = text.lower()
    words = re.findall(r"\b\w+\b", text_lower)
    french_count = sum(1 for w in words if w in french_words)
    if french_count >= 1:
        return "fr"
    return "en"


def generate_voice_bark(text: str, session_id: str, output_dir: str) -> str:
    """Generate expressive audio using Bark via HuggingFace Inference API."""
    mp3_path = os.path.join(output_dir, f"{session_id}_voice_bark.mp3")

    # Bark tags: [laughter], [whispering], [musical], [clears throat], etc.
    # We clean the text if it has too many [brackets] just in case
    try:
        print(f"[Bark] Generating expressive audio for: {text[:50]}...")
    except UnicodeEncodeError:
        print(
            f"[Bark] Generating expressive audio for: [Text contains special characters]..."
        )

    # Bark API expectation: simple text input
    # It returns audio/flac or audio/mpeg
    retries = 3
    for i in range(retries):
        try:
            response = requests.post(
                HF_API_URL, headers=HEADERS, json={"inputs": text}, timeout=60
            )
            if response.status_code == 200:
                with open(mp3_path, "wb") as f:
                    f.write(response.content)
                return mp3_path
            elif response.status_code == 503:
                print(
                    f"[Bark] Model loading (503), retrying in 10s... ({i + 1}/{retries})"
                )
                time.sleep(10)
            else:
                print(f"[Bark] Error {response.status_code}: {response.text}")
                break
        except Exception as e:
            print(f"[Bark] Exception: {e}")
            break
    return None


def generate_voice(
    text: str,
    session_id: str,
    output_dir: str,
    use_expressive: bool = True,
    speed_slow: bool = False,
) -> dict:
    """
    Main TTS entry point. Routes to Bark for expressive audio if requested,
    otherwise falls back to gTTS.
    """
    os.makedirs(output_dir, exist_ok=True)
    language = detect_language(text)

    # Decide between Bark (Expressive) and gTTS (Standard)
    # We use Bark if 'expressive' is requested AND it's likely a short emotional phrase
    # or if it contains special tags.
    is_emotional = any(
        tag in text.lower()
        for tag in [
            "[laughter]",
            "[music]",
            "happy birthday",
            "joyeux anniversaire",
            "laughing",
        ]
    )

    audio_path = None
    engine = "gTTS"

    if use_expressive and (is_emotional or len(text) < 150):
        audio_path = generate_voice_bark(text, session_id, output_dir)
        if audio_path:
            engine = "Bark (Expressive AI)"

    if not audio_path:
        # Fallback to gTTS
        mp3_path = os.path.join(output_dir, f"{session_id}_voice.mp3")
        try:
            print(f"[TTS] Using gTTS: lang={language}, text='{text[:60]}'")
        except UnicodeEncodeError:
            print(
                f"[TTS] Using gTTS: lang={language}, text='[Text contains special characters]'"
            )
        tts = gTTS(text=text, lang=language, slow=speed_slow)
        tts.save(mp3_path)
        audio_path = mp3_path
        engine = "gTTS (Standard)"

    # Estimate duration: average 150 words/min = 2.5 words/sec for gTTS
    # Bark might be slightly different but this is a good baseline for lip-sync
    word_count = len(text.replace("[", "").replace("]", "").split())
    duration_estimate = max(
        1.5, word_count / 2.0
    )  # slightly slower for more natural feel

    print(f"[TTS] Voice saved -> {audio_path} (~{duration_estimate:.1f}s) via {engine}")

    return {
        "mp3_path": audio_path,
        "duration_estimate_s": duration_estimate,
        "language": language,
        "text": text,
        "engine": engine,
    }
