"""
ChattyStickers — Unified Multimedia Sticker Exporter
Produces a SINGLE self-contained multimedia file (MP4 with embedded audio).
The MP4 is the primary "talking sticker" — animation + voice in one file.

Secondary exports (GIF, animated WebP) are also produced for platforms
that don't support MP4 stickers (legacy WhatsApp, Some Telegram builds).

Output hierarchy:
  PRIMARY  → {session_id}_sticker.mp4  (animation + voice merged)
  SECONDARY→ {session_id}_sticker.gif  (silent animation, loop)
  SECONDARY→ {session_id}_sticker.webp (silent animation, WhatsApp native)
"""

import os
import shutil
import subprocess

import numpy as np
import imageio
from PIL import Image


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _frames_to_webm_silent(frames: list, fps: int, dest: str) -> bool:
    """Write PIL frames to a silent WebM file. Returns True on success."""
    if not frames:
        return False
    try:
        # Use VP9 for high quality and transparency support (though currently RGB)
        writer = imageio.get_writer(
            dest, fps=fps, codec="libvpx-vp9", quality=8, macro_block_size=None
        )
        for frame in frames:
            if isinstance(frame, Image.Image):
                writer.append_data(np.array(frame.convert("RGB")))
        writer.close()
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception as e:
        print(f"[Exporter] Silent WebM write error: {e}")
        return False


def _merge_audio_ffmpeg(
    video_path: str, audio_path: str, dest: str, duration_s: float
) -> bool:
    """
    Merge a video file with an audio file using ffmpeg.
    Uses VP9 + Opus for standard WebM stickers.
    Returns True on success.
    """
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            video_path,
            "-stream_loop",
            "-1",  # loop audio if needed
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "libopus",  # WebM standard audio
            "-b:a",
            "64k",
            "-shortest",
            "-movflags",
            "+faststart",
            dest,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        if result.returncode == 0 and os.path.getsize(dest) > 0:
            return True
        else:
            print(f"[Exporter] ffmpeg merge error: {result.stderr.decode()[:300]}")
            return False
    except FileNotFoundError:
        print("[Exporter] ffmpeg not found in PATH — trying bundled imageio-ffmpeg")
        return _merge_audio_imageio_ffmpeg(video_path, audio_path, dest)
    except Exception as e:
        print(f"[Exporter] ffmpeg exception: {e}")
        return False


def _merge_audio_imageio_ffmpeg(video_path: str, audio_path: str, dest: str) -> bool:
    """Fallback: use imageio-ffmpeg's bundled ffmpeg binary."""
    try:
        import imageio_ffmpeg

        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            video_path,
            "-stream_loop",
            "-1",
            "-i",
            audio_path,
            "-c:v",
            "copy",
            "-c:a",
            "libopus",
            "-b:a",
            "64k",
            "-shortest",
            "-movflags",
            "+faststart",
            dest,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=90)
        return result.returncode == 0 and os.path.getsize(dest) > 0
    except Exception as e:
        print(f"[Exporter] imageio-ffmpeg fallback error: {e}")
        return False


# ─── Primary: Unified WebM with embedded audio ─────────────────────────────────


def export_unified_webm(
    frames: list,
    audio_mp3_path: str,
    session_id: str,
    output_dir: str,
    fps: int = 12,
    animation_duration_s: float = 3.0,
) -> str:
    """
    Create the PRIMARY unified talking sticker: WebM video + audio embedded.

    Returns:
        Path to the unified WebM sticker
    """
    os.makedirs(output_dir, exist_ok=True)
    final_path = os.path.join(output_dir, f"{session_id}_sticker.webm")
    silent_path = os.path.join(output_dir, f"{session_id}_silent_tmp.webm")

    if not frames:
        print("[Exporter] No frames — cannot create WebM")
        return ""

    print(f"[Exporter] Writing unified WebM ({len(frames)} frames @ {fps}fps)...")

    # Step 1: silent WebM
    ok_silent = _frames_to_webm_silent(frames, fps, silent_path)
    if not ok_silent:
        print("[Exporter] Silent WebM failed")
        return ""

    # Step 2: merge audio
    has_audio = (
        audio_mp3_path
        and os.path.exists(audio_mp3_path)
        and os.path.getsize(audio_mp3_path) > 1000
    )
    if has_audio:
        merged = _merge_audio_ffmpeg(
            silent_path, audio_mp3_path, final_path, animation_duration_s
        )
        if merged:
            try:
                os.remove(silent_path)
            except OSError:
                pass
            print(f"[Exporter] OK: Unified WebM+audio -> {final_path}")
            return final_path
        else:
            print("[Exporter] Audio merge failed — using silent WebM as fallback")

    # Fallback: rename silent WebM as the sticker
    shutil.move(silent_path, final_path)
    print(f"[Exporter] WARN: Silent WebM (no audio merge) -> {final_path}")
    return final_path


# ─── Secondary: GIF ───────────────────────────────────────────────────────────


def export_gif(frames: list, session_id: str, output_dir: str, fps: int = 12) -> str:
    """Export animated GIF (secondary format, loop, solid bg for robust playback)."""
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, f"{session_id}_sticker.gif")
    if not frames:
        return ""

    rgb_frames = []
    for f in frames:
        if isinstance(f, Image.Image):
            bg = Image.new("RGB", f.size, (255, 255, 255))
            if f.mode == "RGBA":
                bg.paste(f, mask=f.split()[3])
            else:
                bg = f.convert("RGB")
            rgb_frames.append(np.array(bg))

    try:
        # Use imageio's GIF writer, which is vastly more reliable for looping animations
        imageio.mimsave(dest, rgb_frames, format="GIF", fps=fps, loop=0)
        print(f"[Exporter] GIF -> {dest}")
        return dest
    except Exception as e:
        print(f"[Exporter] GIF error: {e}")
        return ""


# ─── Secondary: Animated WebP ─────────────────────────────────────────────────


def export_animated_webp(
    frames: list, session_id: str, output_dir: str, fps: int = 12
) -> str:
    """Export animated WebP (secondary, for WhatsApp/Telegram native sticker)."""
    os.makedirs(output_dir, exist_ok=True)
    dest = os.path.join(output_dir, f"{session_id}_sticker.webp")
    if not frames:
        return ""
    frame_ms = int(1000 / fps)
    rgba = [f.convert("RGBA") for f in frames if isinstance(f, Image.Image)]
    if not rgba:
        return ""
    try:
        rgba[0].save(
            dest,
            format="WEBP",
            save_all=True,
            append_images=rgba[1:],
            duration=frame_ms,
            loop=0,
            lossless=False,
            quality=85,
            method=4,
        )
        print(f"[Exporter] WebP -> {dest}")
        return dest
    except Exception as e:
        print(f"[Exporter] WebP error: {e}")
        return ""


# ─── Master export function ────────────────────────────────────────────────────


def export_all_formats(
    animation_result: dict,
    audio_mp3_path: str,
    session_id: str,
    output_dir: str,
) -> dict:
    """
    Export the unified sticker in all formats.

    Returns:
        {
          "webm": path (PRIMARY — animation + voice, the talking sticker),
          "gif":  path (secondary — silent loop),
          "webp": path (secondary — WhatsApp/Telegram compatible),
        }
    """
    frames = animation_result.get("frames", [])
    fps = animation_result.get("fps", 12)
    duration_s = animation_result.get("duration_s", 3.0)

    os.makedirs(output_dir, exist_ok=True)
    exports = {}

    # PRIMARY: unified WebM + voice
    exports["webm"] = export_unified_webm(
        frames=frames,
        audio_mp3_path=audio_mp3_path,
        session_id=session_id,
        output_dir=output_dir,
        fps=fps,
        animation_duration_s=duration_s,
    )

    # SECONDARY: GIF
    exports["gif"] = export_gif(frames, session_id, output_dir, fps)

    # SECONDARY: animated WebP
    exports["webp"] = export_animated_webp(frames, session_id, output_dir, fps)

    return exports
