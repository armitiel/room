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

# Stolarka. Oscieznica lini otwor od srodka, wiec swiatlo przejscia jest
# o dwie szerokosci ramy wezsze niz otwor w scianie - tak samo jak w budynku.
FRAME_WIDTH_M = 0.06
GLASS_THICKNESS_M = 0.012
DOOR_LEAF_THICKNESS_M = 0.04

# Role powierzchni. Wykonczenie przypisuje sie do roli, a nie do obiektu,
# zeby ten sam wariant dzialal na kazdej scenie bez przepisywania nazw.
SURFACE_ROLES = (
    "floor",
    "ceiling",
    "wall",
    "frame_window",
    "frame_door",
    "glass",
    "leaf",
)

# Wzory tekstur, ktore przegladarka umie narysowac proceduralnie.
# Zadnych plikow zewnetrznych - demo ma dzialac bez sieci.
FINISH_PATTERNS = ("plain", "plaster", "planks", "tiles", "screed")

# Kontrola powierzchni: pokoj moze podac expected_area_m2 przepisane
# z dokumentacji. Rozbieznosc miedzy ta liczba a powierzchnia policzona
# z wielokata jest najtanszym testem, czy rzut przepisano poprawnie.
AREA_WARNING_RATIO = 0.01   # 1 % - ostrzezenie, warto spojrzec
AREA_ERROR_RATIO = 0.03     # 3 % - blad, rzut przepisano zle
AREA_ABSOLUTE_FLOOR_M2 = 0.05  # przy malych pomieszczeniach procenty klamia
