# Kamere — Go-to-Market strategija

## 1. Tržište i target grupe

### Dijaspore koje voze kolima kroz Balkan

| Grupa | Populacija | Ruta | Sezona | Messaging app |
|-------|-----------|------|--------|---------------|
| **Srbi u DACH** | ~800k (DE 400-800k, AT 300k, CH 150k) | DACH → SLO/HRV → SRB | Jun-Sep, Božić, Uskrs | **Viber** #1, WhatsApp #2 |
| **Turci u Nemačkoj** | 3+ miliona | DE → AT → HUN/SRB → BG → TR | Jun-Sep (2.5M ljudi, 604k vozila samo kroz Kapikule za 11 nedelja) | **WhatsApp** (88% TR), Telegram |
| **Kosovski Albanci u CH/DE** | ~800k (DE 542k, CH 350k) | CH/DE → AT → SRB/MNE → KOS | Jun-Sep ("Schatzis" sezona) | **WhatsApp** #1, Viber |
| **Rumuni u IT/ES** | 1M+ | IT → SLO → HRV → SRB → RO ili IT → AT → HUN → RO | Jun-Sep, Crăciun | **WhatsApp** #1 |
| **Bugari u EU** | 500k+ | DE/AT → HUN → SRB → BG ili direktno | Leto, praznici | **Viber** #1 (BG) |
| **S.Makedonci u CH/DE** | 200k+ | CH/DE → AT → SRB → MKD | Leto | **Viber**, WhatsApp |
| **Grci (povratak sa severa)** | turisti | GR → BG/MKD → SRB | Leto | **Viber** #1 (GR) |

### Ključni insight — messaging platforme po grupi:
- **Viber**: Srbija, Bugarska, Grčka, S.Makedonija — Balkanski core
- **WhatsApp**: Turska, Kosovo, Rumunija, Albanija — globalni default
- **Telegram**: Turska (jak #2), Ukrajina, tech-savvy korisnici svuda

### Koliko vozila prelazi granicu?
- Srbija: ~5-6M prelazaka putničkih vozila godišnje (svi prelazi)
- Top prelazi: Batrovci (12.1%), Horgoš (9.6%), Preševo (8.8%)
- Kapikule (BG-TR): 604k vozila samo za 11 letnjih nedelja
- Ukupan adresabilan tržišni potencijal: **10-15M graničnih prelazaka godišnje** na rutama koje pokrivamo ili možemo pokriti

---

## 2. Konkurencija

| Proizvod | Pristup | Slabost | Korisnici |
|----------|---------|---------|-----------|
| **BorderWatcher** | User-reported + zvanični podaci | Zavisi od korisnika da prijave, netačno kad nema reporta | 410k downloads, ~$16/ned prihod |
| **BorderAlarm** | Crowdsource | Isti problem — nema korisnika = nema podataka | Nepoznat |
| **Nakordoni** | Scraping + AI forecast | Dinamički sadržaj, teško scraping, ne pokriva sve | Nepoznat |
| **AllTrafficCams** | Linkovi ka kamerama | Samo slike, bez analize, korisnik sam gleda | Nepoznat |
| **AMSS / HAK / Putevi Srbije** | Zvanični podaci | Spor update, Cloudflare, nepouzdano | N/A |

### Naša prednost:
1. **Computer vision** — ne zavisimo od korisnika da prijave čekanje
2. **Real-time tracking** — merimo stvarno kretanje vozila, ne guessing
3. **Predikcija** — "koliko ĆEŠ čekati kad stigneš" (niko ovo nema)
4. **Automatski 24/7** — ne zavisi od crowdsource-a
5. **Proširivo** — svaka javna kamera na svetu je potencijalni izvor

---

## 3. Validacija — pre skaliranja

### Faza A: Validacija sa srpskom dijasporom (1-2 meseca)
**Cilj:** Dokazati da ljudi koriste servis i da je tačan.

1. **Landing page** na domenu (npr. granica.rs ili kamere.app)
2. **Viber bot** (Srbi koriste Viber više od svega)
   - Pošalji "Batrovci" → dobiješ čekanje + predikciju
   - Pošalji lokaciju → preporuči prelaz
3. **Facebook grupe** — postavi u srpske dijaspora grupe:
   - "Srbi u Nemačkoj" (100k+ članova)
   - "Srbi u Austriji" (50k+)
   - "Srbi u Švajcarskoj" (30k+)
   - "Granični prelazi" FB grupa (30k+)
4. **Meri:**
   - Koliko upita dnevno?
   - Da li se vraćaju?
   - Da li dele sa drugima?
   - Feedback na tačnost

### Faza B: Validacija tačnosti (paralelno)
- Nađi 5-10 poznanika koji putuju preko granice
- Zamoli ih da uporede naš estimate sa stvarnim čekanjem
- Kalibriši model na osnovu feedback-a

### Success kriterijum za dalji razvoj:
- **100+ upita dnevno** posle 2 nedelje (bez plaćenog marketinga)
- **>70% tačnost** (razlika <5min od stvarnog čekanja)
- **Pozitivan word-of-mouth** (ljudi sami dele)

---

## 4. Ekspanzija — step by step

### Step 1: Srpske granice (CURRENT — done)
- ✅ 16 MUP prelaza (32 kamere)
- ✅ 5 HAK prelaza (9 kamera)
- ✅ Web + simulator

### Step 2: Viber + WhatsApp bot (Week 1-2)
- Viber bot za srpsku dijasporu
- WhatsApp bot za širu publiku
- Free tier: 10 upita/dan
- Podeliti u FB grupama

### Step 3: Bugarske granice (Week 3-4)
**Zašto:** Turska dijaspora prolazi BG, i bugarske kamere su javne.
- AllTrafficCams i TrafficVision imaju feed-ove za BG prelaze
- Kapitan Andreevo (BG-TR) — najprometniji kopneni prelaz u Evropi
- Kulata-Promachonas (BG-GR)
- Kalotina (BG-SRB) — direktna veza sa našim sistemom
- Dodaj 10-15 bugarskih kamera

### Step 4: Turska ruta end-to-end (Month 2)
**Killer feature:** Turčin u Minhenu unese lokaciju, sistem mu pokaže:
- Optimalan prelaz na svakoj granici (AT→HUN, HUN→SRB, SRB→BG, BG→TR)
- Ukupno predviđeno vreme za celu rutu
- "Kreni u 4 ujutru, stigneš za 18h sa 45min ukupnog čekanja"
- WhatsApp bot na turskom jeziku

### Step 5: Mađarske i hrvatske kamere (Month 2-3)
- Mađarske kamere (utorrent.hu, ÚTINFORM)
- Hrvatske kamere (HAK — već delimično imamo)
- Slovenačke kamere (promet.si — javne)

### Step 6: Monetizacija (Month 3+)
**Free tier:**
- 10 upita/dan
- Osnovno čekanje (trenutno stanje)

**Premium (3-5€/mes):**
- Neograničeni upiti
- Predikcija na osnovu lokacije
- Push notifikacije: "Batrovci pao na 5min, kreni sad!"
- Alerting: "Čekanje na Horgoš prešlo 60min"
- Ruta optimizacija (cela putanja)
- Bez reklama

**B2B API (po upitu):**
- Logističke firme (kamionski saobraćaj)
- Taxi službe (aerodromski transferi)
- Turističke agencije
- Navigation apps (integracija)

---

## 5. Messaging platforma prioritet

### Build order:
1. **Viber bot** — Srbija, Bugarska, Grčka, Makedonija (Viber dominantan)
2. **WhatsApp bot** — Turska, Kosovo, Rumunija, univerzalan
3. **Telegram bot** — tech-savvy korisnici, Turska secondary, Ukrajina
4. **SMS** — premium, fallback za sve

### Jezici po fazama:
1. **Srpski** (latinica) — faza A
2. **Engleski** — faza B (univerzalan fallback)
3. **Turski** — faza C (Kapikule ekspanzija)
4. **Bugarski** — faza C
5. **Rumunski, Albanski** — faza D

---

## 6. Tech roadmap za ekspanziju

### Šta treba dodati:
1. **Multi-country camera support** — generalizovati frame_grabber za različite izvore
2. **Multi-language bot** — i18n layer
3. **Route optimizer** — optimalna ruta sa više granica
4. **Push notification system** — Firebase/OneSignal
5. **Payment integration** — Stripe za premium
6. **Analytics dashboard** — koliko korisnika, upita, retention

### Infrastruktura:
- Trenutno: 1 Azure VM (B2s) za 41 kameru
- Sa 100+ kamera: upgrade na B4ms ili 2 VM-a
- Sa 1000+ korisnika: dodaj Redis cache za API responses
- Baza: SQLite → PostgreSQL kad premaši 1GB

---

## 7. Timeline

| Nedelja | Milestone |
|---------|-----------|
| 1 | Viber bot live, domen, landing page |
| 2 | Postavljanje u FB grupe, prva validacija |
| 3 | WhatsApp bot, bugarske kamere research |
| 4 | Bugarski prelazi dodati, tačnost validacija |
| 5-6 | Turska ruta end-to-end, WhatsApp na turskom |
| 7-8 | Premium tier, Stripe integracija |
| 9-12 | Mađarska/Slovenija kamere, route optimizer |

---

## 8. Rizici

| Rizik | Mitigation |
|-------|------------|
| Kamere prestanu da rade / promene URL | Monitoring + fallback na crowdsource |
| YOLO netačan noću | Headlight detection backup + historical patterns |
| Pravni (scraping kamera) | Kamere su javne, ne čuvamo lične podatke |
| Konkurencija kopira CV pristup | First-mover advantage + dataset moat (istorijski podaci) |
| EES sistem (biometrija) menja čekanja | Adaptiramo model — EES čini naš servis JOŠ korisnijim jer će čekanja biti duža i nepredvidljivija |
