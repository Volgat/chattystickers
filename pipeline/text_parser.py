"""
ChattyStickers — Text Parser
Parses user input into structured generation parameters.
"""

import re
import json

# Emotion keywords -> animation style & visual tone
EMOTION_MAP = {
    "heureux": ("happy", "bright and colorful"),
    "triste": ("sad", "soft blue tones"),
    "en colere": ("angry", "fiery red tones"),
    "amoureux": ("love", "pink and hearts"),
    "surpris": ("surprised", "wide eyes and sparkles"),
    "dansant": ("dancing", "vibrant energetic"),
    "chante": ("singing", "musical notes around"),
    "dort": ("sleepy", "dreamy soft pastel"),
    "riant": ("laughing", "bright yellow"),
    "salut": ("greeting", "waving and cheerful"),
    "bonjour": ("greeting", "waving and cheerful"),
    "cool": ("cool", "stylish dark tones with sunglasses"),
    "happy": ("happy", "bright and colorful"),
    "sad": ("sad", "soft blue tones"),
    "dance": ("dancing", "vibrant energetic"),
    "sing": ("singing", "musical notes around"),
    "hello": ("greeting", "waving and cheerful"),
}

SUBJECT_MAP = {
    "chat": "cute cartoon cat",
    "chien": "cute cartoon dog",
    "lapin": "cute cartoon rabbit",
    "ours": "cute cartoon bear",
    "panda": "cute cartoon panda",
    "robot": "cute cartoon robot",
    "alien": "cute cartoon alien",
    "fille": "cute cartoon girl",
    "garcon": "cute cartoon boy",
    "moi": "cute cartoon avatar",
    "je": "cute cartoon avatar",
    "cat": "cute cartoon cat",
    "dog": "cute cartoon dog",
    "bear": "cute cartoon bear",
}


def detect_subject(phrase: str) -> str:
    phrase_lower = phrase.lower()
    for key, val in SUBJECT_MAP.items():
        if key in phrase_lower:
            return val
    return "cute cartoon character"


def detect_emotion_and_style(phrase: str):
    phrase_lower = phrase.lower()
    for key, (anim_style, visual_style) in EMOTION_MAP.items():
        if key in phrase_lower:
            return anim_style, visual_style
    return "happy", "bright and colorful"


def extract_speech_text(phrase: str) -> str:
    """Extract quoted speech text, or use the whole phrase."""
    matches = re.findall(r"['\"\u00ab\u00bb]([^'\"<>]+)['\"\u00ab\u00bb]", phrase)
    if matches:
        return matches[0]
    return phrase


def inject_audio_tags(speech_text: str, emotion: str) -> str:
    """Inject Bark-specific tags [laughter], [musical], [whispering] based on emotion/text."""
    text_lower = speech_text.lower()

    # Emotional tag injection for Bark
    if "joyeux anniversaire" in text_lower or "happy birthday" in text_lower:
        return f"♪ Happy Birthday! [laughter] {speech_text} ♪"

    if emotion == "laughing" or "riant" in text_lower or "laugh" in text_lower:
        return f"[laughter] {speech_text}"

    if emotion == "singing" or "chante" in text_lower:
        return f"♪ {speech_text} ♪"

    if "chuchote" in text_lower or "whisper" in text_lower:
        return f"[whispering] {speech_text}"

    return speech_text


def parse_phrase(phrase: str) -> dict:
    """
    Parse a user phrase into sticker generation parameters.
    Tries local heuristic parsing. Simple, fast, no API needed.

    Returns:
        dict with keys: subject, emotion, speech_text, animation_style, image_style, image_prompt
    """
    subject = detect_subject(phrase)
    emotion, image_style = detect_emotion_and_style(phrase)
    raw_speech_text = extract_speech_text(phrase)

    # NEW: Enhanced speech text with expressive tags
    speech_text = inject_audio_tags(raw_speech_text, emotion)

    # Build a rich DALL-E/SD style prompt
    image_prompt = (
        f"{subject}, {emotion} expression, {image_style}, "
        f"sticker style, clean white background, high detail, cute, "
        f"cartoon illustration, chibi style, 2D flat design"
    )

    return {
        "subject": subject,
        "emotion": emotion,
        "speech_text": speech_text,
        "animation_style": emotion,
        "image_style": image_style,
        "image_prompt": image_prompt,
        "original_phrase": phrase,
    }


if __name__ == "__main__":
    test = "Mon chat dit 'Salut !' en dansant"
    result = parse_phrase(test)
    try:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except UnicodeEncodeError:
        print(json.dumps(result, indent=2, ensure_ascii=True))
