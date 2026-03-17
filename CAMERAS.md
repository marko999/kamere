# Available Camera Sources

## 1. MUP Srbije (kamere.mup.gov.rs) — PRIMARY SOURCE

- **Format:** HLS live video (H.264, .m3u8 + .ts segments)
- **Resolution:** 704x576 (PAL)
- **Frame rate:** ~1 fps
- **Segment duration:** 5 seconds
- **Authentication:** None — publicly accessible
- **Cameras per crossing:** 2 (entrance + exit)
- **Total:** 16 crossings × 2 cameras = 32 streams

### Stream URLs:
| Crossing | Camera 1 (usually entrance) | Camera 2 (usually exit) |
|----------|---------------------------|------------------------|
| Đala | https://kamere.mup.gov.rs:4443/Djala/djala1.m3u8 | https://kamere.mup.gov.rs:4443/Djala/djala2.m3u8 |
| Kelebija | https://kamere.mup.gov.rs:4443/Kelebija/kelebija1.m3u8 | https://kamere.mup.gov.rs:4443/Kelebija/kelebija2.m3u8 |
| Horgoš | https://kamere.mup.gov.rs:4443/Horgos/horgos1.m3u8 | https://kamere.mup.gov.rs:4443/Horgos/horgos2.m3u8 |
| Jabuka | https://kamere.mup.gov.rs:4443/Jabuka/jabuka1.m3u8 | https://kamere.mup.gov.rs:4443/Jabuka/jabuka2.m3u8 |
| Gostun | https://kamere.mup.gov.rs:4443/Gostun/gostun1.m3u8 | https://kamere.mup.gov.rs:4443/Gostun/gostun2.m3u8 |
| Šiljani | https://kamere.mup.gov.rs:4443/Spiljani/spiljani1.m3u8 | https://kamere.mup.gov.rs:4443/Spiljani/spiljani2.m3u8 |
| Batrovci | https://kamere.mup.gov.rs:4443/Batrovci/batrovci1.m3u8 | https://kamere.mup.gov.rs:4443/Batrovci/batrovci2.m3u8 |
| Šid | https://kamere.mup.gov.rs:4443/Sid/sid1.m3u8 | https://kamere.mup.gov.rs:4443/Sid/sid2.m3u8 |
| Vatin | https://kamere.mup.gov.rs:4443/Vatin/vatin1.m3u8 | https://kamere.mup.gov.rs:4443/Vatin/vatin2.m3u8 |
| Kotroman | https://kamere.mup.gov.rs:4443/Kotroman/kotroman1.m3u8 | https://kamere.mup.gov.rs:4443/Kotroman/kotroman2.m3u8 |
| Mali Zvornik | https://kamere.mup.gov.rs:4443/MaliZvornik/malizvornik1.m3u8 | https://kamere.mup.gov.rs:4443/MaliZvornik/malizvornik2.m3u8 |
| Sremska Rača | https://kamere.mup.gov.rs:4443/SremskaRaca/sremskaraca1.m3u8 | https://kamere.mup.gov.rs:4443/SremskaRaca/sremskaraca2.m3u8 |
| Trbušnica | https://kamere.mup.gov.rs:4443/Trbusnica/trbusnica1.m3u8 | https://kamere.mup.gov.rs:4443/Trbusnica/trbusnica2.m3u8 |
| Vrška Čuka | https://kamere.mup.gov.rs:4443/VrskaCuka/vrskacuka1.m3u8 | https://kamere.mup.gov.rs:4443/VrskaCuka/vrskacuka2.m3u8 |
| Gradina | https://kamere.mup.gov.rs:4443/Gradina/gradina1.m3u8 | https://kamere.mup.gov.rs:4443/Gradina/gradina2.m3u8 |
| Preševo | https://kamere.mup.gov.rs:4443/Presevo/presevo1.m3u8 | https://kamere.mup.gov.rs:4443/Presevo/presevo2.m3u8 |

### Notes:
- cam1 = "Ulaz" (entrance into Serbia), cam2 = "Izlaz" (exit from Serbia) — verify per crossing
- Streams are H.264 High profile, yuvj420p, SAR 16:11, DAR 16:9
- ffmpeg can extract frames: `ffmpeg -i <url> -vframes 1 -update 1 output.jpg`

---

## 2. HAK Croatia (m.hak.hr) — SECONDARY SOURCE

- **Format:** JPEG snapshots
- **Resolution:** 640x360
- **Refresh rate:** ~30 seconds
- **URL pattern:** `https://m.hak.hr/cam.asp?id=XX&t=<timestamp>`
- **Authentication:** None
- **Overlay info:** Timestamp, temperature, direction labels (HR/SLO/SRB)

### Border Crossing Cameras:
| Crossing | Border | Camera IDs |
|----------|--------|-----------|
| Bregana | HR ↔ SLO | 6, 7 |
| Macelj | HR ↔ SLO | 34, 35 |
| Pasjak | HR ↔ SLO | 40, 41 |
| Bajakovo | HR ↔ SRB | 52, 53 |
| Stara Gradiška | HR ↔ BiH | 26 |

### Refresh mechanism (from kamera.js):
- JavaScript timer refreshes images every N seconds (configured per camera via `<span id="s_XXX">30</span>`)
- URL includes `&t=timestamp` cache buster
- On error, shows placeholder image

---

## 3. Unavailable Sources

### AMSS (kamere.amss.org.rs)
- **Status:** Blocked by Cloudflare
- Would require browser automation (Puppeteer/Playwright) to access
- Not worth the effort for MVP

### 011info.com
- Embeds YouTube streams, not direct camera feeds
- Unreliable, depends on third-party streamers

### uzivokamere.com
- WooCommerce product catalog, just links to other sources
- No direct feeds
