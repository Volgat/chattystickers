"""
ChattyStickers — Flask API Server
Main entry point: orchestrates the full AI sticker generation pipeline.
"""

import os
import uuid
import json
import time
import traceback
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from pipeline.text_parser import parse_phrase
from pipeline.image_generator import generate_sticker_image
from pipeline.tts_engine import generate_voice
from pipeline.animator import create_animated_sticker
from pipeline.earcp_verifier import verify_sticker
from pipeline.sticker_exporter import export_all_formats

load_dotenv()

app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Static Frontend ──────────────────────────────────────────────────────────


@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


# ── Health Check ─────────────────────────────────────────────────────────────


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ChattyStickers", "version": "1.0.0"})


# ── Main Generation Endpoint ─────────────────────────────────────────────────


@app.route("/api/generate", methods=["POST"])
def generate():
    """
    POST /api/generate
    Body: {"phrase": "Mon chat dit 'Salut !' en dansant"}

    Returns JSON with:
      - session_id
      - parsed parameters
      - file paths (relative URLs for browser)
      - earcp_report (quality scores)
      - export_urls (gif, webp, mp4)
    """
    data = request.get_json()
    if not data or "phrase" not in data:
        return jsonify({"error": "Missing 'phrase' in request body"}), 400

    phrase = data["phrase"].strip()
    if not phrase:
        return jsonify({"error": "Phrase cannot be empty"}), 400

    if len(phrase) > 500:
        return jsonify({"error": "Phrase too long (max 500 chars)"}), 400

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(OUTPUT_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    start_time = time.time()

    try:
        # ── Step 1: Parse phrase ─────────────────────────────────
        print(f"\n[{session_id}] === ChattyStickers Pipeline Start ===")
        print(f"[{session_id}] Phrase: {phrase}")
        parsed = parse_phrase(phrase)
        print(f"[{session_id}] Parsed: {json.dumps(parsed, ensure_ascii=False)}")

        # ── Step 2: Generate image ────────────────────────────────
        image_path = generate_sticker_image(
            image_prompt=parsed["image_prompt"],
            session_id=session_id,
            output_dir=session_dir,
        )

        # ── Step 3: Generate voice ────────────────────────────────
        tts_result = generate_voice(
            text=parsed["speech_text"],
            session_id=session_id,
            output_dir=session_dir,
        )
        audio_path = tts_result["mp3_path"]
        audio_duration = tts_result["duration_estimate_s"]

        # ── Step 4: Create animation ──────────────────────────────
        animation_result = create_animated_sticker(
            image_path=image_path,
            animation_style=parsed["animation_style"],
            session_id=session_id,
            output_dir=session_dir,
            speech_duration_s=audio_duration,
        )
        gif_path = animation_result["gif_path"]

        # ── Step 5: EARCP Verification ────────────────────────────
        earcp_report = verify_sticker(
            original_phrase=phrase,
            parsed=parsed,
            image_path=image_path,
            audio_path=audio_path,
            gif_path=gif_path,
            audio_duration_s=audio_duration,
            animation_result=animation_result,
        )

        # ── Step 6: Export formats ────────────────────────────────
        exports = export_all_formats(
            animation_result=animation_result,
            audio_mp3_path=audio_path,
            session_id=session_id,
            output_dir=session_dir,
        )

        elapsed = round(time.time() - start_time, 2)
        print(f"[{session_id}] === Pipeline Done in {elapsed}s ===\n")

        # Build response with relative URLs for frontend
        def to_url(path: str) -> str:
            if path and os.path.exists(path):
                rel = os.path.relpath(path, os.path.dirname(__file__))
                return "/" + rel.replace("\\", "/")
            return None

        # Primary unified sticker = WebM with audio embedded
        unified_webm = exports.get("webm", "")
        preview_gif = gif_path  # for inline preview (faster to load)

        return jsonify(
            {
                "success": True,
                "session_id": session_id,
                "elapsed_s": elapsed,
                "parsed": {
                    "subject": parsed["subject"],
                    "emotion": parsed["emotion"],
                    "speech_text": parsed["speech_text"],
                    "animation_style": parsed["animation_style"],
                    "language": tts_result["language"],
                },
                # PRIMARY: unified talking sticker (animation + voice in one file)
                "sticker": {
                    "url": to_url(unified_webm),  # The talking sticker WebM
                    "preview_gif": to_url(preview_gif),  # GIF for quick browser preview
                    "preview_image": to_url(image_path),
                    "type": "webm",
                    "has_audio": True,
                    "description": "Talking Sticker (Native WebM)",
                },
                # SECONDARY: additional export formats
                "export_urls": {
                    "webm": to_url(exports.get("webm", "")),
                    "gif": to_url(exports.get("gif", "")),
                    "webp": to_url(exports.get("webp", "")),
                },
                "earcp_report": earcp_report,
            }
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[{session_id}] ERROR: {e}\n{tb}")
        return jsonify(
            {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "traceback": tb,
            }
        ), 500


# ── File Serving ─────────────────────────────────────────────────────────────


@app.route("/output/<path:filename>")
def serve_output(filename):
    """Serve generated output files."""
    return send_from_directory(OUTPUT_DIR, filename)


# ── Download Endpoint ─────────────────────────────────────────────────────────


@app.route("/api/download/<session_id>/<format>")
def download_sticker(session_id, format):
    """Download a specific sticker format."""
    allowed_formats = {"gif": "image/gif", "webp": "image/webp", "webm": "video/webm"}
    if format not in allowed_formats:
        return jsonify({"error": "Invalid format"}), 400

    session_dir = os.path.join(OUTPUT_DIR, session_id)
    filename = f"{session_id}_sticker.{format}"
    filepath = os.path.join(session_dir, filename)

    if not os.path.exists(filepath):
        return jsonify({"error": f"File not found: {filename}"}), 404

    return send_file(
        filepath,
        mimetype=allowed_formats[format],
        as_attachment=True,
        download_name=f"chattysticker_{session_id}.{format}",
    )


if __name__ == "__main__":
    print("=" * 60)
    print("  ChattyStickers — AI Animated Talking Sticker Generator")
    print("  http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)
