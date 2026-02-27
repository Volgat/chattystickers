"""
ChattyStickers — Image Generator
Generates sticker images via HuggingFace Inference API.
Uses stabilityai/stable-diffusion-xl-base-1.0 (free, high quality).
Falls back to a Pillow-generated placeholder if API fails.
"""

import os
import io
import time
import requests
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

# Primary: FLUX / SDXL — high quality models on HF Router
HF_IMAGE_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "runwayml/stable-diffusion-v1-5",
]

HF_API_BASE = "https://router.huggingface.co/hf-inference/models"


def generate_image_from_hf(prompt: str, output_path: str) -> str:
    """
    Attempt to generate an image via HuggingFace Inference API.
    Tries multiple models. Returns output path on success.
    """
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "num_inference_steps": 25,
            "guidance_scale": 7.5,
            "width": 512,
            "height": 512,
        },
    }

    for model in HF_IMAGE_MODELS:
        api_url = f"{HF_API_BASE}/{model}"
        print(f"[ImageGen] Trying model: {model}")

        max_retries = 4
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    api_url, headers=headers, json=payload, timeout=60
                )
                if response.status_code == 200:
                    img = Image.open(io.BytesIO(response.content))
                    img = img.convert("RGBA")
                    img = img.resize((512, 512), Image.LANCZOS)
                    img = _apply_rounded_corners(img, radius=60)
                    img.save(output_path, "PNG")
                    print(f"[ImageGen] Success with {model} -> {output_path}")
                    return output_path
                elif response.status_code == 503:
                    estimated_time = response.json().get("estimated_time", 10)
                    wait_time = min(estimated_time, 15)
                    print(
                        f"[ImageGen] Model {model} is loading. Waiting {wait_time}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    print(
                        f"[ImageGen] {model} returned {response.status_code}: {response.text[:200]}"
                    )
                    break  # Break retry loop, try next model
            except Exception as e:
                try:
                    print(f"[ImageGen] Error with {model}: {e}")
                except UnicodeEncodeError:
                    print(
                        f"[ImageGen] Error with {model}: [Exception contains special characters]"
                    )
                break  # Break retry loop, try next model

    # All models failed → generate beautiful placeholder
    print("[ImageGen] All HF models failed. Generating placeholder.")
    return generate_placeholder_image(prompt, output_path)


def _apply_rounded_corners(img: Image.Image, radius: int) -> Image.Image:
    """Apply rounded corners mask to image."""
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    result = Image.new("RGBA", img.size, (0, 0, 0, 0))
    result.paste(img, mask=mask)
    return result


def generate_placeholder_image(prompt: str, output_path: str) -> str:
    """
    Generate an attractive placeholder image when API is unavailable.
    Creates a colorful gradient sticker with emoji and text.
    """
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background
    for y in range(size):
        r = int(255 * (1 - y / size) * 0.8 + 100)
        g = int(180 * (y / size) + 60)
        b = int(220 * (y / size) * 0.7 + 80)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Rounded corners
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (size, size)], radius=80, fill=255)
    img.putalpha(mask)

    # Add a friendly emoji-like face
    cx, cy = size // 2, size // 2 - 30
    # Head
    draw.ellipse([cx - 120, cy - 120, cx + 120, cy + 120], fill=(255, 220, 140, 255))
    # Eyes
    draw.ellipse([cx - 45, cy - 40, cx - 15, cy - 10], fill=(50, 50, 50, 255))
    draw.ellipse([cx + 15, cy - 40, cx + 45, cy - 10], fill=(50, 50, 50, 255))
    # Smile
    draw.arc(
        [cx - 50, cy + 10, cx + 50, cy + 70],
        start=10,
        end=170,
        fill=(50, 50, 50, 255),
        width=8,
    )
    # Cheeks
    draw.ellipse([cx - 90, cy + 10, cx - 50, cy + 50], fill=(255, 180, 160, 160))
    draw.ellipse([cx + 50, cy + 10, cx + 90, cy + 50], fill=(255, 180, 160, 160))

    # Text label at bottom
    label = prompt[:30] + "..." if len(prompt) > 30 else prompt
    draw.rounded_rectangle(
        [20, size - 90, size - 20, size - 20], radius=20, fill=(0, 0, 0, 140)
    )

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    draw.text(
        (size // 2, size - 55), label, fill=(255, 255, 255, 255), anchor="mm", font=font
    )

    img.save(output_path, "PNG")
    print(f"[ImageGen] Placeholder saved -> {output_path}")
    return output_path


def generate_sticker_image(image_prompt: str, session_id: str, output_dir: str) -> str:
    """
    Main entry point for image generation.

    Args:
        image_prompt: Detailed prompt describing the sticker
        session_id: Unique session identifier
        output_dir: Directory to save output file

    Returns:
        Path to generated PNG image
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{session_id}_sticker.png")
    return generate_image_from_hf(image_prompt, output_path)
