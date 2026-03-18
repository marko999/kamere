# Kamere - Border Crossing Wait Time Estimator

## Vision
Servis koji estimira vreme čekanja na graničnim prelazima Srbije (i Hrvatske) analizom javno dostupnih kamera putem computer vision-a. Pored čekanja, izvlači i sve dodatne informacije vidljive na kamerama — tipove vozila, vremenske uslove, broj aktivnih kontrolnih punktova.

## Status — šta je urađeno

### ✅ Phase 1: ML Pipeline + Web MVP — DONE
- Frame grabber (41 kamera — 32 MUP HLS + 9 HAK JPEG)
- YOLOv8 vehicle detection (car/truck/bus/motorcycle/person)
- Vehicle tracking između frejmova (Hungarian algorithm)
- Wait time iz merenja kretanja reda (queue_length / speed)
- Scene extraction (weather, road condition, headlights, booths, density)
- Vehicle analysis (size, spacing/formation)
- QueueHistory smoothing (rolling window 10 ciklusa)
- SQLite storage (40k+ readings za 18h)
- FastAPI + dark theme web frontend
- Deploy na Azure VM (B2s, Ubuntu 24.04)
- Pipeline radi 24/7 na svim kamerama

---

## Roadmap — šta sledi

### Phase 1.5: Intelligence Layer (CURRENT)
Poboljšanja na osnovu podataka koje već skupljamo.

#### 1. Queue growth rate + trend
- Računaj `vehicles_entered - vehicles_exited` po ciklusu = net queue change
- Uporedi poslednjih N readings: čekanje raste / stabilan / opada
- Prikaži trend na kartici: ↑ Raste (+3 min/h) / → Stabilan / ↓ Opada
- Osnova za GPS predikciju

#### 2. Grupisanje prelaza po zemlji
- Frontend: grupiši kartice po destinaciji (Mađarska, Hrvatska, BiH, Rumunija, Bugarska, C.Gora, S.Makedonija, Slovenija)
- Tabs ili sekcije sa zastavama/imenima zemalja
- Korisnik obično zna gde ide, ne koji tačno prelaz

#### 3. Procena po smeru (ulaz vs izlaz)
- Prikaži odvojeno: "Ulaz u Srbiju: 5 min" / "Izlaz iz Srbije: 12 min"
- Korisnik ide u jednom smeru, worst-case nije uvek relevantan

#### 4. Simulator — GPS predikcija čekanja
- Korisnik unese svoju lokaciju (ili dozvoli GPS) + brzinu kretanja
- Sistem računa ETA do svakog prelaza
- Predicted wait = current_wait + (growth_rate × ETA)
- "Kad stigneš za 45min na Batrovci, čekaćeš ~25min"
- Preporuči optimalan prelaz za korisnikovu destinaciju
- Frontend: interaktivna forma sa mapom ili input poljem

#### 5. Vršni sati / patterns
- Kad se nakupi 7+ dana podataka
- Prikaži "obično najgušće 10-14h" za svaki prelaz
- Heatmap sat × dan u nedelji
- Pomogne korisniku da planira kad da putuje

### Phase 2: Telegram Bot
- Bot koji čita iz iste baze
- Pošalji lokaciju → bot preporuči prelaz + predicted wait
- Free tier (5 upita/dan) + Premium (Stripe, 3-4€/mesec)
- Push notifikacije za premium: "Batrovci pao na 5min, kreni sad"
- Alerting: notifikacija kad čekanje preskoči threshold

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

## Tech Stack
- Python 3.11+
- ffmpeg (frame extraction from HLS)
- ultralytics (YOLOv8)
- FastAPI (web backend)
- SQLite (database)
- Vanilla HTML/JS (frontend)
- Azure VM B2s (hosting)
- scipy (Hungarian algorithm for tracking)
- OpenCV (scene analysis, weather, road condition)
