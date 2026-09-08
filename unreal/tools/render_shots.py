"""Kadry z poziomu Room, po jednym na wariant i widok.

Uruchamiany w edytorze z prawdziwa grafika (nie w komandlecie z -nullrhi),
bo zdjecie musi przejsc przez pelny post-process.

Dlaczego przez tick, a nie petla: HighResShot wykonuje sie na nastepnej
klatce, a Lumen liczy swiatlo posrednie przez kilkadziesiat klatek zanim
obraz przestanie szumiec. Petla w pythonie blokuje edytor i klatka nigdy nie
przychodzi. Dlatego to jest automat stanow zawieszony na ticku slate.

Wejscie przez zmienne srodowiskowe:
    ROOM_SCENE    - scene.json (widoki i warianty)
    ROOM_RENDERS  - katalog na gotowe pliki
    ROOM_SHOT_RES - rozdzielczosc, np. "2560x1440" (domyslnie)
"""

import json
import math
import os
import shutil

import unreal

WYSOKOSC_OCZU_M = 1.55
M_TO_UU = 100.0
KLATKI_NA_ZBIEZNOSC = 90
KLATKI_PO_ZDJECIU = 20
KLATKI_NA_PLIK = 200
ZESTAW = "Wykonczenie"

log = unreal.log


def konsola(polecenie):
    unreal.SystemLibrary.execute_console_command(
        unreal.EditorLevelLibrary.get_editor_world(), polecenie)


def przygotuj_edytor():
    """Zdejmuje z widoku wszystko, co nalezy do edytora, a nie do pokoju.

    Trzy rzeczy zepsuly pierwsze kadry:
    - viewport moze "pilotowac" zaznaczonego aktora i wtedy co klatke wraca
      na jego pozycje, kasujac ustawienie kamery - stad kadry patrzace w dol;
    - zaznaczenie rysuje pomaranczowy obrys, ktory wchodzi na zdjecie;
    - widok edytora rysuje siatke i ikony, ktorych w zdjeciu byc nie moze.
    Tryb gry (game view) zdejmuje to wszystko naraz.
    """
    poziom = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    aktorzy = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for opis, akcja in (
        ("wyjscie z pilotowania", lambda: poziom.eject_pilot_level_actor()),
        ("odznaczenie aktorow", lambda: aktorzy.set_selected_level_actors([])),
        ("tryb gry", lambda: poziom.editor_set_game_view(True)),
        # Edytor domyslnie przestaje rysowac, gdy jego okno nie jest na
        # wierzchu - a wtedy HighResShot nie ma czego zapisac i kadr po prostu
        # nie powstaje. Pierwsza seria wyszla tylko do momentu, w ktorym okno
        # zeszlo na spod.
        ("wylaczenie usypiania w tle",
         lambda: unreal.get_default_object(
             getattr(unreal, "EditorPerformanceSettings")).set_editor_property(
                 "throttle_cpu_when_not_foreground", False)),
    ):
        try:
            akcja()
        except Exception as blad:  # noqa: BLE001
            log("[Room] {} nie przeszlo: {}".format(opis, blad))


def czysty_widok():
    """Wylacza wszystko, co jest pomoca edytora, a nie czescia pokoju."""
    # Ten sam wylacznik usypiania, ale przez konsole - gdy klasa ustawien nie
    # jest wystawiona do pythona (w 5.8 nie jest).
    konsola("Slate.bAllowThrottling 0")
    for flaga in ("Grid", "Selection", "SelectionOutline", "ModeWidgets",
                  "BillboardSprites", "LightRadius", "Bounds", "Constraints",
                  "Splines", "Snap", "CameraFrustums", "AudioRadius",
                  "MediaPlanes", "VolumeLightingSamples"):
        konsola("ShowFlag.{} 0".format(flaga))


def plan_ujec(scene, renders):
    """Lista kadrow: kazdy wariant razy kazdy widok z presentation.views."""
    widoki = (scene.get("presentation") or {}).get("views") or {}
    warianty = [w.get("id") for w in scene.get("variants", []) if w.get("id")]
    if not warianty:
        warianty = [None]
    ujecia = []
    for wariant in warianty:
        for nazwa, widok in widoki.items():
            pozycja = widok.get("position") or []
            if len(pozycja) < 2:
                continue
            cel = widok.get("target") or [pozycja[0], pozycja[1] - 1.0]
            ujecia.append({
                "wariant": wariant,
                "widok": nazwa,
                "pozycja": pozycja,
                "cel": cel,
                "plik": os.path.join(renders, "{}-{}.png".format(
                    wariant or "scena", nazwa)),
            })
    return ujecia


def ustaw_kamere(ujecie):
    """Kamera na wysokosci oczu, pozioma.

    Pion trzymamy pionowo - fotograf architektury nie zadziera aparatu, bo
    wtedy sciany zbiegaja sie ku gorze i zdjecie wyglada jak z telefonu.
    Dlatego pitch zostaje zerem, a kadr dobiera sie pozycja.
    """
    px, py = float(ujecie["pozycja"][0]), float(ujecie["pozycja"][1])
    tx, ty = float(ujecie["cel"][0]), float(ujecie["cel"][1])
    yaw = math.degrees(math.atan2(-(ty - py), tx - px))
    unreal.EditorLevelLibrary.set_level_viewport_camera_info(
        unreal.Vector(px * M_TO_UU, -py * M_TO_UU, WYSOKOSC_OCZU_M * M_TO_UU),
        unreal.Rotator(0.0, 0.0, yaw))


def przelacz_wariant(wariant):
    if not wariant:
        return
    for aktor in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem).get_all_level_actors():
        if isinstance(aktor, unreal.LevelVariantSetsActor):
            aktor.switch_on_variant_by_name(ZESTAW, wariant)
            return


class Renderownia(object):
    """Automat stanow: ustaw kadr, poczekaj az swiatlo sie uspokoi, zdjecie."""

    def __init__(self, ujecia, katalog_zrzutow, rozdzielczosc, renders):
        self.ujecia = ujecia
        self.katalog_zrzutow = katalog_zrzutow
        self.rozdzielczosc = rozdzielczosc
        self.renders = renders
        self.i = 0
        self.licznik = 0
        self.faza = "ustaw"
        self.uchwyt = None
        self.gotowe = []
        self.ostatni_rozmiar = -1

    def start(self):
        if not self.ujecia:
            log("[Room] Nie ma czego renderowac - brak widokow w scene.json")
            unreal.SystemLibrary.quit_editor()
            return
        czysty_widok()
        self.uchwyt = unreal.register_slate_post_tick_callback(self.tick)

    def koniec(self):
        if self.uchwyt is not None:
            unreal.unregister_slate_post_tick_callback(self.uchwyt)
            self.uchwyt = None
        for wpis in self.gotowe:
            dopisz_do_raportu(self.renders, wpis)
        log("[Room] Kadry gotowe: {}".format(len(self.gotowe)))
        unreal.SystemLibrary.quit_editor()

    def sprzataj_zrzuty(self):
        """Pusty katalog przed zdjeciem = zero watpliwosci, ktory plik jest czyj.

        Branie "najnowszego pliku" myli sie, gdy silnik zapisze z opoznieniem:
        kadr dostaje wtedy nazwe poprzedniego i cala seria jest przesunieta.
        """
        if not os.path.isdir(self.katalog_zrzutow):
            return
        for nazwa in os.listdir(self.katalog_zrzutow):
            if nazwa.lower().endswith(".png"):
                try:
                    os.remove(os.path.join(self.katalog_zrzutow, nazwa))
                except OSError:
                    pass

    def zbierz_plik(self, ujecie):
        if not os.path.isdir(self.katalog_zrzutow):
            return None
        pliki = [os.path.join(self.katalog_zrzutow, n)
                 for n in os.listdir(self.katalog_zrzutow)
                 if n.lower().endswith(".png")]
        if not pliki:
            return None
        # Plik moze byc jeszcze zapisywany - bierzemy go dopiero, gdy rozmiar
        # przestaje rosnac.
        sciezka = max(pliki, key=os.path.getmtime)
        rozmiar = os.path.getsize(sciezka)
        if rozmiar == 0 or rozmiar != self.ostatni_rozmiar:
            self.ostatni_rozmiar = rozmiar
            return None
        shutil.move(sciezka, ujecie["plik"])
        self.ostatni_rozmiar = -1
        return ujecie["plik"]

    def tick(self, delta):
        # ExecCmds potrafi odpalic skrypt, zanim poziom jest wczytany.
        # Bez tego pierwsze ustawienie kamery poszloby w pustke.
        if unreal.EditorLevelLibrary.get_editor_world() is None:
            return
        # Edytor odrysowuje viewport tylko wtedy, gdy uzna, ze jest po co -
        # a gdy jego okno jest pod spodem, uznaje, ze nie ma. Zakolejkowany
        # HighResShot czeka wtedy w nieskonczonosc na klatke, ktora nie
        # przychodzi: pierwszy kadr wychodzil (okno bylo swieze na wierzchu),
        # drugi juz nie. Wymuszamy odrysowanie co tick.
        try:
            unreal.get_editor_subsystem(
                unreal.LevelEditorSubsystem).editor_invalidate_viewports()
        except Exception:  # noqa: BLE001
            pass
        ujecie = self.ujecia[self.i]
        if self.faza == "ustaw":
            przelacz_wariant(ujecie["wariant"])
            przygotuj_edytor()
            ustaw_kamere(ujecie)
            czysty_widok()
            self.sprzataj_zrzuty()
            self.licznik = 0
            self.faza = "czekaj"
            return
        if self.faza == "czekaj":
            self.licznik += 1
            if self.licznik >= KLATKI_NA_ZBIEZNOSC:
                konsola("HighResShot {}".format(self.rozdzielczosc))
                self.licznik = 0
                self.faza = "zapis"
            return
        if self.faza == "zapis":
            self.licznik += 1
            if self.licznik < KLATKI_PO_ZDJECIU:
                return
            plik = self.zbierz_plik(ujecie)
            if plik is None and self.licznik < KLATKI_NA_PLIK:
                return
            if plik:
                self.gotowe.append({"wariant": ujecie["wariant"],
                                    "widok": ujecie["widok"],
                                    "plik": plik})
                log("[Room] {}".format(plik))
            else:
                log("[Room] Brak pliku dla {} {}".format(
                    ujecie["wariant"], ujecie["widok"]))
            self.i += 1
            self.faza = "ustaw"
            if self.i >= len(self.ujecia):
                self.koniec()


def dopisz_do_raportu(renders, wpis):
    """Raport zbiera sie miedzy uruchomieniami, bo kazdy kadr ma swoje."""
    sciezka = os.path.join(renders, "render-report.json")
    dane = {"kadry": []}
    if os.path.isfile(sciezka):
        try:
            with open(sciezka, encoding="utf-8") as plik:
                dane = json.load(plik)
        except ValueError:
            dane = {"kadry": []}
    dane.setdefault("kadry", [])
    dane["kadry"] = [k for k in dane["kadry"]
                     if k.get("plik") != wpis.get("plik")]
    dane["kadry"].append(wpis)
    with open(sciezka, "w", encoding="utf-8") as plik:
        json.dump(dane, plik, ensure_ascii=False, indent=1)


def main():
    scene = json.load(open(os.environ["ROOM_SCENE"], encoding="utf-8"))
    renders = os.environ.get("ROOM_RENDERS") or os.path.join(
        unreal.Paths.project_saved_dir(), "Kadry")
    os.makedirs(renders, exist_ok=True)
    rozdzielczosc = os.environ.get("ROOM_SHOT_RES", "2560x1440")
    katalog_zrzutow = os.path.abspath(os.path.join(
        unreal.Paths.project_saved_dir(), "Screenshots", "WindowsEditor"))
    ujecia = plan_ujec(scene, renders)
    # Jeden kadr na uruchomienie edytora. Seria w jednej sesji dziala tylko
    # dla pierwszego zdjecia: kolejne HighResShot zostaja w kolejce i nigdy
    # sie nie wykonuja (sprawdzone - wymuszanie odrysowania i wylaczanie
    # usypiania w tle nie pomaga). Osobny proces na kadr jest wolniejszy,
    # ale wychodzi za kazdym razem.
    indeks = int(os.environ.get("ROOM_SHOT_INDEX", "-1"))
    if indeks >= 0:
        if indeks >= len(ujecia):
            log("[Room] Nie ma kadru numer {}".format(indeks))
            unreal.SystemLibrary.quit_editor()
            return
        ujecia = [ujecia[indeks]]
    log("[Room] Kadrow do zrobienia: {}, rozdzielczosc {}".format(
        len(ujecia), rozdzielczosc))
    Renderownia(ujecia, katalog_zrzutow, rozdzielczosc, renders).start()


main()
