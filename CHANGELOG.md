# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Aspect ratio handling for thumbnails**: New `image_fit` parameter with three modes:
  - `cover` (default): Scales to fill the target dimensions and crops excess from center
  - `contain`: Fits inside target dimensions with black letterbox/pillarbox bars
  - `none`: Forces exact dimensions (legacy behavior, may distort)

- **Multiple image format support**: New `image_format` parameter supporting:
  - `webp` (default): Modern format with excellent compression and quality
  - `jpg`: Universal JPEG format for maximum compatibility
  - `png`: Lossless format for highest quality

- **Quality control**: New `image_quality` parameter (0-100 scale) with automatic format-specific conversion:
  - WebP: Uses native 0-100 scale directly
  - JPEG: Converts to FFmpeg's 2-31 scale (inverted)
  - PNG: Ignored (lossless format)

- **Auto-extension correction**: Output file extension is automatically corrected to match the specified `image_format`

- **Animated WebP creation**: New `create_animated_webp` operation for converting video segments to looping animated WebP files:
  - Better compression and color support than GIF
  - Configurable FPS (default 20 for smooth playback)
  - Quality control (0-100)
  - Loop count configuration (0 = infinite)
  - New `preview_webp` profile for quick animated previews

### Changed

- Default thumbnail format changed from JPEG to WebP for better compression and quality
- Default thumbnail quality set to 75
- Renamed `size` parameter to `image_size` for consistency with other `image_*` parameters
- Changed `image_size` default from `"1280x720"` to `None` (uses original video dimensions)
- Updated `thumbnail` profile to use original dimensions by default

### Fixed

- Fixed `AttributeError` in job queue when `_generate_output_path` was called before `self.parameters` was assigned
- Fixed job queue generating incorrect file extensions for thumbnail operations (now respects `image_format` parameter)
- Fixed crop filter using top-left origin instead of center for cover mode
- Standardized FFmpeg filter variable naming to use `iw`/`ih` consistently
- Added whitespace stripping and case normalization for string parameters (`image_fit`, `image_format`, `audio_format`, `size`) to prevent invalid FFmpeg filter syntax

## [1.0.0] - Initial Release

### Added

- Video transcoding with configurable codec, preset, and CRF
- Video compression with target size or scale options
- Watermark overlay with position and opacity controls
- Thumbnail generation from video frames
- Audio extraction to MP3, AAC, WAV, or FLAC
- GIF creation from video segments
- Video concatenation
- Video trimming with start/end time or duration
- Batch processing with job queue and worker pool
- REST API with FastAPI
- Predefined processing profiles
- Workflow support for multi-step processing
- Docker support for containerized deployment

