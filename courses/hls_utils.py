"""
HLS (HTTP Live Streaming) utility functions.

Provides consistent, reusable logic for converting video to HLS, uploading
HLS artifacts to GCS, and deleting them. Used by teacher upload flow and
can be used by async tasks or other callers.

Requires ffmpeg to be installed and on the server PATH.
"""
import json
import logging
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import unquote, urlparse

from django.conf import settings

logger = logging.getLogger(__name__)

# Content types for HLS files (for correct playback and CDN behavior)
HLS_PLAYLIST_CONTENT_TYPE = "application/vnd.apple.mpegurl"
HLS_SEGMENT_CONTENT_TYPE = "video/MP2T"
HLS_ENCODE_PROFILE_VERSION = "seekable-hls-v1"
REQUIRED_VOD_TAGS = (
    "#EXT-X-PLAYLIST-TYPE:VOD",
    "#EXT-X-ENDLIST",
    "#EXT-X-INDEPENDENT-SEGMENTS",
)

# GCS client for listing/deleting by prefix and uploading with content-type
try:
    from google.cloud import storage

    GCS_CLIENT_AVAILABLE = True
except ImportError:
    GCS_CLIENT_AVAILABLE = False
    storage = None


class HLSConversionError(Exception):
    """Raised when ffmpeg HLS conversion fails."""

    pass


class HLSUploadError(Exception):
    """Raised when uploading HLS files to GCS fails."""

    pass


class HLSValidationError(Exception):
    """Raised when an HLS package does not satisfy the playback contract."""

    def __init__(self, message: str, report: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.report = report or {"valid": False, "errors": [message]}


def temp_suffix_for_video(filename: str = "", content_type: str = "") -> str:
    """
    Pick a temp-file suffix so ffmpeg probes the real container.

    Extensionless QuickTime uploads were saved as ``.mp4``, which can produce
    HLS with timestamp holes that hang when the student scrubs the timeline.
    """
    ext = Path(filename or "").suffix
    if ext:
        return ext if ext.startswith(".") else f".{ext}"
    ct = (content_type or "").split(";")[0].strip().lower()
    if "quicktime" in ct or ct in ("video/mov", "video/x-quicktime"):
        return ".mov"
    if "webm" in ct:
        return ".webm"
    if "ogg" in ct:
        return ".ogv"
    if "avi" in ct:
        return ".avi"
    if "wmv" in ct or "ms-wmv" in ct:
        return ".wmv"
    return ".mp4"


def _get_gcs_client():
    """Return a configured google.cloud.storage Client, or None if not available."""
    if not GCS_CLIENT_AVAILABLE:
        return None
    if not getattr(settings, "GS_BUCKET_NAME", None):
        return None
    try:
        if getattr(settings, "GS_CREDENTIALS", None):
            creds = settings.GS_CREDENTIALS
            if isinstance(creds, str):
                client = storage.Client.from_service_account_json(
                    creds, project=getattr(settings, "GS_PROJECT_ID", None)
                )
            else:
                client = storage.Client(
                    credentials=creds, project=getattr(settings, "GS_PROJECT_ID", None)
                )
        else:
            client = storage.Client(project=getattr(settings, "GS_PROJECT_ID", None))
        return client
    except Exception as e:
        logger.warning("Could not create GCS client for HLS: %s", e)
        return None


def convert_to_hls(
    local_video_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Convert a local video file to HLS (playlist.m3u8 + segment*.ts).

    Uses ffmpeg with H.264 + AAC (MPEG-TS safe) and 4-second keyframe-aligned
    segments. Explicit audio encode keeps volume working in Chrome. Forced
    keyframes and ``independent_segments`` keep QuickTime/MOV (edit lists,
    variable frame rate) seekable; MP4 usually already has regular GOPs.

    Args:
        local_video_path: Path to the input video file (e.g. MP4).
        output_dir: Directory for HLS output. If None, a temporary
            directory is created (caller is responsible for cleanup).

    Returns:
        Path to the directory containing playlist.m3u8 and segment files.

    Raises:
        HLSConversionError: If ffmpeg is not found or conversion fails.
        FileNotFoundError: If local_video_path does not exist.
    """
    local_video_path = Path(local_video_path)
    if not local_video_path.exists():
        raise FileNotFoundError(f"Video file not found: {local_video_path}")

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="hls_"))
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    playlist_path = output_dir / "playlist.m3u8"
    segment_pattern = str(output_dir / "segment_%03d.ts")

    cmd = [
        "ffmpeg",
        "-y",
        "-fflags",
        "+genpts",
        "-analyzeduration",
        "20M",
        "-probesize",
        "20M",
        "-i",
        str(local_video_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-sn",
        "-dn",
        "-c:v",
        "libx264",
        "-profile:v",
        "baseline",
        "-level",
        "3.0",
        "-pix_fmt",
        "yuv420p",
        "-g",
        "96",
        "-keyint_min",
        "48",
        "-sc_threshold",
        "0",
        "-force_key_frames",
        "expr:gte(t,n_forced*4)",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-b:a",
        "128k",
        "-avoid_negative_ts",
        "make_zero",
        "-max_muxing_queue_size",
        "2048",
        "-start_number",
        "0",
        "-hls_time",
        "4",
        "-hls_list_size",
        "0",
        "-hls_playlist_type",
        "vod",
        "-hls_flags",
        "independent_segments",
        "-hls_segment_filename",
        segment_pattern,
        "-f",
        "hls",
        str(playlist_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour max for long videos
        )
    except FileNotFoundError:
        raise HLSConversionError(
            "ffmpeg not found. Install ffmpeg and ensure it is on the system PATH."
        )
    except subprocess.TimeoutExpired:
        raise HLSConversionError("HLS conversion timed out (1 hour limit).")

    if result.returncode != 0:
        stderr = result.stderr or "(no stderr)"
        logger.error("ffmpeg HLS conversion failed: %s", stderr[:500])
        raise HLSConversionError(
            f"ffmpeg failed with exit code {result.returncode}: {stderr[:300]}"
        )

    if not playlist_path.exists():
        raise HLSConversionError(
            "ffmpeg completed but playlist.m3u8 was not created."
        )

    logger.info("HLS conversion succeeded: %s", output_dir)
    return output_dir


def _run_media_command(cmd: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise HLSValidationError(f"{cmd[0]} is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise HLSValidationError(f"{cmd[0]} validation timed out.") from exc


def _probe_duration(path: Union[str, Path]) -> float:
    result = _run_media_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    if result.returncode != 0:
        raise HLSValidationError(
            f"ffprobe failed for {Path(path).name}: {(result.stderr or '')[:300]}"
        )
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HLSValidationError(f"Could not read duration for {Path(path).name}.") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise HLSValidationError(f"Invalid duration for {Path(path).name}: {duration}")
    return duration


def _playlist_segment_paths(playlist_path: Path) -> list[Path]:
    lines = playlist_path.read_text(encoding="utf-8").splitlines()
    paths = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        parsed = urlparse(value)
        if parsed.scheme or parsed.netloc:
            raise HLSValidationError("Generated playlists must use relative segment URLs.")
        segment_path = (playlist_path.parent / unquote(parsed.path)).resolve()
        if playlist_path.parent.resolve() not in segment_path.parents:
            raise HLSValidationError(f"Segment escapes HLS directory: {value}")
        paths.append(segment_path)
    if not paths:
        raise HLSValidationError("Playlist contains no media segments.")
    return paths


def validate_hls_package(
    local_hls_dir: Union[str, Path],
    *,
    source_path: Optional[Union[str, Path]] = None,
) -> dict[str, Any]:
    """
    Enforce the canonical VOD seekability contract before publication.

    Every segment is opened independently by ffprobe. Beginning, middle, and
    near-end positions are then decoded through the playlist with ffmpeg.
    """
    hls_dir = Path(local_hls_dir)
    playlist_path = hls_dir / "playlist.m3u8"
    report: dict[str, Any] = {
        "valid": False,
        "profile_version": HLS_ENCODE_PROFILE_VERSION,
        "errors": [],
        "segment_count": 0,
        "segment_probe_failures": [],
        "representative_decode_failures": [],
    }
    try:
        if not playlist_path.exists():
            raise HLSValidationError("playlist.m3u8 was not generated.")
        manifest = playlist_path.read_text(encoding="utf-8")
        missing_tags = [tag for tag in REQUIRED_VOD_TAGS if tag not in manifest]
        if missing_tags:
            raise HLSValidationError(
                f"Playlist is missing required tags: {', '.join(missing_tags)}"
            )

        segments = _playlist_segment_paths(playlist_path)
        report["segment_count"] = len(segments)
        for segment in segments:
            if not segment.is_file():
                report["segment_probe_failures"].append(
                    {"segment": segment.name, "error": "missing"}
                )
                continue
            result = _run_media_command(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=codec_name,width,height",
                    "-of",
                    "json",
                    str(segment),
                ]
            )
            if result.returncode != 0:
                report["segment_probe_failures"].append(
                    {
                        "segment": segment.name,
                        "error": (result.stderr or "ffprobe failed")[:500],
                    }
                )
        if report["segment_probe_failures"]:
            raise HLSValidationError(
                f"{len(report['segment_probe_failures'])} segment(s) failed isolated probing."
            )

        duration = _probe_duration(playlist_path)
        report["duration_seconds"] = duration
        if source_path:
            source_duration = _probe_duration(source_path)
            report["source_duration_seconds"] = source_duration
            tolerance = max(2.0, source_duration * 0.03)
            if abs(duration - source_duration) > tolerance:
                raise HLSValidationError(
                    "HLS duration differs from source beyond tolerance."
                )

        sample_times = sorted(
            {
                0.0,
                max(0.0, duration * 0.5),
                max(0.0, duration - min(2.0, duration * 0.1)),
            }
        )
        for sample_time in sample_times:
            result = _run_media_command(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-ss",
                    f"{sample_time:.3f}",
                    "-i",
                    str(playlist_path),
                    "-t",
                    "1",
                    "-map",
                    "0:v:0",
                    "-f",
                    "null",
                    "-",
                ]
            )
            if result.returncode != 0:
                report["representative_decode_failures"].append(
                    {
                        "time_seconds": sample_time,
                        "error": (result.stderr or "ffmpeg decode failed")[:500],
                    }
                )
        if report["representative_decode_failures"]:
            raise HLSValidationError("Representative HLS decode checks failed.")

        report["valid"] = True
        return report
    except HLSValidationError as exc:
        report["errors"].append(str(exc))
        exc.report = report
        raise


def upload_hls_to_gcs(
    local_hls_dir: Union[str, Path],
    gcs_prefix: str,
) -> str:
    """
    Upload HLS playlist and segments from a local directory to GCS.

    Uploads playlist.m3u8 and all segment*.ts files with the correct
    content-types for streaming. Uses the project's default GCS bucket.

    Args:
        local_hls_dir: Path to the directory containing playlist.m3u8
            and segment files.
        gcs_prefix: GCS object name prefix (e.g. "hls/audio-video/{id}/").
            Must end with a slash so object names are prefix + filename.

    Returns:
        The public URL of the playlist file (e.g. for use as video_url).

    Raises:
        HLSUploadError: If GCS is not configured or upload fails.
    """
    local_hls_dir = Path(local_hls_dir)
    if not local_hls_dir.is_dir():
        raise HLSUploadError(f"Not a directory: {local_hls_dir}")

    playlist_path = local_hls_dir / "playlist.m3u8"
    if not playlist_path.exists():
        raise HLSUploadError(f"Playlist not found: {playlist_path}")

    bucket_name = getattr(settings, "GS_BUCKET_NAME", None)
    if not bucket_name:
        raise HLSUploadError("GCS is not configured (GS_BUCKET_NAME not set).")

    prefix = gcs_prefix.rstrip("/") + "/"

    # Prefer GCS client so we can set content-type
    client = _get_gcs_client()
    if client:
        try:
            bucket = client.bucket(bucket_name)

            # Publish every immutable segment before the playlist. A client can
            # never observe a manifest that references an object not uploaded yet.
            for seg_path in sorted(local_hls_dir.glob("*.ts")):
                blob_name_seg = prefix + seg_path.name
                blob_seg = bucket.blob(blob_name_seg)
                blob_seg.content_type = HLS_SEGMENT_CONTENT_TYPE
                blob_seg.upload_from_filename(
                    str(seg_path), content_type=HLS_SEGMENT_CONTENT_TYPE
                )
                blob_seg.make_public()

            blob_name = prefix + "playlist.m3u8"
            blob = bucket.blob(blob_name)
            blob.content_type = HLS_PLAYLIST_CONTENT_TYPE
            blob.upload_from_filename(
                str(playlist_path), content_type=HLS_PLAYLIST_CONTENT_TYPE
            )
            blob.make_public()
            playlist_url = blob.public_url
            logger.info("Published HLS playlist last to %s", blob_name)

            logger.info(
                "Uploaded HLS segments from %s to gs://%s/%s",
                local_hls_dir,
                bucket_name,
                prefix,
            )
            return playlist_url
        except Exception as e:
            logger.exception("Failed to upload HLS to GCS: %s", e)
            raise HLSUploadError(f"Failed to upload HLS to GCS: {e}") from e

    # Fallback: django default_storage (content-type may be generic)
    from django.core.files.storage import default_storage

    try:
        for seg_path in sorted(local_hls_dir.glob("*.ts")):
            with open(seg_path, "rb") as f:
                default_storage.save(prefix + seg_path.name, f)

        with open(playlist_path, "rb") as f:
            saved_playlist = default_storage.save(prefix + "playlist.m3u8", f)
        playlist_url = default_storage.url(saved_playlist)
        if not playlist_url.startswith("http"):
            playlist_url = (
                f"https://storage.googleapis.com/{bucket_name}/{saved_playlist}"
            )

        logger.info("Uploaded HLS via default_storage to %s", prefix)
        return playlist_url
    except Exception as e:
        logger.exception("Failed to upload HLS via default_storage: %s", e)
        raise HLSUploadError(f"Failed to upload HLS: {e}") from e


def archive_gcs_source(source_object_name: str, archive_object_name: str) -> str:
    """Copy a pending source to durable cold storage without deleting it."""
    client = _get_gcs_client()
    bucket_name = getattr(settings, "GS_BUCKET_NAME", None)
    if not client or not bucket_name:
        raise HLSUploadError("GCS client is required to archive video sources.")
    try:
        bucket = client.bucket(bucket_name)
        source = bucket.blob(source_object_name)
        if not source.exists(client=client):
            raise HLSUploadError(f"Source object does not exist: {source_object_name}")
        archived = bucket.copy_blob(source, bucket, archive_object_name)
        try:
            archived.update_storage_class("COLDLINE")
        except Exception as exc:
            logger.warning("Could not set COLDLINE on %s: %s", archive_object_name, exc)
        return archive_object_name
    except HLSUploadError:
        raise
    except Exception as exc:
        raise HLSUploadError(f"Failed to archive video source: {exc}") from exc


def download_hls_from_gcs(gcs_prefix: str, output_dir: Union[str, Path]) -> Path:
    """Download a playlist and its referenced segments for validation/repair."""
    client = _get_gcs_client()
    bucket_name = getattr(settings, "GS_BUCKET_NAME", None)
    if not client or not bucket_name:
        raise HLSUploadError("GCS client is required to download legacy HLS.")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = gcs_prefix.rstrip("/") + "/"
    bucket = client.bucket(bucket_name)
    playlist_blob = bucket.blob(prefix + "playlist.m3u8")
    if not playlist_blob.exists(client=client):
        raise HLSUploadError(f"Legacy playlist missing: {prefix}playlist.m3u8")
    playlist_path = output / "playlist.m3u8"
    playlist_blob.download_to_filename(str(playlist_path))
    for segment_path in _playlist_segment_paths(playlist_path):
        segment_path.parent.mkdir(parents=True, exist_ok=True)
        relative = segment_path.relative_to(output.resolve()).as_posix()
        blob = bucket.blob(prefix + relative)
        if not blob.exists(client=client):
            raise HLSUploadError(f"Legacy segment missing: {prefix}{relative}")
        blob.download_to_filename(str(segment_path))
    return output


def reconstruct_hls_source(
    local_hls_dir: Union[str, Path],
    output_path: Union[str, Path],
) -> Path:
    """Decode a legacy playlist sequentially into a normalized surrogate MP4."""
    playlist = Path(local_hls_dir) / "playlist.m3u8"
    output = Path(output_path)
    result = _run_media_command(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(playlist),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            str(output),
        ],
        timeout=3600,
    )
    if result.returncode != 0 or not output.exists():
        raise HLSConversionError(
            f"Could not reconstruct legacy HLS: {(result.stderr or '')[:500]}"
        )
    return output


def delete_hls_from_gcs(gcs_prefix: str) -> None:
    """
    Delete all HLS objects under a GCS prefix (playlist + segments + folder placeholder).

    Used when an AudioVideoMaterial that points to HLS is deleted, so the
    entire folder is removed from GCS. Lists by prefix without trailing slash
    so any zero-byte "folder" object (e.g. "hls/audio-video/{id}") is also deleted.

    Args:
        gcs_prefix: GCS object name prefix (e.g. "hls/audio-video/{id}" or with trailing /).
            All objects whose names start with this prefix will be deleted.
    """
    bucket_name = getattr(settings, "GS_BUCKET_NAME", None)
    if not bucket_name:
        logger.warning("Cannot delete HLS from GCS: GS_BUCKET_NAME not set.")
        return

    # Use prefix without trailing slash so we also catch folder placeholder objects
    # (e.g. "hls/audio-video/uuid" as well as "hls/audio-video/uuid/playlist.m3u8")
    prefix = (gcs_prefix or "").rstrip("/")
    prefix_with_slash = prefix + "/" if prefix else ""

    client = _get_gcs_client()
    if client:
        try:
            bucket = client.bucket(bucket_name)
            blobs = list(bucket.list_blobs(prefix=prefix))
            for blob in blobs:
                blob.delete()
                logger.debug("Deleted GCS object: %s", blob.name)
            if blobs:
                logger.info("Deleted %d HLS object(s) under prefix %s", len(blobs), prefix)
        except Exception as e:
            logger.error("Failed to delete HLS objects from GCS (prefix=%s): %s", prefix, e)
        return

    # Fallback: we cannot list by prefix with default_storage only; try deleting
    # known names if the prefix follows our convention (e.g. hls/audio-video/{id}/)
    from django.core.files.storage import default_storage

    playlist_path = prefix_with_slash + "playlist.m3u8"
    try:
        if default_storage.exists(playlist_path):
            default_storage.delete(playlist_path)
            logger.info("Deleted HLS playlist: %s", playlist_path)
    except Exception as e:
        logger.error("Failed to delete HLS playlist %s: %s", playlist_path, e)

    # Segments: default_storage has no listdir(prefix), so we cannot delete
    # segment*.ts without the GCS client. Log so operators know to use GCS client.
    if not GCS_CLIENT_AVAILABLE:
        logger.warning(
            "google-cloud-storage not available; only playlist deleted. "
            "Orphaned segment*.ts may remain under %s",
            prefix,
        )


if __name__ == "__main__":
    """
    Run this file with a small video file to test HLS conversion and GCS upload.

    Usage:
        python manage.py shell -c "from courses.hls_utils import *; run_test('path/to/video.mp4')"
    or (after Django setup):
        python -c "
        import os, sys
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
        import django; django.setup()
        from courses.hls_utils import run_test
        run_test(sys.argv[1] if len(sys.argv) > 1 else 'path/to/video.mp4')
        "
    """
    import shutil
    import sys
    import uuid

    # Ensure Django is configured when run as script
    if "django" not in sys.modules or not getattr(settings, "GS_BUCKET_NAME", None):
        import os
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
        import django
        django.setup()

    def run_test(video_path: str, cleanup_after: bool = False) -> None:
        """Convert a local video to HLS and upload to GCS. Prints playlist URL."""
        video_path = Path(video_path)
        if not video_path.exists():
            print(f"Error: File not found: {video_path}")
            sys.exit(1)

        test_prefix = f"hls/test-run/{uuid.uuid4().hex[:12]}"
        local_hls_dir = None

        try:
            print(f"Converting {video_path} to HLS...")
            local_hls_dir = convert_to_hls(video_path)
            print(f"HLS files written to: {local_hls_dir}")

            print(f"Uploading to GCS prefix: {test_prefix}")
            playlist_url = upload_hls_to_gcs(local_hls_dir, test_prefix)
            print(f"\nPlaylist URL (check in GCP Console):\n  {playlist_url}\n")

            if cleanup_after:
                print(f"Cleaning up GCS prefix: {test_prefix}")
                delete_hls_from_gcs(test_prefix)
                print("Done (GCS test objects deleted).")
            else:
                print("Leave objects in GCS (use cleanup_after=True to delete).")
        except (HLSConversionError, HLSUploadError, FileNotFoundError) as e:
            print(f"Error: {e}")
            sys.exit(1)
        finally:
            if local_hls_dir and local_hls_dir.exists():
                shutil.rmtree(local_hls_dir, ignore_errors=True)
                print("Local HLS directory removed.")

    # Allow: python courses/hls_utils.py video.mp4 [--cleanup]
    if len(sys.argv) < 2:
        print("Usage: python -m courses.hls_utils <video_file> [--cleanup]")
        print("  video_file  Path to a small MP4 (or other ffmpeg-supported video)")
        print("  --cleanup   Delete the test objects from GCS after upload")
        sys.exit(1)

    cleanup = "--cleanup" in sys.argv
    video_arg = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not video_arg:
        print("Error: Provide a video file path.")
        sys.exit(1)

    run_test(video_arg, cleanup_after=cleanup)
