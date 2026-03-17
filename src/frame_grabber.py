"""
Frame grabber for border crossing cameras.

Supports two source types:
- MUP: HLS streams via ffmpeg subprocess
- HAK: JPEG snapshots via HTTP GET
"""

import logging
import os
import subprocess
import tempfile
import time
from urllib.parse import urlparse

import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning for HAK cameras with flaky certs
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _grab_mup(url: str, output_path: str) -> np.ndarray | None:
    """Grab a single frame from a MUP HLS stream using ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-timeout", "10000000",
                "-i", url,
                "-vframes", "1",
                "-y",
                tmp_path,
            ],
            capture_output=True,
            timeout=15,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            logger.error("ffmpeg failed for %s (exit %d): %s", url, result.returncode, stderr[:500])
            return None

        frame = cv2.imread(tmp_path)
        if frame is None:
            logger.error("cv2.imread returned None for ffmpeg output from %s", url)
            return None

        # Copy the frame file to the final output path
        os.replace(tmp_path, output_path)
        return frame

    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out (15s) for %s", url)
        return None
    except Exception:
        logger.exception("Unexpected error grabbing MUP frame from %s", url)
        return None
    finally:
        # Clean up temp file if it still exists (wasn't moved)
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _grab_hak(url: str, output_path: str) -> np.ndarray | None:
    """Grab a single frame from a HAK JPEG camera via HTTP GET."""
    # Add cache-busting timestamp
    separator = "&" if "?" in url else "?"
    full_url = f"{url}{separator}t={int(time.time() * 1000)}"

    try:
        resp = requests.get(full_url, timeout=10, verify=False)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("HTTP request failed for %s", url)
        return None

    # Decode JPEG bytes to numpy array
    img_array = np.frombuffer(resp.content, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if frame is None:
        logger.error("cv2.imdecode returned None for %s (%d bytes)", url, len(resp.content))
        return None

    # Save to disk
    cv2.imwrite(output_path, frame)
    return frame


def grab_frame(
    camera: dict, output_dir: str = "frames"
) -> tuple[np.ndarray | None, str | None]:
    """
    Grab a single frame from a camera.

    camera dict has keys: id, source_type ("mup" or "hak"), url

    Returns (frame_as_numpy_array, saved_file_path) or (None, None) on failure.
    """
    os.makedirs(output_dir, exist_ok=True)

    camera_id = camera["id"]
    source_type = camera["source_type"]
    url = camera["url"]
    timestamp = int(time.time())
    filename = f"{camera_id}_{timestamp}.jpg"
    output_path = os.path.join(output_dir, filename)

    logger.info("Grabbing frame from %s camera %s", source_type.upper(), camera_id)

    if source_type == "mup":
        frame = _grab_mup(url, output_path)
    elif source_type == "hak":
        frame = _grab_hak(url, output_path)
    else:
        logger.error("Unknown source_type '%s' for camera %s", source_type, camera_id)
        return None, None

    if frame is None:
        return None, None

    logger.info("Saved frame: %s (%dx%d)", output_path, frame.shape[1], frame.shape[0])
    return frame, output_path


def grab_all_frames(
    cameras: list[dict], output_dir: str = "frames"
) -> list[tuple[dict, np.ndarray, str]]:
    """
    Grab frames from all cameras sequentially.

    Returns list of (camera, frame, path) for successful grabs.
    Failed grabs are logged and skipped.
    """
    results = []

    for camera in cameras:
        try:
            frame, path = grab_frame(camera, output_dir)
            if frame is not None and path is not None:
                results.append((camera, frame, path))
        except Exception:
            logger.exception("Unexpected error processing camera %s", camera.get("id", "unknown"))

    logger.info("Grabbed %d/%d frames successfully", len(results), len(cameras))
    return results
