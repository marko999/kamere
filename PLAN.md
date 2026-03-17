# Kamere - Border Crossing Wait Time Estimator

## Vision
Servis koji estimira vreme čekanja na graničnim prelazima Srbije (i Hrvatske) analizom javno dostupnih kamera putem computer vision-a. Pored čekanja, izvlači i sve dodatne informacije vidljive na kamerama — tipove vozila, vremenske uslove, broj aktivnih traka/kabina.

## Phases

### Phase 1: ML Pipeline + Web MVP (current)
- Frame grabber za MUP HLS streamove i HAK JPEG kamere
- YOLO vehicle detection + counting
- Kalibracija modela (uporedi sa MUP zvaničnim vremenima)
- Jednostavna web stranica: uneseš prelaz → dobiješ estimaciju
- Deploy na VPS
- Testiranje sa poznanicima koji putuju

### Phase 2: Telegram Bot
- Bot koji čita iz iste baze
- Free tier (5 upita/dan) + Premium (Stripe, 3-4€/mesec)
- Push notifikacije za premium korisnike

### Phase 3: Viber Bot
- Ista logika, šira publika u regionu

### Phase 4: SMS
- Premium SMS broj preko Infobip/operatera
- "GRANICA BATROVCI" → 50 din, instant odgovor
- Zahteva ugovor sa operaterima

### Phase 5: B2B API
- REST API za logističke firme, taxi službe, turističke agencije
- JSON, webhookovi, SLA

---

## Week 1 Plan: Frame Grabber + YOLO Pipeline

### Tasks:
1. **Frame grabber service**
   - MUP: HLS stream → ffmpeg → frame extraction (every 30s)
   - HAK: HTTP GET cam.asp?id=XX → JPEG (every 30s)
   - Save frames to disk with timestamp

2. **YOLO vehicle detection + scene analysis**
   - YOLOv8 (ultralytics) for object detection
   - Vehicle counting by zones (queue area)
   - Classify: car vs truck vs bus vs motorcycle
   - Detect people (potential customs officers near booths)
   - Count active/open lanes vs closed lanes

3. **Scene intelligence (extract everything useful from frames)**
   - **Vehicle breakdown:** cars, trucks, buses, motorcycles — buses = slower processing
   - **Weather detection:** rain/snow/fog/clear — from image brightness, blur, visible precipitation
     (can use simple CV heuristics or a small classifier)
   - **Active lanes/booths:** how many control points are staffed vs empty
   - **Queue length:** estimate in meters based on camera calibration
   - **Congestion trend:** comparing last N readings — growing, stable, shrinking
   - **Anomalies:** accident, road block, unusually empty (possible closure)

4. **Data storage**
   - SQLite database
   - Table: readings (crossing_id, timestamp, car_count, truck_count, bus_count,
     person_count, active_lanes, weather, queue_length_m, estimated_wait_min, raw_json)
   - Table: crossings (id, name, country_border, mup_stream_url, hak_cam_id)
   - raw_json column stores full detection output for later analysis

5. **Calibration**
   - Scrape MUP official wait times for ground truth
   - Compare with camera-based estimates
   - Tune formula: vehicle_count × factor = minutes

6. **Per-crossing camera calibration**
   - One-time manual step per camera: mark zones (queue area, booth area, exit area)
   - Define pixel-to-meter ratio for queue length estimation
   - Mark lane positions for lane counting

### Week 2: Web MVP
- FastAPI backend, single endpoint
- Single HTML page, vanilla JS
- Deploy to VPS

---

## Tech Stack
- Python 3.11+
- ffmpeg (frame extraction from HLS)
- ultralytics (YOLOv8)
- FastAPI (web backend)
- SQLite (database)
- Vanilla HTML/JS (frontend)
- Hetzner/Fly.io (hosting, ~5€/month)
