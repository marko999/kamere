# CLAUDE.md

## Project: Kamere — Border Crossing Wait Time Estimator

Estimates border crossing wait times in Serbia/Croatia by analyzing public camera feeds with computer vision. Extracts everything useful from frames: vehicle counts by type, weather, active lanes, queue length, anomalies.

## Key Files
- `PLAN.md` — Full project plan with phases and weekly breakdown
- `CAMERAS.md` — All camera sources, URLs, formats, and technical details

## Architecture
```
MUP HLS streams ──┐
                   ├──→ Frame grabber ──→ YOLOv8 ──→ Scene analyzer ──→ SQLite
HAK JPEG cameras ──┘    (every 30s)       │              │                 │
                                          │              │                 ↓
                                          │              │        FastAPI ──→ HTML page
                                          │              │        (later: Telegram/Viber/SMS)
                                          ↓              ↓
                                    Vehicle counts   Weather, lanes,
                                    (car/truck/bus)  queue length, anomalies
```

## Tech Stack
- Python 3.11+, ffmpeg, ultralytics (YOLOv8), FastAPI, SQLite
- No frameworks on frontend — vanilla HTML/JS

## Commands
- TBD as project develops

## Important Notes
- MUP streams are public HLS on port 4443, no auth needed
- HAK cameras are JPEG snapshots refreshed every ~30s
- ffmpeg must be installed (`brew install ffmpeg`)
- All camera URLs are documented in CAMERAS.md

## Scope: Extract EVERYTHING from frames
Not just vehicle counts. Also:
- Vehicle type breakdown (cars, trucks, buses, motorcycles)
- Weather conditions (rain/snow/fog from image analysis)
- Number of active lanes/customs booths
- Queue length in estimated meters
- Congestion trend (growing/stable/shrinking)
- Anomalies (unusually empty, possible accident/closure)
- Presence of buses (= significantly slower processing)
