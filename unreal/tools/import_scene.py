"""Budowa poziomu Room w Unrealu z FBX i manifestu z Blendera.

Skrypt uruchamia sie w silniku (komandlet pythonscript). Niczego nie zgaduje
z nazw zasobow: role, pomieszczenia i produkty bierze z manifestu, a kolory
wykonczen z tego samego scene.json, ktorego uzywa przegladarka. Dzieki temu
warianty "basic" i "premium" znacza w Unrealu dokladnie to samo, co w
RoomViewer.setVariant().

Wejscie przez zmienne srodowiskowe:
    ROOM_MANIFEST - manifest z blender/scripts/export_unreal.py
    ROOM_SCENE    - scene.json tej samej sceny
    ROOM_REPORT   - gdzie zapisac raport weryfikacyjny
"""

import json
import os

import unreal

ROOT = "/Game/Room"
P_MESHES = ROOT + "/Meshes"
P_MATERIALS = ROOT + "/Materials"
P_TEXTURES = ROOT + "/Textures"
P_MAPS = ROOT + "/Maps"
LEVEL_PATH = P_MAPS + "/L_Room"

M_TO_UU = 100.0
# Ta sama lista co w blender/scripts/export_unreal.py - listwa jest
# powierzchnia budowlana, wiec zmienia sie razem z wykonczeniem.
SURFACE_ROLES = ("floor", "wall", "ceiling", "skirting", "frame_window",
                 "frame_door", "glass", "leaf")

report = {"steps": [], "problems": [], "notes": []}


def step(name, **data):
    entry = {"step": name}
    entry.update(data)
    report["steps"].append(entry)
    unreal.log("[Room] {} {}".format(name, json.dumps(data, ensure_ascii=False)))


def problem(text):
    """Cos jest nie tak z wynikiem - budowa konczy sie bledem."""
    report["problems"].append(text)
    unreal.log_warning("[Room] PROBLEM: " + text)


def note(text):
    """Scena jest dobra, ale warto wiedziec, ktora droga poszla."""
    report["notes"].append(text)
    unreal.log_warning("[Room] UWAGA: " + text)


def need_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit("Brak zmiennej srodowiskowej {}".format(name))
    return value


def read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def hex_to_linear(value):
    """Kolor z scene.json jest w sRGB; Unreal liczy w przestrzeni liniowej."""
    text = str(value).lstrip("#")
    channels = [int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    out = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
           for c in channels]
    return unreal.LinearColor(out[0], out[1], out[2], 1.0)


def resolve_finish(variant, role, room_id):
    """Dokladnie ta sama regula co resolveFinish() w web/index.html:
    pasuje rola, a room_id albo nie wystepuje, albo sie zgadza; wygrywa
    ostatnie pasujace przypisanie."""
    chosen = None
    for assignment in variant.get("assignments", []):
        if assignment.get("role") != role:
            continue
        if "room_id" in assignment and assignment["room_id"] != room_id:
            continue
        chosen = assignment.get("finish")
    return chosen


# --- import FBX --------------------------------------------------------

def try_set(obj, name, value):
    """Ustawia wlasciwosc, jesli ta wersja silnika ja ma.

    Nazwy wlasciwosci swiatel i post-processu roznia sie miedzy wersjami
    silnika. Zamiast wywalac cala budowe na jednej literowce, zapisujemy
    w raporcie, czego nie udalo sie ustawic - scena powstanie, tylko bez
    tego jednego ustawienia.
    """
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception as error:  # noqa: BLE001 - kazdy powod jest ciekawy
        report.setdefault("pominiete_wlasciwosci", []).append(
            "{}: {}".format(name, error))
        return False


def clean_meshes():
    """Kasuje siatki z poprzedniej budowy, zanim wejdzie nowy FBX.

    Import nadpisuje zasoby o tych samych identyfikatorach, ale scena
    z mniejsza liczba obiektow zostawia sieroty: S0200 z mieszkania
    przezylby budowe pokoju i nikt by nie wiedzial, skad ta siatka jest.
    Gorzej - dopasowanie po poczatku nazwy w index_meshes() moglo by ja
    komus podstawic. Poziom i tak powstaje od zera, wiec nie ma czego
    zachowywac.

    Materialy leca razem z siatkami. Sa w calosci wyliczone z scene.json,
    a _create() zwraca istniejacy zasob bez zmian - wiec bez kasowania
    poprawka w materiale bazowym nie doszlaby do sceny nigdy.
    """
    usuniete = {}
    for katalog in (P_MESHES, P_MATERIALS):
        if not unreal.EditorAssetLibrary.does_directory_exist(katalog):
            continue
        usuniete[katalog] = len(
            unreal.EditorAssetLibrary.list_assets(katalog, recursive=True))
        unreal.EditorAssetLibrary.delete_directory(katalog)
    step("czyszczenie", usunieto=usuniete)


def import_fbx(fbx_path):
    """Import kazdej siatki osobno, w jej wlasnym ukladzie.

    transform_vertex_to_absolute=False jest tu istotne. Przy True kazda
    siatka ma wierzcholki we wspolrzednych sceny, wiec jej bryla obejmuje
    caly dom: silnik liczy wtedy pole odleglosci w maksymalnej
    rozdzielczosci dla kazdego z 246 obiektow (mierzone: 15-22 s na obiekt,
    czyli ponad godzina), a odciecie widoku przestaje dzialac. Przy False
    bryly sa ciasne, a pozycje bierzemy z manifestu.
    """
    mesh_data = unreal.FbxStaticMeshImportData()
    mesh_data.set_editor_property("combine_meshes", False)
    mesh_data.set_editor_property("transform_vertex_to_absolute", False)
    mesh_data.set_editor_property("auto_generate_collision", False)
    mesh_data.set_editor_property("generate_lightmap_u_vs", False)
    mesh_data.set_editor_property("convert_scene", True)
    mesh_data.set_editor_property("force_front_x_axis", False)
    mesh_data.set_editor_property("convert_scene_unit", False)
    mesh_data.set_editor_property("import_translation", unreal.Vector(0, 0, 0))
    # Uwaga: import_uniform_scale nie dziala - sprawdzone, silnik 5.8 wozi
    # FBX przez Interchange, ktory tej wartosci nie czyta. Przeliczenie
    # metrow na centymetry robi scale_meshes_to_cm() po imporcie.
    mesh_data.set_editor_property("import_uniform_scale", 1.0)

    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("mesh_type_to_import",
                                unreal.FBXImportType.FBXIT_STATIC_MESH)
    options.set_editor_property("static_mesh_import_data", mesh_data)

    task = unreal.AssetImportTask()
    task.set_editor_property("filename", fbx_path)
    task.set_editor_property("destination_path", P_MESHES)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", True)
    task.set_editor_property("save", False)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths"))
    step("import_fbx", plik=fbx_path, zaimportowane=len(paths))
    return paths


def index_meshes(ids):
    """Mapa identyfikator z manifestu -> StaticMesh.

    Silnik potrafi dokleic do nazwy przyrostek (obserwowane: "Mesh"), wiec
    dopasowujemy najpierw doslownie, a potem po poczatku nazwy. Kazdy zasob
    moze trafic tylko do jednego identyfikatora - inaczej dwa obiekty
    dostalyby te sama siatke i nikt by tego nie zauwazyl.
    """
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = {}
    for data in registry.get_assets_by_path(P_MESHES, recursive=True):
        asset = data.get_asset()
        if isinstance(asset, unreal.StaticMesh):
            assets[asset.get_name()] = asset

    found = {}
    uzyte = set()
    for key in ids:
        if key in assets:
            found[key] = assets[key]
            uzyte.add(key)
    for key in ids:
        if key in found:
            continue
        for name, asset in sorted(assets.items()):
            if name not in uzyte and name.startswith(key):
                found[key] = asset
                uzyte.add(name)
                break
    step("zasoby", w_projekcie=len(assets), dopasowane=len(found),
         nadmiarowe=sorted(set(assets) - uzyte)[:8])
    return found


# --- materialy ---------------------------------------------------------

def _create(name, path, cls, factory):
    full = "{}/{}".format(path, name)
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        return unreal.EditorAssetLibrary.load_asset(full)
    return unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name, path, cls, factory)


WORLD_ALIGNED = ("/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
                 "WorldAlignedTexture.WorldAlignedTexture")
WORLD_ALIGNED_NORMAL = ("/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
                        "WorldAlignedNormal.WorldAlignedNormal")
WHITE_TEXTURE = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"
# Nazwa wejscia rozmiaru zawiera w sobie typ i rozni sie miedzy wersjami
# silnika, a python nie pozwala odczytac listy wejsc funkcji. Probujemy po
# kolei; w 5.8 przechodzi "TextureSize".
WEJSCIA_ROZMIARU = ("TextureSize (V3)", "TextureSize", "WorldSize (V3)",
                    "WorldSize")


def world_aligned_normal(material, lib, rozmiar):
    """Mapa normalnych rzutowana tak samo jak kolor.

    Bez niej tynk i drewno sa gladkie jak szklo: kolor sie zgadza, ale
    swiatlo slizga sie po plaskiej plaszczyznie i wszystko czyta sie jak
    wydruk. Mapa normalnych daje mikroreliefe - to ona sprawia, ze tynk
    wyglada jak tynk.

    Suwak "UseNormal" jest po to, zeby wykonczenie bez mapy nie dostalo
    smieci: przy zerze mieszanie zwraca czysta normalna plaszczyzny.
    """
    funkcja = unreal.EditorAssetLibrary.load_asset(WORLD_ALIGNED_NORMAL)
    biala = unreal.EditorAssetLibrary.load_asset(WHITE_TEXTURE)
    if funkcja is None or biala is None:
        # Sprawdzone w 5.8: w katalogu Texturing sa tylko ScaleUVsByCenter,
        # TextureCropping i WorldAlignedTexture - funkcji do map normalnych
        # ten silnik nie ma. Podstawienie zwyklej WorldAlignedTexture nie
        # przejdzie, bo sampler w niej jest kolorowy, a mapa normalnych ma
        # inny typ i material sie nie skompiluje. Zeby miec relief, trzeba
        # albo napisac wlasna funkcje, albo rozwinac UV w Blenderze.
        note("Ten silnik nie ma WorldAlignedNormal - powierzchnie dostaja "
             "kolor i szorstkosc, bez mikroreliefu")
        return False
    tekstura = lib.create_material_expression(
        material, unreal.MaterialExpressionTextureObjectParameter, -1150, 260)
    tekstura.set_editor_property("parameter_name", "NormalTexture")
    tekstura.set_editor_property("texture", biala)
    suwak = lib.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -1150, 460)
    suwak.set_editor_property("parameter_name", "UseNormal")
    suwak.set_editor_property("default_value", 0.0)
    plaska = lib.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -820, 460)
    plaska.set_editor_property("constant", unreal.LinearColor(0.0, 0.0, 1.0, 1.0))
    wezel = lib.create_material_expression(
        material, unreal.MaterialExpressionMaterialFunctionCall, -820, 260)
    wezel.set_material_function(funkcja)
    mieszanie = lib.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -300, 300)

    for skad, wyjscie, dokad, wejscie in (
        (tekstura, "", wezel, "TextureObject"),
        (plaska, "", mieszanie, "A"),
        (wezel, "XYZ Texture", mieszanie, "B"),
        (suwak, "", mieszanie, "Alpha"),
    ):
        if not lib.connect_material_expressions(skad, wyjscie, dokad, wejscie):
            note("Mapa normalnych: nie udalo sie polaczyc {} w {}".format(
                wejscie, material.get_name()))
            return False
    for kandydat in WEJSCIA_ROZMIARU:
        if lib.connect_material_expressions(rozmiar, "", wezel, kandydat):
            break
    return lib.connect_material_property(
        mieszanie, "", unreal.MaterialProperty.MP_NORMAL)


def world_aligned_color(material, lib, color):
    """Tekstura rzutowana ze wspolrzednych swiata, bez UV.

    Dwadziescia scian, skosow i oscienic w tej scenie nie ma wspolrzednych UV
    w ogole - to plaszczyzny wyciete skryptem, nikt ich nie rozwijal. Zamiast
    dorabiac im UV, bierzemy teksture rzutowana z trzech osi: jej rozmiar
    podaje sie w centymetrach swiata, wiec "deska co 120 cm" znaczy tu
    dokladnie to samo, co format produktu w katalogu.

    Gdy wykonczenie nie ma tekstury, w gniezdzie siedzi biala i mnozenie
    zostawia czysty kolor - czyli to, co bylo wczesniej.
    """
    funkcja = unreal.EditorAssetLibrary.load_asset(WORLD_ALIGNED)
    biala = unreal.EditorAssetLibrary.load_asset(WHITE_TEXTURE)
    if funkcja is None or biala is None:
        note("Brak WorldAlignedTexture albo bialej tekstury - wykonczenia "
             "zostaja plaskim kolorem")
        return False
    tekstura = lib.create_material_expression(
        material, unreal.MaterialExpressionTextureObjectParameter, -1150, -200)
    tekstura.set_editor_property("parameter_name", "BaseTexture")
    tekstura.set_editor_property("texture", biala)
    rozmiar = lib.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -1150, 20)
    rozmiar.set_editor_property("parameter_name", "TextureSize")
    rozmiar.set_editor_property("default_value", 120.0)
    wezel = lib.create_material_expression(
        material, unreal.MaterialExpressionMaterialFunctionCall, -820, -140)
    wezel.set_material_function(funkcja)
    mnozenie = lib.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -300, -140)

    udalo = True
    for skad, wyjscie, dokad, wejscie in (
        (tekstura, "", wezel, "TextureObject"),
        (wezel, "XYZ Texture", mnozenie, "A"),
        (color, "", mnozenie, "B"),
    ):
        if not lib.connect_material_expressions(skad, wyjscie, dokad, wejscie):
            note("Nie udalo sie polaczyc {} -> {} w materiale {}".format(
                wyjscie or "wyjscie", wejscie, material.get_name()))
            udalo = False
    if not udalo:
        return False

    # Nazwa wejscia rozmiaru zawiera w sobie typ i rozni sie miedzy wersjami
    # silnika ("TextureSize (V3)" kontra "WorldSize"), a python nie pozwala
    # odczytac listy wejsc funkcji. Probujemy po kolei; jesli zadna nie
    # pasuje, funkcja uzyje swojej wartosci domyslnej - tekstura bedzie, tylko
    # w innej skali, i o tym mowi uwaga w raporcie.
    for kandydat in WEJSCIA_ROZMIARU:
        if lib.connect_material_expressions(rozmiar, "", wezel, kandydat):
            step("rozmiar_tekstury", material=material.get_name(),
                 wejscie=kandydat)
            break
    else:
        note("Nie znalazlem wejscia rozmiaru w WorldAlignedTexture - skala "
             "tekstur zostaje domyslna dla materialu {}".format(
                 material.get_name()))
    if not world_aligned_normal(material, lib, rozmiar):
        note("Material {} zostaje bez map normalnych".format(
            material.get_name()))
    return lib.connect_material_property(
        mnozenie, "", unreal.MaterialProperty.MP_BASE_COLOR)


def base_material(name, translucent=False):
    """Jeden material z parametrami; wykonczenia to jego instancje.

    Instancja nie kompiluje shadera od nowa, wiec 14 wykonczen i dwa
    warianty nie kosztuja nic poza pamiecia.
    """
    full = "{}/{}".format(P_MATERIALS, name)
    if unreal.EditorAssetLibrary.does_asset_exist(full):
        return unreal.EditorAssetLibrary.load_asset(full)

    material = _create(name, P_MATERIALS, unreal.Material,
                       unreal.MaterialFactoryNew())
    lib = unreal.MaterialEditingLibrary

    # Sciany, sufit i skosy w rekonstrukcji ze zdjec to plaszczyzny o zerowej
    # grubosci - jedna warstwa trojkatow. Silnik domyslnie rysuje tylko
    # przednia strone, wiec od srodka pokoju polowa scian po prostu znikala
    # i bylo widac niebo. Dwustronny material to naprawia; kosztuje tyle, ze
    # scena rysuje obie strony kazdej plaszczyzny.
    material.set_editor_property("two_sided", True)

    color = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -520, -100)
    color.set_editor_property("parameter_name", "BaseColor")
    color.set_editor_property("default_value",
                              unreal.LinearColor(0.75, 0.74, 0.72, 1.0))
    if not world_aligned_color(material, lib, color):
        lib.connect_material_property(color, "",
                                      unreal.MaterialProperty.MP_BASE_COLOR)

    rough = lib.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -520, 120)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", 0.8)
    lib.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)

    metal = lib.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, -520, 220)
    metal.set_editor_property("parameter_name", "Metallic")
    metal.set_editor_property("default_value", 0.0)
    lib.connect_material_property(metal, "", unreal.MaterialProperty.MP_METALLIC)

    if translucent:
        material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        material.set_editor_property("two_sided", True)
        opacity = lib.create_material_expression(
            material, unreal.MaterialExpressionScalarParameter, -520, 320)
        opacity.set_editor_property("parameter_name", "Opacity")
        opacity.set_editor_property("default_value", 0.25)
        lib.connect_material_property(opacity, "",
                                      unreal.MaterialProperty.MP_OPACITY)

    lib.recompile_material(material)
    return material


def import_textures(folder):
    """Wciaga pliki tekstur z dysku do projektu.

    Tekstury z blenda przychodza same, zaszyte w FBX. To sa te dobrane
    osobno - CC0 z ambientCG - i leza poza projektem, zeby nie puchl.
    Mapy normalnych dostaja wlasciwe ustawienia kompresji; bez tego silnik
    traktuje je jak zwykly obrazek i powierzchnia wychodzi niebieskawa.
    """
    if not folder or not os.path.isdir(folder):
        return
    pliki = []
    for korzen, _, nazwy in os.walk(folder):
        for nazwa in nazwy:
            if nazwa.lower().endswith((".jpg", ".jpeg", ".png", ".tga")):
                pliki.append(os.path.join(korzen, nazwa))
    if not pliki:
        return
    zadania = []
    for sciezka in pliki:
        zadanie = unreal.AssetImportTask()
        zadanie.set_editor_property("filename", sciezka)
        zadanie.set_editor_property("destination_path", P_TEXTURES)
        zadanie.set_editor_property("automated", True)
        zadanie.set_editor_property("replace_existing", True)
        zadanie.set_editor_property("save", False)
        zadania.append(zadanie)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(zadania)

    poprawione = 0
    for data in unreal.AssetRegistryHelpers.get_asset_registry() \
            .get_assets_by_path(P_TEXTURES, recursive=True):
        asset = data.get_asset()
        if not isinstance(asset, unreal.Texture2D):
            continue
        nazwa = asset.get_name()
        if "Normal" in nazwa:
            try_set(asset, "compression_settings",
                    unreal.TextureCompressionSettings.TC_NORMALMAP)
            try_set(asset, "srgb", False)
            poprawione += 1
        elif "Roughness" in nazwa or "Displacement" in nazwa:
            try_set(asset, "srgb", False)
            poprawione += 1
    step("import_tekstur", katalog=folder, plikow=len(pliki),
         poprawione_mapy=poprawione)


def index_textures():
    """Mapa nazwa zasobu -> Texture2D, ze wszystkiego, co przyszlo z FBX."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    znalezione = {}
    for data in registry.get_assets_by_path(ROOT, recursive=True):
        asset = data.get_asset()
        if isinstance(asset, unreal.Texture2D):
            znalezione[asset.get_name()] = asset
    step("tekstury", znalezione=sorted(znalezione))
    return znalezione


def finish_instance(variant_id, finish_id, finish, opaque, glass, tekstury):
    name = "MI_{}_{}".format(variant_id, finish_id).replace("-", "_")
    full = "{}/{}".format(P_MATERIALS, name)
    existed = unreal.EditorAssetLibrary.does_asset_exist(full)
    instance = _create(name, P_MATERIALS, unreal.MaterialInstanceConstant,
                       unreal.MaterialInstanceConstantFactoryNew())
    lib = unreal.MaterialEditingLibrary
    has_opacity = "opacity" in finish
    if not existed:
        lib.set_material_instance_parent(instance, glass if has_opacity else opaque)

    # Tekstura niesie wlasny kolor, wiec mnozenie zostawiamy neutralne -
    # inaczej barwa zastepcza przyciemnilaby zdjecie drugi raz.
    nazwa_tekstury = str(finish.get("texture", ""))
    tekstura = tekstury.get(nazwa_tekstury) if nazwa_tekstury else None
    if nazwa_tekstury and tekstura is None:
        note("Wykonczenie {} prosi o teksture {}, ktorej nie ma w projekcie"
             .format(finish_id, nazwa_tekstury))
    if tekstura is not None:
        lib.set_material_instance_texture_parameter_value(
            instance, "BaseTexture", tekstura)
        # Bez barwienia mnozymy przez biel, czyli zostawiamy teksture taka,
        # jaka jest. "tint" sluzy do tego, zeby ta sama deska mogla byc raz
        # ciemniejsza, raz jasniejsza - bez trzymania dwoch plikow.
        lib.set_material_instance_vector_parameter_value(
            instance, "BaseColor",
            hex_to_linear(finish["tint"]) if finish.get("tint")
            else unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    else:
        lib.set_material_instance_vector_parameter_value(
            instance, "BaseColor", hex_to_linear(finish.get("color", "#cccccc")))
    mapa = tekstury.get(str(finish.get("normal", ""))) if finish.get("normal") else None
    if mapa is not None:
        lib.set_material_instance_texture_parameter_value(
            instance, "NormalTexture", mapa)
        lib.set_material_instance_scalar_parameter_value(
            instance, "UseNormal", 1.0)
    else:
        lib.set_material_instance_scalar_parameter_value(
            instance, "UseNormal", 0.0)
        if finish.get("normal"):
            note("Wykonczenie {} prosi o mape normalnych {}, ktorej nie ma"
                 .format(finish_id, finish.get("normal")))
    # scale_m to realny format produktu: deska co 1,2 m, plytka co 0,3 m.
    lib.set_material_instance_scalar_parameter_value(
        instance, "TextureSize", float(finish.get("scale_m", 1.2)) * M_TO_UU)
    lib.set_material_instance_scalar_parameter_value(
        instance, "Roughness", float(finish.get("roughness", 0.8)))
    lib.set_material_instance_scalar_parameter_value(instance, "Metallic", 0.0)
    if has_opacity:
        lib.set_material_instance_scalar_parameter_value(
            instance, "Opacity", float(finish["opacity"]))
    return instance


# --- poziom ------------------------------------------------------------

def plan_to_ue(px, py, z_m=0.0):
    """Wspolrzedne rzutu (metry, uklad Blendera) na uklad Unreala.

    Przejscie Blender -> Unreal to odbicie wzgledem plaszczyzny XZ:
    (x, y, z) -> (x, -y, z), plus metry na centymetry. To zalozenie jest
    sprawdzane w raporcie przez porownanie bryly kazdego obiektu.
    """
    return unreal.Vector(px * M_TO_UU, -py * M_TO_UU, z_m * M_TO_UU)


def mesh_size_uu(mesh):
    """Rozmiar bryly siatki w jednostkach silnika, albo None."""
    for getter in ("get_bounding_box", "get_bounds"):
        function = getattr(mesh, getter, None)
        if function is None:
            continue
        try:
            value = function()
        except Exception:  # noqa: BLE001
            continue
        low = getattr(value, "min", None)
        high = getattr(value, "max", None)
        if low is not None and high is not None:
            return [high.x - low.x, high.y - low.y, high.z - low.z]
        extent = getattr(value, "box_extent", None)
        if extent is not None:
            return [extent.x * 2, extent.y * 2, extent.z * 2]
    return None


def _apply_build_scale(api, meshes, value):
    for mesh in meshes:
        settings = api.get_lod_build_settings(mesh, 0)
        settings.set_editor_property("build_scale3d", value)
        api.set_lod_build_settings(mesh, 0, settings)


def scale_meshes_to_cm(meshes, sprawdzian):
    """Wpina mnoznik 100 w same siatki, zeby aktorzy mieli normalna skale.

    Blender zapisuje geometrie w metrach. Mozna to nadrobic skala aktora
    100, ale wtedy kazdy obiekt w edytorze ma skale w rodzaju [6, 12, 220]
    i nikt tego pozniej nie ruszy bez bledu. Build Scale przelicza siatke
    raz, przy budowie zasobu. Jesli API zawiedzie, wracamy do skali aktora
    i zapisujemy to w raporcie - lepsza brzydka scena niz zadna.
    """
    mnoznik = unreal.Vector(M_TO_UU, M_TO_UU, M_TO_UU)
    # W komandlecie StaticMeshEditorSubsystem bywa nieutworzony (zmierzone:
    # get_editor_subsystem zwraca None), wiec probujemy tez starszej
    # biblioteki z EditorScriptingUtilities.
    kandydaci = [
        ("StaticMeshEditorSubsystem",
         unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)),
        ("EditorStaticMeshLibrary",
         getattr(unreal, "EditorStaticMeshLibrary", None)),
    ]
    powody = []
    for nazwa, api in kandydaci:
        if api is None:
            powody.append("{}: brak".format(nazwa))
            continue
        try:
            _apply_build_scale(api, meshes, mnoznik)
        except Exception as error:  # noqa: BLE001 - interesuje nas kazdy powod
            powody.append("{}: {}".format(nazwa, error))
            continue
        # Samo ustawienie wlasciwosci nic nie znaczy, dopoki siatka nie
        # urosla. EditorStaticMeshLibrary przyjmuje ja bez bledu i zostawia
        # geometrie bez zmian - dlatego mierzymy, zamiast wierzyc. Gdy nie
        # zadzialalo, cofamy ustawienie: inaczej skala aktora zmnozylaby sie
        # kiedys ze skala budowy i dom urosl by sto razy.
        mesh, oczekiwany_m = sprawdzian
        zmierzony = mesh_size_uu(mesh)
        os_ = max(range(3), key=lambda a: oczekiwany_m[a])
        powod = None
        if zmierzony is None:
            powod = "nie da sie zmierzyc siatki"
        elif oczekiwany_m[os_] <= 1e-6:
            powod = "brak wymiaru do porownania"
        else:
            stosunek = zmierzony[os_] / (oczekiwany_m[os_] * M_TO_UU)
            if abs(stosunek - 1.0) > 0.01:
                powod = "siatka ma {:.3f} oczekiwanego rozmiaru".format(stosunek)
        if powod is None:
            step("skala_siatek", metoda=nazwa, siatek=len(meshes),
                 sprawdzenie={"os": os_, "stosunek": round(stosunek, 4)})
            return True
        powody.append("{}: {}".format(nazwa, powod))
        try:
            _apply_build_scale(api, meshes, unreal.Vector(1.0, 1.0, 1.0))
        except Exception as error:  # noqa: BLE001
            powody.append("{}: nie udalo sie cofnac ({})".format(nazwa, error))
    note("Build Scale nie zadzialalo ({}); skala 100 idzie na aktorow - "
         "scena jest poprawna, tylko pole Scale w edytorze pokazuje setki"
         .format("; ".join(powody)))
    return False


def distance_fields_two_sided(meshes):
    """Pola odleglosci liczone tak, jakby siatki mialy grubosc.

    Lumen szuka geometrii po polach odleglosci. Plaszczyzna bez grubosci ma
    takie pole prawie zerowe, wiec slonce swieci przez sciane i wnetrze
    dostaje plamy zamiast cienia. Ta flaga kaze silnikowi liczyc pole tak,
    jakby plaszczyzna byla zamknieta bryla.
    """
    api = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem) \
        or getattr(unreal, "EditorStaticMeshLibrary", None)
    if api is None:
        note("Brak API ustawien budowy siatek - pola odleglosci zostaja "
             "jednostronne, Lumen moze przeswiecac przez sciany")
        return False
    for mesh in meshes:
        try:
            settings = api.get_lod_build_settings(mesh, 0)
            settings.set_editor_property(
                "generate_distance_field_as_if_two_sided", True)
            api.set_lod_build_settings(mesh, 0, settings)
        except Exception as error:  # noqa: BLE001
            note("Pola odleglosci dwustronne nie weszly: {}".format(error))
            return False
    step("pola_odleglosci", dwustronne=len(meshes))
    return True


def entry_transform(entry, scale_factor=1.0):
    """Transformacja obiektu z manifestu, przelozona na uklad Unreala.

    Odbicie M = diag(1, -1, 1) zamienia obrot R na M R M. Dla kwaternionu
    (w, x, y, z) daje to (w, -x, y, -z): os obraca sie razem z ukladem, a
    zwrot obrotu zmienia sie, bo odbicie zmienia skretnosc. Skala po
    przeksztalceniu zostaje ta sama, bo M S M = S dla skali osiowej.
    """
    location = entry["location_m"]
    w, x, y, z = entry["quaternion_wxyz"]
    scale = entry["scale"]
    transform = unreal.Transform()
    transform.set_editor_property(
        "translation", plan_to_ue(location[0], location[1], location[2]))
    transform.set_editor_property("rotation", unreal.Quat(-x, y, -z, w))
    transform.set_editor_property(
        "scale3d", unreal.Vector(scale[0] * scale_factor,
                                 scale[1] * scale_factor,
                                 scale[2] * scale_factor))
    return transform


def ensure_collision(mesh):
    """Sciany maja wyciete otwory, wiec prosta bryla kolizji zaslepilaby
    drzwi. Uzywamy geometrii jako kolizji - pionek przechodzi tam, gdzie
    widac przejscie."""
    body = mesh.get_editor_property("body_setup")
    if body is None:
        subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        if subsystem is not None:
            subsystem.add_simple_collisions(mesh, unreal.ScriptCollisionShapeType.BOX)
        body = mesh.get_editor_property("body_setup")
    if body is None:
        return False
    body.set_editor_property(
        "collision_trace_flag",
        unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    return True


def spawn_window_lights(actors, editor, scene):
    """Prostokatne swiatlo tuz za kazdym oknem i drzwiami zewnetrznymi.

    Samo slonce wpada waskim snopem, a reszta okna jest tylko jasna dziura -
    w prawdziwym pokoju swieci cale niebo widoczne przez szybe, na calej
    powierzchni otworu. Dlatego w swietle otworu staje prostokat o jego
    wymiarach, odsuniety na zewnatrz i skierowany do srodka.

    Pozycje bierzemy z "openings" w scene.json, wiec nikt nie ustawia tego
    recznie - okno dodane w kontrakcie od razu dostaje swoje swiatlo.
    """
    import math
    postawione = []
    for room in scene.get("rooms", []):
        polygon = room.get("polygon_xy_m") or []
        if len(polygon) < 3:
            continue
        for opening in room.get("openings", []):
            if opening.get("kind") not in ("window",):
                continue
            i = int(opening.get("wall_index", 0)) % len(polygon)
            poczatek = polygon[i]
            koniec = polygon[(i + 1) % len(polygon)]
            dx, dy = koniec[0] - poczatek[0], koniec[1] - poczatek[1]
            dlugosc = math.hypot(dx, dy)
            if dlugosc < 1e-6:
                continue
            dx, dy = dx / dlugosc, dy / dlugosc
            szerokosc = float(opening.get("width_m", 1.0))
            wzdluz = float(opening.get("offset_m", 0.0)) + szerokosc / 2.0
            sx = poczatek[0] + dx * wzdluz
            sy = poczatek[1] + dy * wzdluz
            # Obrys jest zapisany przeciwnie do ruchu wskazowek zegara, wiec
            # normalna na zewnatrz to (dy, -dx). Odsuwamy swiatlo 25 cm za
            # lico sciany, zeby nie swiecilo od srodka w oscieznice.
            nx, ny = dy, -dx
            sx += nx * 0.25
            sy += ny * 0.25
            wysokosc = float(opening.get("height_m", 1.2))
            srodek_z = float(opening.get("sill_m", 0.0)) + wysokosc / 2.0
            yaw = math.degrees(math.atan2(ny, -nx))
            swiatlo = editor.spawn_actor_from_class(
                unreal.RectLight, plan_to_ue(sx, sy, srodek_z),
                unreal.Rotator(0.0, 0.0, yaw))
            swiatlo.set_actor_label("Swiatlo okna {}".format(room.get("id", "?")))
            komponent = swiatlo.rect_light_component
            try_set(komponent, "mobility", unreal.ComponentMobility.MOVABLE)
            try_set(komponent, "intensity_units", unreal.LightUnits.LUMENS)
            # Subtelnie: to ma wypelnic otwor swiatlem nieba, a nie zrobic
            # z okna reflektora.
            try_set(komponent, "intensity", 900.0)
            try_set(komponent, "use_temperature", True)
            try_set(komponent, "temperature", 7000.0)
            try_set(komponent, "source_width", szerokosc * M_TO_UU)
            try_set(komponent, "source_height", wysokosc * M_TO_UU)
            try_set(komponent, "attenuation_radius", 900.0)
            try_set(komponent, "barn_door_angle", 80.0)
            actors.append(swiatlo)
            postawione.append({"pokoj": room.get("id"),
                               "otwor": opening.get("kind"),
                               "szerokosc_m": szerokosc})
    step("swiatla_okien", postawione=postawione)


def spawn_lights(actors, scene):
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun = editor.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0, 0, 900),
        unreal.Rotator(0, -42, -140))
    sun.set_actor_label("Slonce")
    slonce = sun.light_component
    try_set(slonce, "intensity", 11.0)
    try_set(slonce, "mobility", unreal.ComponentMobility.MOVABLE)
    try_set(slonce, "use_temperature", True)
    # 6200 K to swiatlo dnia z lekka domieszka nieba. Przy 5600 K wnetrze
    # z brazowa podloga wychodzilo pomaranczowe, bo cieple swiatlo odbija
    # sie od cieplej podlogi i barwa mnozy sie sama przez siebie.
    try_set(slonce, "temperature", 6200.0)
    # Ostry, czarny cien bierze sie stad, ze slonce jest matematycznym
    # punktem. Prawdziwe zajmuje na niebie okolo pol stopnia i dlatego cien
    # ma miekka krawedz. Wieksza wartosc = szersza polcien; 1,5 stopnia
    # wyglada jak lekko zamglony dzien, a nie jak noz.
    try_set(slonce, "light_source_angle", 1.5)
    try_set(slonce, "light_source_soft_angle", 0.6)
    actors.append(sun)

    sky = editor.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 900))
    sky.set_actor_label("Niebo")
    niebo = sky.light_component
    try_set(niebo, "real_time_capture", True)
    # 7.0 i ta barwa to wartosci dobrane recznie w edytorze przez
    # uzytkownika (7 wrzesnia 2026) i odczytane z zapisanego poziomu.
    # Skrypt buduje poziom od zera, wiec zeby nie zginely, musza byc tutaj.
    # Odbarwione, lekko zielonkawe niebo daje cien szary zamiast granatowego.
    try_set(niebo, "intensity", 7.0)
    try_set(niebo, "light_color", unreal.Color(r=182, g=191, b=182, a=255))
    try_set(niebo, "mobility", unreal.ComponentMobility.MOVABLE)
    # Dolna polkula domyslnie jest czarna, wiec wnetrze nie dostaje nic od
    # ziemi. To wlasnie to swiatlo rozjasnia cienie w pokoju - bez niego
    # wszystko, na co nie pada slonce, jest czarne.
    try_set(niebo, "lower_hemisphere_is_black", False)
    try_set(niebo, "lower_hemisphere_color",
            unreal.LinearColor(0.14, 0.13, 0.12, 1.0))
    actors.append(sky)

    atmosphere = editor.spawn_actor_from_class(unreal.SkyAtmosphere,
                                               unreal.Vector(0, 0, 0))
    atmosphere.set_actor_label("Atmosfera")
    actors.append(atmosphere)

    # Swiatlo dzienne przez okna nie wystarcza w glebi rzutu - jedna lampa
    # na pomieszczenie, w srodku ciezkosci wielokata, tuz pod sufitem.
    for room in scene.get("rooms", []):
        polygon = room.get("polygon_xy_m") or []
        if not polygon:
            continue
        cx = sum(p[0] for p in polygon) / len(polygon)
        cy = sum(p[1] for p in polygon) / len(polygon)
        height = float(room.get("height_m", 2.7))
        # 35 cm pod sufitem lampa swiecila w spody szyn i opraw wiszacych
        # przy suficie, a te rzucaly na sufit wielkie ciemne plamy. 60 cm
        # nizej to nadal wysokosc zyrandola, a cien opraw robi sie maly.
        lamp = editor.spawn_actor_from_class(
            unreal.PointLight, plan_to_ue(cx, cy, height - 0.6))
        lamp.set_actor_label("Lampa {}".format(room.get("id", "?")))
        component = lamp.point_light_component
        try_set(component, "mobility", unreal.ComponentMobility.MOVABLE)
        # Lumeny zamiast liczby bez jednostki. 600 lm to zarowka LED okolo
        # 6 W - w dzien ma dopelniac, a nie przebijac okno. Przy 1400 lm
        # i 3000 K caly pokoj wychodzil pomaranczowy.
        try_set(component, "intensity_units", unreal.LightUnits.LUMENS)
        try_set(component, "intensity", 600.0)
        try_set(component, "use_temperature", True)
        try_set(component, "temperature", 3800.0)
        try_set(component, "attenuation_radius", 700.0)
        # Zarowka ma rozmiar, wiec jej cien tez ma miekka krawedz. Punktowe
        # zrodlo daje cien wyciety nozem - to samo, co przy sloncu.
        try_set(component, "source_radius", 8.0)
        try_set(component, "soft_source_radius", 25.0)
        try_set(component, "cast_shadows", True)
        actors.append(lamp)

    spawn_window_lights(actors, editor, scene)

    # Bez tego pierwszy przebieg wyszedl calkiem przeswietlony: przy
    # wylaczonej automatycznej ekspozycji jasnosc jest stala, a wnetrze
    # oswietlone lampami i niebem ja przekracza. Automat z ograniczeniami
    # sam sie dostraja w kazdym pomieszczeniu, zamiast zgadywac swiatla.
    volume = editor.spawn_actor_from_class(unreal.PostProcessVolume,
                                           unreal.Vector(0, 0, 0))
    volume.set_actor_label("Ekspozycja")
    volume.set_editor_property("unbound", True)
    settings = volume.get_editor_property("settings")
    for nazwa, wartosc in (
        ("auto_exposure_method", unreal.AutoExposureMethod.AEM_HISTOGRAM),
        ("auto_exposure_min_brightness", 0.03),
        ("auto_exposure_max_brightness", 6.0),
        ("auto_exposure_speed_up", 3.0),
        ("auto_exposure_speed_down", 1.0),
        # Zero, bo przy +0,6 sciany i posciel wychodzily przepalone na bialo.
        ("auto_exposure_bias", 0.0),
        # Lumen liczy swiatlo odbite. Bez niego swieci tylko to, na co pada
        # promien wprost, a kazdy cien jest czarna dziura - dokladnie to
        # bylo widac na zrzutach.
        ("dynamic_global_illumination_method",
         unreal.DynamicGlobalIlluminationMethod.LUMEN),
        ("reflection_method", unreal.ReflectionMethod.LUMEN),
        ("lumen_scene_lighting_quality", 2.0),
        ("lumen_scene_detail", 2.0),
        ("lumen_final_gather_quality", 2.0),
        # Pokoj ma 4 m, wiec dalekie promienie sa marnowane; 20 m wystarcza
        # z zapasem na to, co widac przez okno.
        ("lumen_max_trace_distance", 2000.0),
        ("ambient_occlusion_intensity", 0.4),
        ("bloom_intensity", 0.35),
    ):
        try_set(settings, "override_" + nazwa, True)
        try_set(settings, nazwa, wartosc)
    volume.set_editor_property("settings", settings)
    actors.append(volume)
    return actors


def spawn_player_start(scene):
    views = (scene.get("presentation") or {}).get("views") or {}
    start = None
    for name in ("salon", "wiatrolap"):
        if name in views:
            start = views[name]
            break
    if start is None and views:
        start = list(views.values())[0]
    if start is None:
        rooms = scene.get("rooms") or []
        if not rooms:
            return None
        polygon = rooms[0]["polygon_xy_m"]
        start = {"position": [sum(p[0] for p in polygon) / len(polygon),
                              sum(p[1] for p in polygon) / len(polygon)]}

    px, py = start["position"][0], start["position"][1]
    target = start.get("target") or [px, py - 1.0]
    # Yaw w Unrealu liczymy w tym samym ukladzie co pozycje: Y jest odwrocone.
    import math
    yaw = math.degrees(math.atan2(-(target[1] - py), target[0] - px))
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = editor.spawn_actor_from_class(
        unreal.PlayerStart, plan_to_ue(px, py, 0.9), unreal.Rotator(0, 0, yaw))
    actor.set_actor_label("Start")
    return actor


# --- warianty ----------------------------------------------------------

def material_property_path(actor):
    """Nazwa wlasciwosci materialu bywa inna miedzy wersjami silnika,
    wiec zamiast wpisywac ja na sztywno, pytamy o liste i wybieramy."""
    names = list(unreal.VariantManagerLibrary.get_capturable_properties(actor))
    wanted = [n for n in names if "Material" in n]
    # Szukamy slotu materialu, czyli "Material[0]". Samo "Material" w nazwie
    # nie wystarcza: lista zawiera tez "Material Cache Tile Count", ktore
    # jest liczba i przy pierwszym podejsciu wskoczylo tu zamiast materialu.
    element = [n for n in wanted if n.rstrip().endswith("Material[0]")]
    if not element:
        element = [n for n in wanted if "Material[" in n]
    return (element or [None])[0], wanted


VARIANT_SET_NAME = "Wykonczenie"


def build_variants(scene, surface_actors, materials_by_variant):
    """LevelVariantSets z tymi samymi identyfikatorami co w przegladarce."""
    lvs = unreal.VariantManagerLibrary.create_level_variant_sets_asset(
        "LVS_Wykonczenie", ROOT)
    variant_set = unreal.VariantSet()
    variant_set.set_display_text(VARIANT_SET_NAME)
    unreal.VariantManagerLibrary.add_variant_set(lvs, variant_set)

    # Sciezka wlasciwosci jest taka sama dla kazdego StaticMeshActor, a
    # get_capturable_properties chodzi po calym drzewie wlasciwosci - pytamy
    # wiec raz, a nie 278 razy.
    path, first_property_list = (None, [])
    if surface_actors:
        path, first_property_list = material_property_path(
            list(surface_actors.values())[0])
    made = []
    for definition in scene.get("variants", []):
        variant = unreal.Variant()
        variant.set_display_text(definition["id"])
        unreal.VariantManagerLibrary.add_variant(variant_set, variant)
        captured = 0
        for key, actor in surface_actors.items():
            instance = materials_by_variant[definition["id"]].get(key)
            if instance is None:
                continue
            unreal.VariantManagerLibrary.add_actor_binding(variant, actor)
            if path is None:
                continue
            value = unreal.VariantManagerLibrary.capture_property(variant, actor, path)
            if value is None:
                continue
            unreal.VariantManagerLibrary.set_value_object(value, instance)
            captured += 1
        made.append({"id": definition["id"], "przechwycone": captured})
    step("warianty", zestawy=made, uzyta_wlasciwosc=path,
         wlasciwosci_materialu=[n for n in (first_property_list or [])
                                if "Material" in n][:8])

    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = editor.spawn_actor_from_class(unreal.LevelVariantSetsActor,
                                          unreal.Vector(0, 0, 0))
    actor.set_actor_label("Warianty wykonczenia")
    actor.set_level_variant_sets(lvs)
    # Ten sam identyfikator co RoomViewer.setVariant('basic'):
    # aktor.switch_on_variant_by_name('Wykonczenie', 'basic').
    default_id = (scene.get("variants") or [{}])[0].get("id")
    if default_id:
        actor.switch_on_variant_by_name(VARIANT_SET_NAME, default_id)
    return lvs, actor


# --- calosc ------------------------------------------------------------

def main():
    manifest = read_json(need_env("ROOM_MANIFEST"))
    scene = read_json(need_env("ROOM_SCENE"))
    report_path = need_env("ROOM_REPORT")
    report["manifest"] = {k: manifest[k] for k in
                          ("scene_id", "fbx_sha256", "mesh_count", "size_m")}
    report["scene_status"] = scene.get("status")
    report["scene_id"] = scene.get("scene_id")

    clean_meshes()
    import_fbx(manifest["fbx"])
    import_textures(os.environ.get("ROOM_TEXTURES", ""))
    meshes = index_meshes([entry["id"] for entry in manifest["meshes"]])
    wzorzec = next((e for e in manifest["meshes"] if e["id"] in meshes), None)
    sprawdzian = (meshes[wzorzec["id"]],
                  [wzorzec["local_max_m"][a] - wzorzec["local_min_m"][a]
                   for a in range(3)]) if wzorzec else (None, [0, 0, 0])
    w_siatkach = bool(wzorzec) and scale_meshes_to_cm(list(meshes.values()),
                                                      sprawdzian)
    scale_factor = 1.0 if w_siatkach else M_TO_UU
    step("skala", w_siatkach=w_siatkach, mnoznik_aktora=scale_factor)
    distance_fields_two_sided(list(meshes.values()))

    level = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    # new_level tworzy i od razu zapisuje zasob, wiec przy drugim przebiegu
    # zwraca False. Wtedy otwieramy istniejacy poziom i czyscimy go, zamiast
    # kasowac plik - buduje sie tak samo, a nic nie ginie.
    if not level.new_level(LEVEL_PATH):
        if not level.load_level(LEVEL_PATH):
            raise SystemExit("Nie udalo sie ani utworzyc, ani otworzyc "
                             "poziomu {}".format(LEVEL_PATH))
        stare = editor.get_all_level_actors()
        editor.destroy_actors(stare)
        step("poziom", tryb="ponowne uzycie", usunieto_aktorow=len(stare))
    else:
        step("poziom", tryb="nowy")

    opaque = base_material("M_RoomSurface")
    glass = base_material("M_RoomGlass", translucent=True)
    finishes = scene.get("finishes") or {}
    tekstury = index_textures()
    instances = {}
    for definition in scene.get("variants", []):
        for finish_id, finish in finishes.items():
            instances[(definition["id"], finish_id)] = finish_instance(
                definition["id"], finish_id, finish, opaque, glass, tekstury)
    step("materialy", instancji=len(instances), wykonczen=len(finishes))

    default_variant = (scene.get("variants") or [{}])[0].get("id")
    surface_actors = {}
    by_variant = {d["id"]: {} for d in scene.get("variants", [])}
    spawned, missing, no_collision, placed = [], [], [], []

    for entry in manifest["meshes"]:
        mesh = meshes.get(entry["id"])
        if mesh is None:
            missing.append(entry["id"])
            continue
        if not ensure_collision(mesh):
            no_collision.append(entry["id"])
        # spawn_actor_from_object nie dziala w komandlecie (silnik zglasza
        # "No actor was spawned"), wiec stawiamy aktora z klasy i sami
        # podpinamy siatke.
        actor = editor.spawn_actor_from_class(unreal.StaticMeshActor,
                                              unreal.Vector(0, 0, 0),
                                              unreal.Rotator(0, 0, 0))
        if actor is None:
            missing.append(entry["id"])
            continue
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.set_actor_transform(entry_transform(entry, scale_factor),
                                  False, False)
        actor.set_actor_label("{} {}".format(entry["id"], entry["blender_name"]))
        actor.set_folder_path("Room/{}".format(entry["role"]))
        if entry["role"] == "glass":
            # Szyba jest przezroczysta, ale jej cien w Lumenie jest pelny -
            # okno rzucaloby na podloge ciemny prostokat zamiast swiatla.
            try_set(actor.static_mesh_component, "cast_shadow", False)
        spawned.append(actor)
        placed.append((entry, actor))
        if entry["kind"] != "surface":
            continue
        surface_actors[entry["id"]] = actor
        for definition in scene.get("variants", []):
            finish_id = resolve_finish(definition, entry["role"], entry["room_id"])
            if finish_id and (definition["id"], finish_id) in instances:
                by_variant[definition["id"]][entry["id"]] = \
                    instances[(definition["id"], finish_id)]
        start_material = by_variant.get(default_variant, {}).get(entry["id"])
        if start_material is not None:
            actor.static_mesh_component.set_material(0, start_material)

    step("aktorzy", ustawionych=len(spawned), powierzchni=len(surface_actors),
         brak_zasobu=missing[:10], brak_kolizji=len(no_collision))
    if missing:
        problem("Brak zasobu dla {} siatek z manifestu".format(len(missing)))

    spawn_lights(spawned, scene)
    start = spawn_player_start(scene)
    if start is None:
        problem("Nie ustawiono punktu startowego - scena nie ma pomieszczen")

    build_variants(scene, surface_actors, by_variant)
    verify(manifest, placed, surface_actors, by_variant)

    unreal.EditorAssetLibrary.save_directory(ROOT, only_if_is_dirty=False,
                                             recursive=True)
    level.save_current_level()
    step("zapis", poziom=LEVEL_PATH)

    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    unreal.log("[Room] raport: {}".format(report_path))


def expected_box(low_m, high_m):
    """Bryla z Blendera po odbiciu osi Y, w centymetrach."""
    return ([low_m[0] * M_TO_UU, -high_m[1] * M_TO_UU, low_m[2] * M_TO_UU],
            [high_m[0] * M_TO_UU, -low_m[1] * M_TO_UU, high_m[2] * M_TO_UU])


def verify(manifest, placed, surface_actors, by_variant):
    """Sprawdzenie, czy kazdy obiekt stanal tam, gdzie mial.

    Porownanie idzie obiekt po obiekcie, nie tylko po calej scenie. Zgodna
    bryla calosci potrafi ukryc dwa bledy, ktore sie znosza - np. mebel
    obrocony w zla strone wewnatrz poprawnego obrysu domu.
    """
    if not placed:
        problem("Nie ustawiono zadnego obiektu - nie ma czego sprawdzac")
        return
    worst = []
    total_low = [None, None, None]
    total_high = [None, None, None]
    for entry, actor in placed:
        origin, extent = actor.get_actor_bounds(False)
        low = [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z]
        high = [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]
        for axis in range(3):
            total_low[axis] = low[axis] if total_low[axis] is None \
                else min(total_low[axis], low[axis])
            total_high[axis] = high[axis] if total_high[axis] is None \
                else max(total_high[axis], high[axis])
        want_low, want_high = expected_box(entry["bounds_min_m"], entry["bounds_max_m"])
        error = max(max(abs(low[a] - want_low[a]), abs(high[a] - want_high[a]))
                    for a in range(3))
        worst.append((round(error, 2), entry["id"], entry["blender_name"],
                      [[round(v, 1) for v in low], [round(v, 1) for v in high]],
                      [[round(v, 1) for v in want_low], [round(v, 1) for v in want_high]]))

    worst.sort(key=lambda item: item[0], reverse=True)
    powyzej_1cm = sum(1 for e in worst if e[0] > 1.0)
    scene_low, scene_high = expected_box(manifest["bounds_min_m"],
                                         manifest["bounds_max_m"])
    scene_error = round(max(max(abs(total_low[a] - scene_low[a]),
                                abs(total_high[a] - scene_high[a]))
                            for a in range(3)), 2)
    step("polozenie",
         najgorsze_cm=[{"blad_cm": w[0], "id": w[1], "obiekt": w[2],
                        "w_unrealu": w[3], "oczekiwane": w[4]} for w in worst[:6]],
         obiektow_powyzej_1cm=powyzej_1cm,
         bryla_sceny_blad_cm=scene_error,
         bryla_w_unrealu=[[round(v, 1) for v in total_low],
                          [round(v, 1) for v in total_high]])
    if powyzej_1cm:
        problem("{} obiektow stoi inaczej niz w eksporcie (najgorszy {} cm, {})"
                .format(powyzej_1cm, worst[0][0], worst[0][2]))

    roles = {}
    for entry in manifest["meshes"]:
        roles[entry["role"]] = roles.get(entry["role"], 0) + 1
    pokrycie = {vid: len(mapping) for vid, mapping in by_variant.items()}
    rozne = 0
    ids = list(by_variant.keys())
    if len(ids) >= 2:
        first, second = by_variant[ids[0]], by_variant[ids[1]]
        for key in surface_actors:
            if first.get(key) is not second.get(key):
                rozne += 1
    step("pokrycie", role=roles, materialy_na_wariant=pokrycie,
         powierzchnie_rozne_miedzy_wariantami=rozne)
    if rozne == 0:
        problem("Warianty nie roznia sie zadna powierzchnia")
    braki = [key for key in surface_actors
             if any(key not in mapping for mapping in by_variant.values())]
    if braki:
        problem("{} powierzchni bez materialu w ktoryms wariancie "
                "(np. {})".format(len(braki), braki[:5]))


main()
