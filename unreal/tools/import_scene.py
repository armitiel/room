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
P_MAPS = ROOT + "/Maps"
LEVEL_PATH = P_MAPS + "/L_Room"

M_TO_UU = 100.0
SURFACE_ROLES = ("floor", "wall", "ceiling", "frame_window", "frame_door",
                 "glass", "leaf")

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

    color = lib.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, -520, -100)
    color.set_editor_property("parameter_name", "BaseColor")
    color.set_editor_property("default_value",
                              unreal.LinearColor(0.75, 0.74, 0.72, 1.0))
    lib.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)

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


def finish_instance(variant_id, finish_id, finish, opaque, glass):
    name = "MI_{}_{}".format(variant_id, finish_id).replace("-", "_")
    full = "{}/{}".format(P_MATERIALS, name)
    existed = unreal.EditorAssetLibrary.does_asset_exist(full)
    instance = _create(name, P_MATERIALS, unreal.MaterialInstanceConstant,
                       unreal.MaterialInstanceConstantFactoryNew())
    lib = unreal.MaterialEditingLibrary
    has_opacity = "opacity" in finish
    if not existed:
        lib.set_material_instance_parent(instance, glass if has_opacity else opaque)
    lib.set_material_instance_vector_parameter_value(
        instance, "BaseColor", hex_to_linear(finish.get("color", "#cccccc")))
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


def spawn_lights(actors, scene):
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    sun = editor.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0, 0, 900),
        unreal.Rotator(0, -42, -140))
    sun.set_actor_label("Slonce")
    sun.light_component.set_editor_property("intensity", 6.0)
    sun.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
    actors.append(sun)

    sky = editor.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 900))
    sky.set_actor_label("Niebo")
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_editor_property("intensity", 1.0)
    sky.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
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
        lamp = editor.spawn_actor_from_class(
            unreal.PointLight, plan_to_ue(cx, cy, height - 0.35))
        lamp.set_actor_label("Lampa {}".format(room.get("id", "?")))
        component = lamp.point_light_component
        component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        component.set_editor_property("intensity", 900.0)
        component.set_editor_property("attenuation_radius", 600.0)
        component.set_editor_property("source_radius", 12.0)
        component.set_editor_property("cast_shadows", True)
        actors.append(lamp)

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
        ("auto_exposure_min_brightness", 0.05),
        ("auto_exposure_max_brightness", 8.0),
        ("auto_exposure_speed_up", 4.0),
        ("auto_exposure_speed_down", 4.0),
        ("auto_exposure_bias", 0.0),
    ):
        settings.set_editor_property("override_" + nazwa, True)
        settings.set_editor_property(nazwa, wartosc)
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

    import_fbx(manifest["fbx"])
    meshes = index_meshes([entry["id"] for entry in manifest["meshes"]])
    wzorzec = next((e for e in manifest["meshes"] if e["id"] in meshes), None)
    sprawdzian = (meshes[wzorzec["id"]],
                  [wzorzec["local_max_m"][a] - wzorzec["local_min_m"][a]
                   for a in range(3)]) if wzorzec else (None, [0, 0, 0])
    w_siatkach = bool(wzorzec) and scale_meshes_to_cm(list(meshes.values()),
                                                      sprawdzian)
    scale_factor = 1.0 if w_siatkach else M_TO_UU
    step("skala", w_siatkach=w_siatkach, mnoznik_aktora=scale_factor)

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
    instances = {}
    for definition in scene.get("variants", []):
        for finish_id, finish in finishes.items():
            instances[(definition["id"], finish_id)] = finish_instance(
                definition["id"], finish_id, finish, opaque, glass)
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
