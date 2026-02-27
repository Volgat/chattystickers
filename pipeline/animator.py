"""
ChattyStickers — Animator
Creates animated sticker frames from a static image.
Applies motion effects based on emotion (dancing, talking, bouncing).
Assembles frames into an animated GIF (usable as sticker).
"""

import os
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance


# Animation presets per emotion style
ANIMATION_PRESETS = {
    "happy": {
        "bounce_amplitude": 15,
        "bounce_speed": 0.25,
        "rotation_max": 5,
        "scale_pulse": 0.06,
        "frames": 24,
        "fps": 12,
    },
    "dancing": {
        "bounce_amplitude": 25,
        "bounce_speed": 0.3,
        "rotation_max": 15,
        "scale_pulse": 0.08,
        "frames": 30,
        "fps": 15,
    },
    "singing": {
        "bounce_amplitude": 10,
        "bounce_speed": 0.15,
        "rotation_max": 3,
        "scale_pulse": 0.12,
        "frames": 24,
        "fps": 12,
    },
    "sad": {
        "bounce_amplitude": 5,
        "bounce_speed": 0.12,
        "rotation_max": 2,
        "scale_pulse": 0.02,
        "frames": 20,
        "fps": 8,
    },
    "greeting": {
        "bounce_amplitude": 18,
        "bounce_speed": 0.28,
        "rotation_max": 10,
        "scale_pulse": 0.05,
        "frames": 24,
        "fps": 12,
    },
    "surprised": {
        "bounce_amplitude": 30,
        "bounce_speed": 0.35,
        "rotation_max": 3,
        "scale_pulse": 0.18,
        "frames": 20,
        "fps": 12,
    },
    "cool": {
        "bounce_amplitude": 8,
        "bounce_speed": 0.18,
        "rotation_max": 5,
        "scale_pulse": 0.04,
        "frames": 20,
        "fps": 10,
    },
}

DEFAULT_PRESET = ANIMATION_PRESETS["happy"]


def _get_preset(animation_style: str) -> dict:
    return ANIMATION_PRESETS.get(animation_style.lower(), DEFAULT_PRESET)


def _apply_talking_effect(img: Image.Image, intensity: float) -> Image.Image:
    """Simulate talking by slightly scaling the bottom part of the image."""
    w, h = img.size
    bottom_crop = img.crop((0, h // 2, w, h))
    new_h = int((h // 2) * (1 + intensity * 0.05))
    bottom_scaled = bottom_crop.resize((w, new_h), Image.LANCZOS)
    result = Image.new("RGBA", (w, h + new_h - h // 2), (0, 0, 0, 0))
    result.paste(img.crop((0, 0, w, h // 2)), (0, 0))
    result.paste(
        bottom_scaled,
        (0, h // 2),
        bottom_scaled if bottom_scaled.mode == "RGBA" else None,
    )
    return result.resize((w, h), Image.LANCZOS)


def _make_frame(
    base_img: Image.Image,
    frame_idx: int,
    total_frames: int,
    preset: dict,
    canvas_size: int = 512,
) -> Image.Image:
    """Generate a single animation frame."""
    t = frame_idx / total_frames  # 0 to 1 normalized
    angle_rad = 2 * math.pi * t

    # Bounce effect (vertical oscillation)
    bounce_y = int(preset["bounce_amplitude"] * math.sin(angle_rad * 2))

    # Rotation oscillation
    rotation = preset["rotation_max"] * math.sin(angle_rad)

    # Scale pulse (breathing effect)
    scale = 1.0 + preset["scale_pulse"] * math.sin(angle_rad * 2)

    # Talking intensity (for speech frames)
    talk_intensity = max(0, math.sin(angle_rad * 3))

    # Get base dimensions
    base_w, base_h = base_img.size

    # Apply scale
    new_w = int(base_w * scale)
    new_h = int(base_h * scale)
    scaled = base_img.resize((new_w, new_h), Image.LANCZOS)

    # Apply rotation
    rotated = scaled.rotate(rotation, expand=False, resample=Image.BICUBIC)

    # Create transparent canvas
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))

    # Center + bounce
    paste_x = (canvas_size - rotated.width) // 2
    paste_y = (canvas_size - rotated.height) // 2 + bounce_y

    # Paste with alpha mask
    if rotated.mode == "RGBA":
        canvas.paste(rotated, (paste_x, paste_y), rotated)
    else:
        canvas.paste(rotated, (paste_x, paste_y))

    return canvas


def create_animated_sticker(
    image_path: str,
    animation_style: str,
    session_id: str,
    output_dir: str,
    speech_duration_s: float = 2.0,
) -> dict:
    """
    Create an animated sticker GIF from a static image.

    Args:
        image_path: Path to source PNG sticker image
        animation_style: Emotion style for the animation
        session_id: Unique session identifier
        output_dir: Directory to save outputs
        speech_duration_s: Duration of speech (affects frame count)

    Returns:
        dict with gif_path, frame_count, fps, duration_s
    """
    os.makedirs(output_dir, exist_ok=True)
    preset = _get_preset(animation_style)

    # Adjust frame count to match speech duration
    target_duration = max(speech_duration_s, 1.5)
    frames_needed = int(target_duration * preset["fps"])
    # Loop minimum preset frames
    total_frames = max(frames_needed, preset["frames"])

    print(
        f"[Animator] Style={animation_style}, frames={total_frames}, fps={preset['fps']}"
    )

    # Load base image
    base_img = Image.open(image_path).convert("RGBA")
    base_img = base_img.resize((420, 420), Image.LANCZOS)

    # Generate frames
    frames = []
    for i in range(total_frames):
        frame = _make_frame(base_img, i, total_frames, preset, canvas_size=512)
        # Convert to RGB for GIF compatibility (P mode)
        frame_rgb = Image.new("RGBA", frame.size, (255, 255, 255, 0))
        frame_rgb.paste(frame, mask=frame.split()[3] if frame.mode == "RGBA" else None)
        frames.append(frame_rgb)

    # Save animated GIF
    gif_path = os.path.join(output_dir, f"{session_id}_animated.gif")
    frame_duration_ms = int(1000 / preset["fps"])

    frames[0].save(
        gif_path,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        disposal=2,
    )

    duration_s = total_frames / preset["fps"]
    print(
        f"[Animator] GIF saved -> {gif_path} ({total_frames} frames, {duration_s:.1f}s)"
    )

    return {
        "gif_path": gif_path,
        "frame_count": total_frames,
        "fps": preset["fps"],
        "duration_s": duration_s,
        "animation_style": animation_style,
        "frames": frames,  # Keep in memory for MP4 export
    }
