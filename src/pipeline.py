"""Main pipeline — grabs frames, detects vehicles, tracks movement, estimates wait times."""

import logging
import time

from .config import CAMERAS, FRAME_INTERVAL, FRAMES_DIR, DB_PATH
from .database import init_db, save_reading
from .frame_grabber import grab_frame
from .detector import detect
from .analyzer import analyze_scene, build_reading
from .tracker import VehicleTracker
from .queue_analyzer import analyze_queue, QueueHistory

logger = logging.getLogger(__name__)

# Module-level state (persists across cycles)
_tracker = VehicleTracker()
_history = QueueHistory(window=10)


def process_camera(camera: dict, conn) -> dict | None:
    """Grab frame, detect, track, analyze, save — for one camera."""
    frame, path = grab_frame(camera, output_dir=FRAMES_DIR)
    if frame is None:
        return None

    # Detect vehicles
    detections = detect(frame)

    # Track vehicles between frames
    tracker_result = _tracker.update(camera["id"], detections.get("detections", []))

    # Analyze queue dynamics from tracking
    queue_raw = analyze_queue(tracker_result, detections, frame_interval=FRAME_INTERVAL)
    queue_data = _history.add(camera["id"], queue_raw)

    # Scene analysis (weather, anomalies, counts + tracking-based wait time)
    analysis = analyze_scene(frame, detections, queue_data)
    reading = build_reading(camera, analysis)
    save_reading(conn, reading)

    # Log with tracking info
    wait = reading.get("estimated_wait_min")
    wait_str = f"{wait:.1f}min" if wait is not None else "measuring..."
    moving = queue_data.get("queue_moving")
    moving_str = "moving" if moving else ("stopped" if moving is False else "?")
    tracked = queue_data.get("vehicles_tracked", 0)

    logger.info(
        "%s: %d cars, %d trucks, %d buses | %s | wait=%s | queue=%s | tracked=%d | %s",
        camera["id"],
        reading.get("car_count", 0),
        reading.get("truck_count", 0),
        reading.get("bus_count", 0),
        reading.get("weather", "?"),
        wait_str,
        moving_str,
        tracked,
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

    cycle = 0
    try:
        while True:
            cycle += 1
            cycle_start = time.time()
            logger.info("=== Cycle %d ===", cycle)
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
