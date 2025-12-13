import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Handles FFmpeg video processing operations."""

    def __init__(self):
        self.ffmpeg_path = "ffmpeg"
        self.ffprobe_path = "ffprobe"

    def get_video_info(self, input_path: str) -> Dict:
        """Extract video metadata using ffprobe."""
        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                input_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            video_stream = next(
                (s for s in info.get("streams", []) if s["codec_type"] == "video"),
                None
            )

            if not video_stream:
                raise ValueError("No video stream found")

            return {
                "duration": float(info["format"].get("duration", 0)),
                "size": int(info["format"].get("size", 0)),
                "bitrate": int(info["format"].get("bit_rate", 0)),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "codec": video_stream.get("codec_name"),
                "fps": eval(video_stream.get("r_frame_rate", "0/1"))
            }
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")
            raise

    def transcode(
        self,
        input_path: str,
        output_path: str,
        codec: str = "libx264",
        preset: str = "medium",
        crf: int = 23,
        audio_codec: str = "aac",
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Transcode video to different format/codec."""

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-c:v", codec,
            "-preset", preset,
            "-crf", str(crf),
            "-c:a", audio_codec,
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-y",
            output_path
        ]

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def compress(
        self,
        input_path: str,
        output_path: str,
        target_size_mb: Optional[float] = None,
        scale: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Compress video with optional target size."""

        video_info = self.get_video_info(input_path)
        duration = video_info["duration"]

        cmd = [self.ffmpeg_path, "-i", input_path]

        if target_size_mb:
            # Calculate target bitrate
            target_bitrate = int((target_size_mb * 8192) / duration) - 128  # Leave room for audio
            cmd.extend(["-b:v", f"{target_bitrate}k", "-maxrate", f"{target_bitrate * 1.5}k", "-bufsize", f"{target_bitrate * 2}k"])

        if scale:
            cmd.extend(["-vf", f"scale={scale}"])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-y",
            output_path
        ])

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def add_watermark(
        self,
        input_path: str,
        output_path: str,
        watermark_path: str,
        position: str = "bottom-right",
        opacity: float = 0.7,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Add watermark to video."""

        position_map = {
            "top-left": "10:10",
            "top-right": "W-w-10:10",
            "bottom-left": "10:H-h-10",
            "bottom-right": "W-w-10:H-h-10",
            "center": "(W-w)/2:(H-h)/2"
        }

        overlay_pos = position_map.get(position, "W-w-10:H-h-10")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-i", watermark_path,
            "-filter_complex", f"[1]format=rgba,colorchannelmixer=aa={opacity}[wm];[0][wm]overlay={overlay_pos}",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            "-y",
            output_path
        ]

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def generate_thumbnail(
        self,
        input_path: str,
        output_path: str,
        timestamp: str = "00:00:01",
        size: str = "1280x720",
        image_fit: str = "cover",
        image_format: str = "webp",
        image_quality: int = 75,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Generate thumbnail from video.
        
        Args:
            input_path: Path to input video file
            output_path: Path for output thumbnail (extension will be auto-corrected)
            timestamp: Time position to capture thumbnail from
            size: Target size as "WIDTHxHEIGHT" (e.g., "1280x720")
            image_fit: How to handle aspect ratio mismatch:
                - "cover": Scale to fill, crop excess (default)
                - "contain": Fit inside, add black bars
                - "none": Force exact size (may distort)
            image_format: Output format - "webp", "jpg", or "png"
            image_quality: Quality 0-100 (higher is better, ignored for PNG)
            progress_callback: Optional callback for progress updates
        """
        # Parse size dimensions
        width, height = size.replace(":", "x").split("x")
        
        # Build video filter based on image_fit mode
        vf_filter = self._build_thumbnail_filter(width, height, image_fit)
        
        # Correct output path extension based on image_format
        output_path = self._correct_thumbnail_extension(output_path, image_format)
        
        # Build quality arguments based on format
        quality_args = self._get_thumbnail_quality_args(image_format, image_quality)
        
        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-ss", timestamp,
            "-vframes", "1",
            "-vf", vf_filter,
        ]
        cmd.extend(quality_args)
        cmd.extend([
            "-progress", "pipe:1",
            "-y",
            output_path
        ])

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def _build_thumbnail_filter(self, width: str, height: str, image_fit: str) -> str:
        """Build FFmpeg video filter string for thumbnail generation."""
        if image_fit == "cover":
            # Scale to fill, then crop from center to exact dimensions
            return f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-{width})/2:(ih-{height})/2"
        elif image_fit == "contain":
            # Scale to fit inside, pad with black bars
            return f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        else:
            # "none" - force exact size (legacy behavior, may distort)
            return f"scale={width}:{height}"

    def _correct_thumbnail_extension(self, output_path: str, image_format: str) -> str:
        """Correct output path extension to match the specified image format."""
        path = Path(output_path)
        
        extension_map = {
            "webp": ".webp",
            "jpg": ".jpg",
            "jpeg": ".jpg",
            "png": ".png"
        }
        
        correct_ext = extension_map.get(image_format.lower(), ".webp")
        
        # Replace extension if it doesn't match
        if path.suffix.lower() != correct_ext:
            return str(path.with_suffix(correct_ext))
        
        return output_path

    def _get_thumbnail_quality_args(self, image_format: str, quality: int) -> List[str]:
        """Get format-specific quality arguments for thumbnail generation."""
        # Clamp quality to valid range
        quality = max(0, min(100, quality))
        
        if image_format.lower() == "png":
            # PNG is lossless, no quality param needed
            return []
        elif image_format.lower() == "webp":
            # WebP uses 0-100 scale (higher is better)
            return ["-quality", str(quality)]
        else:
            # JPEG uses q:v with 2-31 scale (lower is better)
            # Convert 0-100 to 31-2 range
            jpeg_quality = int(31 - (quality * 29 / 100))
            jpeg_quality = max(2, min(31, jpeg_quality))
            return ["-q:v", str(jpeg_quality)]

    def extract_audio(
        self,
        input_path: str,
        output_path: str,
        audio_format: str = "mp3",
        bitrate: str = "192k",
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Extract audio from video."""

        codec_map = {
            "mp3": "libmp3lame",
            "aac": "aac",
            "wav": "pcm_s16le",
            "flac": "flac"
        }

        codec = codec_map.get(audio_format, "libmp3lame")

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-vn",
            "-c:a", codec,
            "-b:a", bitrate,
            "-progress", "pipe:1",
            "-y",
            output_path
        ]

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def create_gif(
        self,
        input_path: str,
        output_path: str,
        start_time: str = "00:00:00",
        duration: int = 5,
        fps: int = 10,
        scale: int = 480,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Convert video segment to GIF."""

        cmd = [
            self.ffmpeg_path,
            "-ss", start_time,
            "-t", str(duration),
            "-i", input_path,
            "-vf", f"fps={fps},scale={scale}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0",
            "-progress", "pipe:1",
            "-y",
            output_path
        ]

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def concatenate_videos(
        self,
        input_paths: List[str],
        output_path: str,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Concatenate multiple videos."""

        # Create a temporary file list
        concat_file = Path(output_path).parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for path in input_paths:
                f.write(f"file '{path}'\n")

        try:
            cmd = [
                self.ffmpeg_path,
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                "-progress", "pipe:1",
                "-y",
                output_path
            ]

            return self._execute_ffmpeg(cmd, input_paths[0], progress_callback)
        finally:
            if concat_file.exists():
                concat_file.unlink()

    def trim_video(
        self,
        input_path: str,
        output_path: str,
        start_time: str,
        end_time: Optional[str] = None,
        duration: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Trim video to specific duration."""

        cmd = [
            self.ffmpeg_path,
            "-i", input_path,
            "-ss", start_time
        ]

        if end_time:
            cmd.extend(["-to", end_time])
        elif duration:
            cmd.extend(["-t", str(duration)])

        cmd.extend([
            "-c", "copy",
            "-progress", "pipe:1",
            "-y",
            output_path
        ])

        return self._execute_ffmpeg(cmd, input_path, progress_callback)

    def _execute_ffmpeg(
        self,
        cmd: List[str],
        input_path: str,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """Execute FFmpeg command with progress tracking."""

        start_time = datetime.now()

        try:
            # Get total duration for progress calculation
            video_info = self.get_video_info(input_path)
            total_duration = video_info["duration"]

            logger.info(f"Executing: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            # Parse progress
            for line in process.stdout:
                if progress_callback:
                    # Parse out_time_ms from ffmpeg progress
                    match = re.search(r'out_time_ms=(\d+)', line)
                    if match:
                        current_ms = int(match.group(1))
                        current_sec = current_ms / 1_000_000
                        progress_pct = min(100, (current_sec / total_duration) * 100) if total_duration > 0 else 0
                        progress_callback(progress_pct)

            process.wait()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            return {
                "success": True,
                "processing_time": processing_time,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }

        except Exception as e:
            logger.error(f"FFmpeg execution failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
