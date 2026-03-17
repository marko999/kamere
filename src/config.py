"""Camera configuration and application constants."""

# ---------------------------------------------------------------------------
# Application settings
# ---------------------------------------------------------------------------
FRAME_INTERVAL = 30  # seconds between frame grabs
FRAMES_DIR = "frames"
DB_PATH = "kamere.db"

# ---------------------------------------------------------------------------
# MUP base URL
# ---------------------------------------------------------------------------
_MUP_BASE = "https://kamere.mup.gov.rs:4443"

# ---------------------------------------------------------------------------
# Helper to build MUP camera pairs (cam1=entrance, cam2=exit)
# ---------------------------------------------------------------------------

def _mup_pair(crossing_name: str, path: str, slug: str) -> list[dict]:
    """Return entrance + exit camera dicts for one MUP crossing."""
    return [
        {
            "id": f"{slug}_1",
            "name": f"{crossing_name} - Ulaz",
            "crossing": crossing_name,
            "direction": "entrance",
            "source_type": "mup",
            "url": f"{_MUP_BASE}/{path}/{slug}1.m3u8",
        },
        {
            "id": f"{slug}_2",
            "name": f"{crossing_name} - Izlaz",
            "crossing": crossing_name,
            "direction": "exit",
            "source_type": "mup",
            "url": f"{_MUP_BASE}/{path}/{slug}2.m3u8",
        },
    ]


# ---------------------------------------------------------------------------
# All cameras
# ---------------------------------------------------------------------------

CAMERAS: list[dict] = [
    # ── MUP Serbia (HLS streams) ─────────────────────────────────────────
    #          crossing_name    URL path       slug
    *_mup_pair("Djala",         "Djala",       "djala"),
    *_mup_pair("Kelebija",     "Kelebija",    "kelebija"),
    *_mup_pair("Horgos",       "Horgos",      "horgos"),
    *_mup_pair("Jabuka",       "Jabuka",      "jabuka"),
    *_mup_pair("Gostun",       "Gostun",      "gostun"),
    *_mup_pair("Spiljani",     "Spiljani",    "spiljani"),
    *_mup_pair("Batrovci",     "Batrovci",    "batrovci"),
    *_mup_pair("Sid",          "Sid",         "sid"),
    *_mup_pair("Vatin",        "Vatin",       "vatin"),
    *_mup_pair("Kotroman",     "Kotroman",    "kotroman"),
    *_mup_pair("Mali Zvornik", "MaliZvornik", "malizvornik"),
    *_mup_pair("Sremska Raca", "SremskaRaca", "sremskaraca"),
    *_mup_pair("Trbusnica",    "Trbusnica",   "trbusnica"),
    *_mup_pair("Vrska Cuka",   "VrskaCuka",   "vrskacuka"),
    *_mup_pair("Gradina",      "Gradina",     "gradina"),
    *_mup_pair("Presevo",      "Presevo",     "presevo"),

    # ── HAK Croatia (JPEG snapshots) ─────────────────────────────────────
    {
        "id": "bregana_6",
        "name": "Bregana (cam 6)",
        "crossing": "Bregana",
        "direction": "entrance",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=6",
    },
    {
        "id": "bregana_7",
        "name": "Bregana (cam 7)",
        "crossing": "Bregana",
        "direction": "exit",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=7",
    },
    {
        "id": "macelj_34",
        "name": "Macelj (cam 34)",
        "crossing": "Macelj",
        "direction": "entrance",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=34",
    },
    {
        "id": "macelj_35",
        "name": "Macelj (cam 35)",
        "crossing": "Macelj",
        "direction": "exit",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=35",
    },
    {
        "id": "pasjak_40",
        "name": "Pasjak (cam 40)",
        "crossing": "Pasjak",
        "direction": "entrance",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=40",
    },
    {
        "id": "pasjak_41",
        "name": "Pasjak (cam 41)",
        "crossing": "Pasjak",
        "direction": "exit",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=41",
    },
    {
        "id": "bajakovo_52",
        "name": "Bajakovo (cam 52)",
        "crossing": "Bajakovo",
        "direction": "entrance",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=52",
    },
    {
        "id": "bajakovo_53",
        "name": "Bajakovo (cam 53)",
        "crossing": "Bajakovo",
        "direction": "exit",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=53",
    },
    {
        "id": "stara_gradiska_26",
        "name": "Stara Gradiska (cam 26)",
        "crossing": "Stara Gradiska",
        "direction": "entrance",
        "source_type": "hak",
        "url": "https://m.hak.hr/cam.asp?id=26",
    },
]

# ---------------------------------------------------------------------------
# Quick lookup helpers
# ---------------------------------------------------------------------------

def get_camera(camera_id: str) -> dict | None:
    """Return camera dict by id, or None."""
    for cam in CAMERAS:
        if cam["id"] == camera_id:
            return cam
    return None


def get_cameras_for_crossing(crossing: str) -> list[dict]:
    """Return all cameras for a given crossing name."""
    return [c for c in CAMERAS if c["crossing"] == crossing]


# Unique crossing names (preserving insertion order)
CROSSINGS: list[str] = list(dict.fromkeys(c["crossing"] for c in CAMERAS))
