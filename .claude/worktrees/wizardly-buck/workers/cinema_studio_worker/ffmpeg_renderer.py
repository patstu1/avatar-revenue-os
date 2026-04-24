"""Internal FFmpeg compositor — produces real H.264 .mp4 from a reference image.

Ported from NEWCINEMA's runInternalRenderer() (functions/src/video_generation.ts:303-408).
Applies a Ken Burns zoom-and-pan effect on a single still image.

This is a motion compositor, NOT an AI generative video engine.
It produces a real playable .mp4 file. No fake progress, no placeholder URLs.

Requires: ffmpeg available on PATH (confirmed in aro-worker-generation container).
"""

import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class RenderError(Exception):
    """Raised when ffmpeg rendering fails."""


def _parse_resolution(resolution: str = "1080p") -> tuple[int, int]:
    """Map resolution label to (width, height)."""
    r = resolution.strip().lower()
    if r == "720p":
        return (1280, 720)
    if r in ("4k", "2160p"):
        return (3840, 2160)
    return (1920, 1080)  # default 1080p


def _parse_duration(seconds: Optional[float] = None) -> float:
    """Clamp duration to 2-30 seconds."""
    if not seconds or seconds < 2:
        return 6.0
    return min(seconds, 30.0)


def _download_image(url: str, dest: Path) -> None:
    """Download a reference image from URL to local path."""
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
    except httpx.HTTPError as e:
        raise RenderError(f"Failed to download reference image: {e}") from e


def _generate_canvas(dest: Path, width: int, height: int) -> None:
    """Generate a solid black canvas frame using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s={width}x{height}:d=1",
        "-frames:v", "1",
        str(dest),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        raise RenderError(f"Canvas generation failed: {result.stderr.decode()[:500]}")


def _verify_ffmpeg() -> str:
    """Verify ffmpeg is available and return path."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RenderError("ffmpeg not found on PATH")
    return ffmpeg_path


def render_ken_burns(
    ref_image_url: Optional[str] = None,
    duration_seconds: Optional[float] = None,
    resolution: str = "1080p",
    aspect_ratio: str = "16:9",
    on_progress: Optional[Callable[[int], None]] = None,
) -> dict:
    """Render a Ken Burns motion video from a reference image.

    Args:
        ref_image_url: URL of the input image. If None, generates a black canvas.
        duration_seconds: Video duration (2-30s, default 6s).
        resolution: "720p", "1080p", or "4k".
        aspect_ratio: Aspect ratio string (informational, resolution drives actual size).
        on_progress: Optional callback receiving progress 0-100.

    Returns:
        dict with:
            - "mp4_path": Path to the rendered .mp4 file (caller must clean up)
            - "cover_path": Path to the extracted cover PNG
            - "width": int
            - "height": int
            - "duration": float
            - "fps": int
            - "codec": str
    """
    _verify_ffmpeg()

    w, h = _parse_resolution(resolution)
    duration = _parse_duration(duration_seconds)
    fps = 30
    total_frames = int(duration * fps)

    # Create temp directory for this render
    tmp_dir = tempfile.mkdtemp(prefix="studio_render_")
    render_id = uuid.uuid4().hex[:12]
    input_img = Path(tmp_dir) / f"{render_id}-in.jpg"
    out_mp4 = Path(tmp_dir) / f"{render_id}-out.mp4"
    cover_png = Path(tmp_dir) / f"{render_id}-cover.png"

    try:
        # Step 1: Get input image
        if ref_image_url:
            _download_image(ref_image_url, input_img)
        else:
            _generate_canvas(input_img, w, h)

        if on_progress:
            on_progress(15)

        # Step 2: Render Ken Burns video with ffmpeg
        # Zoompan filter: gentle zoom-in with centered pan
        zoom_expr = "zoom+0.001"
        filter_chain = (
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
            f"zoompan=z='{zoom_expr}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
            f":d={total_frames}:s={w}x{h}:fps={fps}"
        )

        render_cmd = [
            "ffmpeg", "-y",
            "-i", str(input_img),
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-crf", "20",
            "-preset", "veryfast",
            "-t", str(duration),
            str(out_mp4),
        ]

        logger.info(
            "ffmpeg_render_start",
            extra={"render_id": render_id, "resolution": f"{w}x{h}", "duration": duration},
        )

        result = subprocess.run(
            render_cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            stderr = result.stderr.decode()[:1000]
            raise RenderError(f"ffmpeg render failed (exit {result.returncode}): {stderr}")

        if not out_mp4.is_file() or out_mp4.stat().st_size == 0:
            raise RenderError("ffmpeg produced no output file")

        if on_progress:
            on_progress(85)

        # Step 3: Extract cover frame at 50% mark
        midpoint = duration / 2
        cover_cmd = [
            "ffmpeg", "-y",
            "-i", str(out_mp4),
            "-ss", str(midpoint),
            "-frames:v", "1",
            str(cover_png),
        ]

        cover_result = subprocess.run(cover_cmd, capture_output=True, timeout=60)
        if cover_result.returncode != 0:
            logger.warning("Cover frame extraction failed, continuing without cover")
            cover_png = None

        if on_progress:
            on_progress(95)

        file_size = out_mp4.stat().st_size
        logger.info(
            "ffmpeg_render_complete",
            extra={
                "render_id": render_id,
                "file_size": file_size,
                "resolution": f"{w}x{h}",
                "duration": duration,
            },
        )

        return {
            "mp4_path": str(out_mp4),
            "cover_path": str(cover_png) if cover_png and cover_png.is_file() else None,
            "width": w,
            "height": h,
            "duration": duration,
            "fps": fps,
            "codec": "h264",
            "file_size": file_size,
            "tmp_dir": tmp_dir,  # caller MUST clean this up
        }

    except RenderError:
        # Clean up on failure
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RenderError(f"Unexpected render error: {e}") from e


def cleanup_render(tmp_dir: str) -> None:
    """Remove temporary render directory. Call after uploading the output."""
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
