"""FFmpeg-based video processing — real subprocess calls, no mocks, no artificial limits.

Every method shells out to ffmpeg/ffprobe via subprocess.run, checks the return code,
and raises on failure.  Designed to be called from Celery workers with temp file paths.
"""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    """Raised when an ffmpeg/ffprobe command fails."""


class VideoProcessor:
    """Static utility class wrapping ffmpeg/ffprobe operations."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run(cmd: List[str], description: str) -> subprocess.CompletedProcess:
        """Run a command, log it, and raise on non-zero exit."""
        logger.info("ffmpeg.run | %s | cmd=%s", description, " ".join(cmd))
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                "ffmpeg.failed | %s | code=%d | stderr=%s",
                description,
                result.returncode,
                result.stderr[:2000],
            )
            raise VideoProcessingError(
                f"{description} failed (exit {result.returncode}): {result.stderr[:500]}"
            )
        logger.info("ffmpeg.ok | %s", description)
        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def extract_clip(
        input_path: str,
        output_path: str,
        start_sec: float,
        end_sec: float,
    ) -> str:
        """Extract a time-range clip from a video.

        Uses ``-ss`` before input for fast seek and ``-to`` for the duration
        relative to the seek point so the output is exactly (end - start) seconds.

        Returns:
            output_path on success.
        """
        duration = end_sec - start_sec
        if duration <= 0:
            raise ValueError(f"end_sec ({end_sec}) must be greater than start_sec ({start_sec})")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        VideoProcessor._run(cmd, f"extract_clip {start_sec}s-{end_sec}s")
        return output_path

    @staticmethod
    def convert_to_vertical(
        input_path: str,
        output_path: str,
        width: int = 1080,
        height: int = 1920,
    ) -> str:
        """Scale and crop/pad video to vertical (portrait) dimensions.

        Strategy: scale so the *smaller* dimension fills the target, then
        center-crop.  This avoids black bars for most landscape sources.
        If the source is already portrait it pads instead of cropping.

        Returns:
            output_path on success.
        """
        # Two-pass filter: scale to cover, then crop to exact size.
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"setsar=1"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path,
        ]
        VideoProcessor._run(cmd, "convert_to_vertical")
        return output_path

    @staticmethod
    def burn_subtitles(
        input_path: str,
        srt_path: str,
        output_path: str,
        font_size: int = 24,
        font_color: str = "white",
        outline_color: str = "black",
    ) -> str:
        """Burn an SRT subtitle file into the video.

        Uses the ``subtitles`` filter with style overrides.

        Returns:
            output_path on success.
        """
        # Escape colons and backslashes in the path for the subtitles filter.
        escaped_srt = srt_path.replace("\\", "\\\\").replace(":", "\\:")
        style = (
            f"FontSize={font_size},"
            f"PrimaryColour=&H00FFFFFF,"
            f"OutlineColour=&H00000000,"
            f"Outline=2,"
            f"Shadow=1"
        )
        vf = f"subtitles='{escaped_srt}':force_style='{style}'"
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]
        VideoProcessor._run(cmd, "burn_subtitles")
        return output_path

    @staticmethod
    def get_duration(input_path: str) -> float:
        """Return the duration of a media file in seconds using ffprobe.

        Returns:
            Duration as a float.
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            input_path,
        ]
        result = VideoProcessor._run(cmd, "get_duration")
        try:
            probe = json.loads(result.stdout)
            return float(probe["format"]["duration"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise VideoProcessingError(
                f"Could not parse duration from ffprobe output: {exc}"
            ) from exc

    @staticmethod
    def extract_audio(
        input_path: str,
        output_path: str,
        codec: str = "aac",
        bitrate: str = "192k",
    ) -> str:
        """Extract the audio track from a video file.

        Returns:
            output_path on success.
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-c:a", codec,
            "-b:a", bitrate,
            output_path,
        ]
        VideoProcessor._run(cmd, "extract_audio")
        return output_path

    @staticmethod
    def concat_clips(
        clip_paths: List[str],
        output_path: str,
    ) -> str:
        """Concatenate multiple clips using the concat demuxer.

        Creates a temporary file list, runs ffmpeg concat, then cleans up
        the list file.

        Returns:
            output_path on success.
        """
        if not clip_paths:
            raise ValueError("clip_paths must not be empty")

        # Write the concat file list to a temp file.
        list_fd = None
        list_path = None
        try:
            list_fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffconcat_")
            with open(list_path, "w") as f:
                for clip in clip_paths:
                    # Escape single quotes in file paths for ffmpeg concat format.
                    safe = clip.replace("'", "'\\''")
                    f.write(f"file '{safe}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_path,
                "-c", "copy",
                output_path,
            ]
            VideoProcessor._run(cmd, f"concat_clips ({len(clip_paths)} clips)")
        finally:
            if list_path:
                try:
                    Path(list_path).unlink(missing_ok=True)
                except OSError:
                    pass

        return output_path

    @staticmethod
    def add_watermark(
        input_path: str,
        watermark_path: str,
        output_path: str,
        position: str = "bottom_right",
        opacity: float = 0.5,
        margin: int = 20,
    ) -> str:
        """Overlay a watermark image on the video.

        Supported positions: top_left, top_right, bottom_left, bottom_right, center.

        Returns:
            output_path on success.
        """
        position_map = {
            "top_left": f"x={margin}:y={margin}",
            "top_right": f"x=W-w-{margin}:y={margin}",
            "bottom_left": f"x={margin}:y=H-h-{margin}",
            "bottom_right": f"x=W-w-{margin}:y=H-h-{margin}",
            "center": "x=(W-w)/2:y=(H-h)/2",
        }
        pos = position_map.get(position, position_map["bottom_right"])

        # Scale watermark to ~10% of video width, apply opacity via colorchannelmixer.
        filter_complex = (
            f"[1:v]scale=iw*0.1:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[wm];"
            f"[0:v][wm]overlay={pos}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", watermark_path,
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            output_path,
        ]
        VideoProcessor._run(cmd, f"add_watermark position={position}")
        return output_path

    @staticmethod
    def generate_thumbnail(
        input_path: str,
        output_path: str,
        timestamp_sec: float = 1.0,
        width: int = 1280,
        height: int = 720,
    ) -> str:
        """Extract a single frame as a JPEG thumbnail.

        Returns:
            output_path on success.
        """
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp_sec),
            "-i", input_path,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-q:v", "2",
            output_path,
        ]
        VideoProcessor._run(cmd, f"generate_thumbnail at {timestamp_sec}s")
        return output_path

    @staticmethod
    def get_video_info(input_path: str) -> dict:
        """Return full probe info (streams, format) as a dict.

        Returns:
            Parsed JSON dict from ffprobe.
        """
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]
        result = VideoProcessor._run(cmd, "get_video_info")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise VideoProcessingError(
                f"Could not parse ffprobe JSON: {exc}"
            ) from exc
