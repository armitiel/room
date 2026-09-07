"""Wypisuje sygnatury funkcji Variant Managera w tym silniku."""

import json
import os

import unreal

lib = unreal.VariantManagerLibrary
out = {}
for name in ("get_capturable_properties", "capture_property", "add_actor_binding",
             "add_variant", "add_variant_set", "create_level_variant_sets_asset",
             "create_level_variant_sets_actor", "set_value_object", "record",
             "get_captured_properties", "get_property_type_string"):
    fn = getattr(lib, name, None)
    out[name] = (fn.__doc__ or "").strip().splitlines()[:4] if fn else None

out["PropertyValue"] = sorted(m for m in dir(unreal.PropertyValue)
                              if not m.startswith("_")) \
    if hasattr(unreal, "PropertyValue") else None
out["LevelVariantSetsActor"] = sorted(
    m for m in dir(unreal.LevelVariantSetsActor) if not m.startswith("_"))

target = os.path.normpath(os.path.join(
    unreal.Paths.project_dir(), "..", "..", "work", "unreal", "probe-variant.json"))
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=1)
