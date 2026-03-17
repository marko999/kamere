"""Main pipeline — grabs frames, runs detection, analyzes scenes, stores results."""

import logging
import time

from .config import CAMERAS, FRAME_INTERVAL, FRAMES_DIR, DB_PATH
from .database import init_db, save_reading
from .frame_grabber import grab_frame
from .detector import detect
from .analyzer import analyze_scene, build_reading

logger = logging.getLogger(__name__)


def process_camera(camera: dict, conn) -> dict | None:
    """Grab frame, detect, analyze, save — for one camera. Returns reading or None."""
    frame, path = grab_frame(camera, output_dir=FRAMES_DIR)
    if frame is None:
        return None

    detections = detect(frame)
    analysis = analyze_scene(frame, detections)
    reading = build_reading(camera, analysis)
    save_reading(conn, reading)

    logger.info(
        "%s: %d cars, %d trucks, %d buses | weather=%s | wait=%.0fmin | %s",
        camera["id"],
        reading.get("car_count", 0),
        reading.get("truck_count", 0),
        reading.get("bus_count", 0),
        reading.get("weather", "?"),
        reading.get("estimated_wait_min", 0),
        reading.get("anomalies", ""),
    )
    return reading


def run_once(conn, cameras: list[dict] | None = None) -> list[dict]:
    """Run one full cycle across all cameras. Returns list of successful readings."""
    if cameras is None:
        cameras = CAMERAS

    readings = []
    for camera in cameras:
        try:
            reading = process_camera(camera, conn)
            if reading:
                readings.append(reading)
        except Exception:
            logger.exception("Error processing camera %s", camera.get("id", "?"))

    logger.info("Cycle complete: %d/%d cameras processed", len(readings), len(cameras))
    return readings


def run_loop(cameras: list[dict] | None = None, interval: int | None = None):
    """Run the pipeline in a continuous loop."""
    if interval is None:
        interval = FRAME_INTERVAL

    conn = init_db(DB_PATH)
    logger.info("Pipeline started — %d cameras, %ds interval", len(cameras or CAMERAS), interval)

    try:
        while True:
            cycle_start = time.time()
            run_once(conn, cameras)
            elapsed = time.time() - cycle_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                logger.info("Sleeping %.0fs until next cycle", sleep_time)
                time.sleep(sleep_time)
    except KeyboardInterrupt:
        logger.info("Pipeline stopped by user")
    finally:
        conn.close()
