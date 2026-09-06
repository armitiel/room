"""Stale kontraktu sceny. Zrodlo prawdy: docs/architecture.md."""

SUPPORTED_SCHEMA_VERSIONS = ("0.1",)

UNITS = "m"
COORDINATE_SYSTEM = "right_handed_z_up"

# Status nadaje czlowiek. AI nie ma prawa ustawic "approved".
STATUS_DRAFT = "draft"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_APPROVED = "approved"
STATUS_EXAMPLE_ONLY = "example_only"

SCENE_STATUSES = (
    STATUS_DRAFT,
    STATUS_NEEDS_REVIEW,
    STATUS_APPROVED,
    STATUS_EXAMPLE_ONLY,
)

# Tylko scena o tym statusie moze trafic do generatora produkcyjnego.
BUILDABLE_STATUSES = (STATUS_APPROVED,)

OPENING_KINDS = ("door", "window", "passage")

# Tolerancja geometryczna w metrach. Ponizej tego progu dwa punkty
# uznajemy za ten sam punkt, a wymiar za zerowy.
EPS_M = 1e-6

# Progi zdrowego rozsadku - naruszenie daje ostrzezenie, nie blad.
MIN_ROOM_HEIGHT_M = 2.0
MAX_ROOM_HEIGHT_M = 6.0
MIN_ROOM_AREA_M2 = 1.0
MAX_ROOM_AREA_M2 = 500.0

DEFAULT_WALL_THICKNESS_M = 0.12
