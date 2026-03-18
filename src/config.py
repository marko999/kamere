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
# Camera view types:
#   "queue"        — A tier: sees actual queue/waiting line, wait time reliable
#   "approach"     — B tier: sees approach road or parking, partial info
#   "post_control" — C tier: sees area AFTER customs, useless for wait time
# ---------------------------------------------------------------------------


def _mup_cam(crossing_name: str, path: str, slug: str, num: int,
             direction: str, view_type: str) -> dict:
    """Build a single MUP camera dict."""
    label = "Ulaz" if direction == "entrance" else "Izlaz"
    return {
        "id": f"{slug}_{num}",
        "name": f"{crossing_name} - {label}",
        "crossing": crossing_name,
        "direction": direction,
        "source_type": "mup",
        "view_type": view_type,
        "url": f"{_MUP_BASE}/{path}/{slug}{num}.m3u8",
    }


# ---------------------------------------------------------------------------
# All cameras — classified by what each camera actually sees
# ---------------------------------------------------------------------------

CAMERAS: list[dict] = [
    # ── Đala (SRB-HUN) — small crossing, road approach ────────────────
    _mup_cam("Djala", "Djala", "djala", 1, "entrance", "approach"),
    _mup_cam("Djala", "Djala", "djala", 2, "exit", "approach"),

    # ── Kelebija (SRB-HUN) — cam2 sees queue to booths ────────────────
    _mup_cam("Kelebija", "Kelebija", "kelebija", 1, "entrance", "post_control"),
    _mup_cam("Kelebija", "Kelebija", "kelebija", 2, "exit", "queue"),

    # ── Horgoš (SRB-HUN) — BOTH cameras see post-control zone ─────────
    _mup_cam("Horgos", "Horgos", "horgos", 1, "entrance", "post_control"),
    _mup_cam("Horgos", "Horgos", "horgos", 2, "exit", "post_control"),

    # ── Jabuka (SRB-ROU) — narrow road approach ───────────────────────
    _mup_cam("Jabuka", "Jabuka", "jabuka", 1, "entrance", "approach"),
    _mup_cam("Jabuka", "Jabuka", "jabuka", 2, "exit", "approach"),

    # ── Gostun (SRB-MNE) — parking/approach ───────────────────────────
    _mup_cam("Gostun", "Gostun", "gostun", 1, "entrance", "approach"),
    _mup_cam("Gostun", "Gostun", "gostun", 2, "exit", "approach"),

    # ── Špiljani (SRB-MNE) — cam1 sees truck queue! ───────────────────
    _mup_cam("Spiljani", "Spiljani", "spiljani", 1, "entrance", "queue"),
    _mup_cam("Spiljani", "Spiljani", "spiljani", 2, "exit", "approach"),

    # ── Batrovci (SRB-HRV) — cam1 highway approach, cam2 post-control ─
    _mup_cam("Batrovci", "Batrovci", "batrovci", 1, "entrance", "approach"),
    _mup_cam("Batrovci", "Batrovci", "batrovci", 2, "exit", "post_control"),

    # ── Šid (SRB-HRV) — BOTH cameras see full truck queues! ──────────
    _mup_cam("Sid", "Sid", "sid", 1, "entrance", "queue"),
    _mup_cam("Sid", "Sid", "sid", 2, "exit", "queue"),

    # ── Vatin (SRB-ROU) — BOTH cameras see vehicle queues! ───────────
    _mup_cam("Vatin", "Vatin", "vatin", 1, "entrance", "queue"),
    _mup_cam("Vatin", "Vatin", "vatin", 2, "exit", "queue"),

    # ── Kotroman (SRB-BIH) — booth area ──────────────────────────────
    _mup_cam("Kotroman", "Kotroman", "kotroman", 1, "entrance", "approach"),
    _mup_cam("Kotroman", "Kotroman", "kotroman", 2, "exit", "approach"),

    # ── Mali Zvornik (SRB-BIH) — bridge + town street ────────────────
    _mup_cam("Mali Zvornik", "MaliZvornik", "malizvornik", 1, "entrance", "approach"),
    _mup_cam("Mali Zvornik", "MaliZvornik", "malizvornik", 2, "exit", "approach"),

    # ── Sremska Rača (SRB-BIH) — cam2 sees truck queue! ──────────────
    _mup_cam("Sremska Raca", "SremskaRaca", "sremskaraca", 1, "entrance", "approach"),
    _mup_cam("Sremska Raca", "SremskaRaca", "sremskaraca", 2, "exit", "queue"),

    # ── Trbušnica (SRB-BIH) — road approach ──────────────────────────
    _mup_cam("Trbusnica", "Trbusnica", "trbusnica", 1, "entrance", "approach"),
    _mup_cam("Trbusnica", "Trbusnica", "trbusnica", 2, "exit", "approach"),

    # ── Vrška Čuka (SRB-BGR) — small crossing ────────────────────────
    _mup_cam("Vrska Cuka", "VrskaCuka", "vrskacuka", 1, "entrance", "approach"),
    _mup_cam("Vrska Cuka", "VrskaCuka", "vrskacuka", 2, "exit", "approach"),

    # ── Gradina (SRB-BGR) — cam1 highway approach, sees trucks far ───
    _mup_cam("Gradina", "Gradina", "gradina", 1, "entrance", "queue"),
    _mup_cam("Gradina", "Gradina", "gradina", 2, "exit", "approach"),

    # ── Preševo (SRB-MKD) — cam1 wide parking with buses + cars ──────
    _mup_cam("Presevo", "Presevo", "presevo", 1, "entrance", "queue"),
    _mup_cam("Presevo", "Presevo", "presevo", 2, "exit", "approach"),

    # ── HAK Croatia (JPEG snapshots) — view_type TBD, default approach ─
    {"id": "bregana_6", "name": "Bregana (cam 6)", "crossing": "Bregana",
     "direction": "entrance", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=6"},
    {"id": "bregana_7", "name": "Bregana (cam 7)", "crossing": "Bregana",
     "direction": "exit", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=7"},
    {"id": "macelj_34", "name": "Macelj (cam 34)", "crossing": "Macelj",
     "direction": "entrance", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=34"},
    {"id": "macelj_35", "name": "Macelj (cam 35)", "crossing": "Macelj",
     "direction": "exit", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=35"},
    {"id": "pasjak_40", "name": "Pasjak (cam 40)", "crossing": "Pasjak",
     "direction": "entrance", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=40"},
    {"id": "pasjak_41", "name": "Pasjak (cam 41)", "crossing": "Pasjak",
     "direction": "exit", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=41"},
    {"id": "bajakovo_52", "name": "Bajakovo (cam 52)", "crossing": "Bajakovo",
     "direction": "entrance", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=52"},
    {"id": "bajakovo_53", "name": "Bajakovo (cam 53)", "crossing": "Bajakovo",
     "direction": "exit", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=53"},
    {"id": "stara_gradiska_26", "name": "Stara Gradiska (cam 26)", "crossing": "Stara Gradiska",
     "direction": "entrance", "source_type": "hak", "view_type": "approach",
     "url": "https://m.hak.hr/cam.asp?id=26"},
]

# ---------------------------------------------------------------------------
# Quick lookup helpers
# ---------------------------------------------------------------------------

# Camera view_type lookup
CAM_VIEW_TYPE: dict[str, str] = {cam["id"]: cam.get("view_type", "approach") for cam in CAMERAS}


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
