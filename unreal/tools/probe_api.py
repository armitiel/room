"""Sprawdza, co API Pythona w tym konkretnym silniku naprawde udostepnia.

Uruchamiane raz, przed napisaniem importera. Nie zaklada niczego z
dokumentacji innej wersji Unreala - zapisuje stan tego, co jest na dysku.
Wynik trafia do pliku, bo print z komandletu nie zawsze dociera do stdout.
"""

import json
import os

import unreal

WANTED = [
    "AssetToolsHelpers", "EditorAssetLibrary", "EditorLevelLibrary",
    "LevelEditorSubsystem", "EditorActorSubsystem", "AssetImportTask",
    "FbxImportUI", "FbxStaticMeshImportData", "FbxSceneImportFactory",
    "InterchangeAssetImportData", "MaterialEditingLibrary",
    "MaterialInstanceConstantFactoryNew", "MaterialFactoryNew",
    "VariantManagerLibrary", "LevelVariantSets", "LevelVariantSetsActor",
    "LevelVariantSetsFunctionDirector", "VariantSet", "Variant",
    "PropertyValueMaterial", "StaticMeshActor", "DirectionalLight",
    "SkyLight", "SkyAtmosphere", "PlayerStart", "PostProcessVolume",
    "ExponentialHeightFog", "StaticMeshEditorSubsystem",
    "InterchangeManager", "ImportAssetParameters",
]

out = {
    "engine": unreal.SystemLibrary.get_engine_version(),
    "present": {name: hasattr(unreal, name) for name in WANTED},
    "members": {},
}

for holder in ("VariantManagerLibrary", "Variant", "VariantSet",
               "LevelVariantSets", "PropertyValueMaterial",
               "LevelEditorSubsystem", "AssetImportTask"):
    if hasattr(unreal, holder):
        out["members"][holder] = sorted(
            m for m in dir(getattr(unreal, holder)) if not m.startswith("_")
        )

target = os.path.join(
    unreal.Paths.project_dir(), "..", "..", "work", "unreal", "probe.json"
)
target = os.path.normpath(target)
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=1)
unreal.log("PROBE zapisany do {}".format(target))
