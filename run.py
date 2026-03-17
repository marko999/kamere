#!/usr/bin/env python3
"""Entry point for the Kamere pipeline."""

import argparse
import logging

from src.config import CAMERAS, get_cameras_for_crossing
from src.pipeline import run_loop, run_once
from src.database import init_db, DB_PATH


def main():
    parser = argparse.ArgumentParser(description="Kamere — border crossing camera pipeline")
    parser.add_argument(
        "--crossing", "-c",
        help="Process only cameras for this crossing (e.g. Batrovci)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one cycle and exit (don't loop)",
    )
    parser.add_argument(
        "--interval", "-i", type=int, default=30,
        help="Seconds between cycles (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    cameras = CAMERAS
    if args.crossing:
        cameras = get_cameras_for_crossing(args.crossing)
        if not cameras:
            print(f"No cameras found for crossing: {args.crossing}")
            return

    if args.once:
        conn = init_db(DB_PATH)
        readings = run_once(conn, cameras)
        conn.close()
        print(f"\nProcessed {len(readings)} cameras:")
        for r in readings:
            print(f"  {r['camera_id']}: {r['car_count']} cars, "
                  f"{r['truck_count']} trucks, {r['bus_count']} buses — "
                  f"wait ~{r['estimated_wait_min']:.0f}min ({r['weather']})")
    else:
        run_loop(cameras, interval=args.interval)


if __name__ == "__main__":
    main()
