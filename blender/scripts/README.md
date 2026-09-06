# Blender/Python
Planowane skrypty: validate_scene.py, build_scene.py, export_scene.py.
Wejście: zatwierdzony scene.json i katalog modeli. Wyjście: work/scenes/<scene_id>/.
Generator powinien być powtarzalny, zachowywać identyfikatory obiektów i nie pobierać losowych modeli z sieci.
Przyszłe uruchomienie: blender --background --python-exit-code 1 --python blender/scripts/build_scene.py -- --scene <plik>
Komenda jest kontraktem planowanego skryptu; skrypt nie jest jeszcze zaimplementowany.