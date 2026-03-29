"""
Pollinations.ai image generation service.
Free API — no key required. Supports FLUX, SD, DreamShaper models.
"""

import urllib.parse
import random
import httpx
from typing import Optional

from bot.config import (
    POLLINATIONS_API_KEY,
    POLLINATIONS_MODEL,
    POLLINATIONS_WIDTH,
    POLLINATIONS_HEIGHT,
    STYLE_PRESETS,
)

BASE_URL = "https://gen.pollinations.ai/image"


def build_prompt(
    user_prompt: str,
    style_name: Optional[str] = None,
    selfie_description: Optional[str] = None,
) -> str:
    """
    Build a rich generation prompt.
    - If a style preset is selected, inject its suffix.
    - Always add quality boosters.
    """
    parts = []

    # Base subject — if user uploaded selfie we reference it
    if selfie_description:
        parts.append(selfie_description)

    # User's own text
    parts.append(user_prompt.strip())

    # Style preset suffix
    if style_name and style_name in STYLE_PRESETS:
        parts.append(STYLE_PRESETS[style_name])

    # Universal quality boosters
    parts.append(
        "masterpiece, best quality, ultra detailed, sharp focus, 8K resolution"
    )

    return ", ".join(p for p in parts if p)


def generate_image_url(
    prompt: str,
    model: str = POLLINATIONS_MODEL,
    width: int = POLLINATIONS_WIDTH,
    height: int = POLLINATIONS_HEIGHT,
    seed: Optional[int] = None,
) -> str:
    """
    Construct the Pollinations.ai image URL.
    The URL itself IS the generation trigger (GET request returns the image).
    """
    if seed is None:
        seed = random.randint(1, 2_000_000)

    encoded_prompt = urllib.parse.quote(prompt)

    url = (
        f"{BASE_URL}/{encoded_prompt}"
        f"?model={model}"
        f"&width={width}"
        f"&height={height}"
        f"&seed={seed}"
        f"&nologo=true"
        f"&enhance=true"
        f"&safe=true"
    )
    if POLLINATIONS_API_KEY:
        url += f"&key={POLLINATIONS_API_KEY}"
    return url


async def generate_image(
    prompt: str,
    style_name: Optional[str] = None,
    selfie_description: Optional[str] = None,
    model: str = POLLINATIONS_MODEL,
) -> tuple[bytes, str]:
    """
    Generate an image and return (image_bytes, image_url).
    Makes a real HTTP GET to Pollinations.ai which returns the image binary.
    Timeout: 120 seconds (60s recommended for Vercel Pro).
    """
    full_prompt = build_prompt(prompt, style_name, selfie_description)
    url = generate_image_url(full_prompt, model=model)

    headers = {}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content, url
    except httpx.TimeoutException:
        raise Exception(
            "Image generation timed out. This can happen on free hosting plans "
            "with low timeout limits. Try again or use a host with higher timeout."
        )


async def generate_image_with_reference(
    prompt: str,
    reference_image_url: str,
    style_name: Optional[str] = None,
    model: str = "flux",
) -> tuple[bytes, str]:
    """
    Image-to-image generation using the selfie as reference.
    Supports both URLs and base64 data URLs.
    """
    full_prompt = build_prompt(prompt, style_name)
    seed = random.randint(1, 2_000_000)
    encoded_prompt = urllib.parse.quote(full_prompt)

    if reference_image_url.startswith("data:image"):
        b64_data = reference_image_url.split(",", 1)[1]
        image_param = f"data:image/jpeg;base64,{urllib.parse.quote(b64_data)}"
    else:
        image_param = urllib.parse.quote(reference_image_url)

    url = (
        f"{BASE_URL}/{encoded_prompt}"
        f"?model={model}"
        f"&width={POLLINATIONS_WIDTH}"
        f"&height={POLLINATIONS_HEIGHT}"
        f"&seed={seed}"
        f"&nologo=true"
        f"&enhance=true"
        f"&image={image_param}"
    )
    if POLLINATIONS_API_KEY:
        url += f"&key={POLLINATIONS_API_KEY}"

    headers = {}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.content, url
