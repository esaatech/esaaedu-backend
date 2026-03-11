"""
HLS (HTTP Live Streaming) utility functions.

Provides consistent, reusable logic for converting video to HLS, uploading
HLS artifacts to GCS, and deleting them. Used by teacher upload flow and
can be used by async tasks or other callers.

Requires ffmpeg to be installed and on the server PATH.
"""
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from django.conf import settings

logger = logging.getLogger(__name__)

# Content types for HLS files (for correct playback and CDN behavior)
HLS_PLAYLIST_CONTENT_TYPE = "application/vnd.apple.mpegurl"
HLS_SEGMENT_CONTENT_TYPE = "video/MP2T"

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

    Uses ffmpeg with baseline profile and 4-second segments for broad
    compatibility. The output directory will contain playlist.m3u8 and
    segment000.ts, segment001.ts, etc.

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
        "-y",  # Overwrite output
        "-i",
        str(local_video_path),
        "-profile:v",
        "baseline",
        "-level",
        "3.0",
        "-start_number",
        "0",
        "-hls_time",
        "4",
        "-hls_list_size",
        "0",
        "-hls_segment_filename",
        segment_pattern,
        "-hls_flags",
        "split_by_time",
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

            # Upload playlist
            blob_name = prefix + "playlist.m3u8"
            blob = bucket.blob(blob_name)
            blob.content_type = HLS_PLAYLIST_CONTENT_TYPE
            blob.upload_from_filename(
                str(playlist_path), content_type=HLS_PLAYLIST_CONTENT_TYPE
            )
            blob.make_public()
            playlist_url = blob.public_url
            logger.info("Uploaded HLS playlist to %s", blob_name)

            # Upload segments (ffmpeg may name them playlist0.ts, segment000.ts, etc.)
            for seg_path in sorted(local_hls_dir.glob("*.ts")):
                blob_name_seg = prefix + seg_path.name
                blob_seg = bucket.blob(blob_name_seg)
                blob_seg.content_type = HLS_SEGMENT_CONTENT_TYPE
                blob_seg.upload_from_filename(
                    str(seg_path), content_type=HLS_SEGMENT_CONTENT_TYPE
                )
                blob_seg.make_public()

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
        with open(playlist_path, "rb") as f:
            saved_playlist = default_storage.save(prefix + "playlist.m3u8", f)
        playlist_url = default_storage.url(saved_playlist)
        if not playlist_url.startswith("http"):
            playlist_url = (
                f"https://storage.googleapis.com/{bucket_name}/{saved_playlist}"
            )

        for seg_path in sorted(local_hls_dir.glob("*.ts")):
            with open(seg_path, "rb") as f:
                default_storage.save(prefix + seg_path.name, f)

        logger.info("Uploaded HLS via default_storage to %s", prefix)
        return playlist_url
    except Exception as e:
        logger.exception("Failed to upload HLS via default_storage: %s", e)
        raise HLSUploadError(f"Failed to upload HLS: {e}") from e


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
