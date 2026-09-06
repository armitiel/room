"""Wczytywanie i zapis danych projektu: scene.json oraz katalog produktow.

Modul odpowiada wylacznie za wejscie/wyjscie i lokalizacje plikow.
Regul walidacji tutaj nie ma - te sa w roomlib.validate.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


class SceneIOError(Exception):
    """Blad odczytu lub zapisu danych projektu."""


def repo_root(start: Optional[str] = None) -> str:
    """Znajduje katalog glowny repozytorium po obecnosci katalogu docs/.

    Skrypty Blendera uruchamiane sa z roznych katalogow roboczych,
    wiec sciezek nie zgadujemy wzgledem cwd.
    """
    here = os.path.abspath(start or __file__)
    if os.path.isfile(here):
        here = os.path.dirname(here)
    current = here
    while True:
        if os.path.isdir(os.path.join(current, "docs")) and os.path.isfile(
            os.path.join(current, "README.md")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            raise SceneIOError(
                "Nie znaleziono katalogu glownego repozytorium (szukano docs/ i README.md)."
            )
        current = parent


def read_json(path: str) -> Any:
    if not os.path.isfile(path):
        raise SceneIOError("Plik nie istnieje: {}".format(path))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise SceneIOError("Niepoprawny JSON w {}: {}".format(path, exc)) from exc


def write_json(path: str, data: Any) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_scene(path: str) -> Dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise SceneIOError("scene.json musi byc obiektem JSON, otrzymano {}".format(type(data).__name__))
    return data


def default_catalog_path(root: Optional[str] = None) -> str:
    return os.path.join(root or repo_root(), "catalog", "products.json")


def load_catalog(path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Zwraca produkty jako slownik product_id -> wpis.

    Brak pliku katalogu nie jest bledem odczytu: pusty katalog to
    poprawny stan projektu przed pozyskaniem licencji. Walidator
    zglosi problem dopiero wtedy, gdy scena odwoluje sie do produktu.
    """
    catalog_path = path or default_catalog_path()
    if not os.path.isfile(catalog_path):
        return {}
    data = read_json(catalog_path)
    if not isinstance(data, dict):
        raise SceneIOError("catalog/products.json musi byc obiektem JSON.")
    products = data.get("products", [])
    if not isinstance(products, list):
        raise SceneIOError("Pole 'products' w katalogu musi byc lista.")
    result: Dict[str, Dict[str, Any]] = {}
    for entry in products:
        if isinstance(entry, dict) and isinstance(entry.get("product_id"), str):
            result[entry["product_id"]] = entry
    return result


def duplicate_product_ids(path: Optional[str] = None) -> List[str]:
    """Identyfikatory produktow powtorzone w katalogu."""
    catalog_path = path or default_catalog_path()
    if not os.path.isfile(catalog_path):
        return []
    data = read_json(catalog_path)
    seen: Dict[str, int] = {}
    for entry in data.get("products", []) if isinstance(data, dict) else []:
        if isinstance(entry, dict):
            pid = entry.get("product_id")
            if isinstance(pid, str):
                seen[pid] = seen.get(pid, 0) + 1
    return sorted(pid for pid, count in seen.items() if count > 1)


def resolve_model_path(entry: Dict[str, Any], root: Optional[str] = None) -> Optional[str]:
    """Bezwzgledna sciezka pliku modelu produktu, jesli wpis ja podaje."""
    model_path = entry.get("model_path")
    if not isinstance(model_path, str) or not model_path.strip():
        return None
    if os.path.isabs(model_path):
        return model_path
    return os.path.join(root or repo_root(), model_path)


def work_dir(scene_id: str, root: Optional[str] = None) -> str:
    """Katalog na wyniki robocze danej sceny. work/ jest poza repozytorium."""
    path = os.path.join(root or repo_root(), "work", "scenes", scene_id)
    os.makedirs(path, exist_ok=True)
    return path
