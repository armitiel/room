"""Build the main local demo: Blender -> glTF + scene metadata -> offline HTML.

Run with Python. Pass --blender if Blender is not on PATH or in the default
Windows installation. The source stays draft; this command creates a preview.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', default=shutil.which('blender') or
                        r'C:\Program Files\Blender Foundation\Blender 4.3\blender.exe')
    args = parser.parse_args()
    source = ROOT/'datasets/sample/kruszczyki-22/scene.json'
    catalog = ROOT/'catalog/products.json'
    folder = ROOT/'work/scenes/showcase'
    folder.mkdir(parents=True, exist_ok=True)
    before = {str(path.relative_to(ROOT)): digest(path) for path in [source,catalog]}
    if not Path(args.blender).is_file():
        parser.error('Blender not found; specify --blender with its executable path.')
    commands = [
        [args.blender,'--background','--factory-startup','--python-exit-code','1',
         '--python','blender/scripts/build_scene.py','--','--scene',str(source),
         '--allow-unapproved','--ceiling','--out',str(folder/'main.blend')],
        [args.blender,'--background','--factory-startup',str(folder/'main.blend'),
         '--python-exit-code','1','--python','blender/scripts/export_scene.py','--',
         '--format','glb','--units','m','--out',str(folder/'main.glb')],
    ]
    for index, command in enumerate(commands):
        log = folder/f'build-step-{index+1}.log'
        with log.open('w',encoding='utf-8') as output:
            result = subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
        if result.returncode:
            raise SystemExit(f'Build failed; see {log}')
    after = {str(path.relative_to(ROOT)): digest(path) for path in [source,catalog]}
    if before != after:
        raise SystemExit('Scene/catalog changed during build; preview was not replaced. Run again.')
    # Assemble the standalone file in the work directory first. Only publish local
    # artifacts after every build stage succeeds.
    subprocess.run([sys.executable,str(ROOT/'web/tools/build_standalone.py'),
                    '--model',str(folder/'main.glb'),'--scene',str(source),
                    '--out',str(folder/'standalone.html')],cwd=ROOT,check=True)
    shutil.copy2(source, ROOT/'web/scene.json')
    shutil.copy2(folder/'main.glb', ROOT/'web/assets/room.glb')
    shutil.copy2(folder/'standalone.html', ROOT/'web/standalone.html')
    manifest = {'built_at':datetime.now(timezone.utc).isoformat(),'source_sha256':before,
                'preview_only':True,'furniture_count':len(json.loads(source.read_text(encoding='utf-8'))['furniture']),
                'artifacts':{str(p.relative_to(ROOT)):digest(p) for p in
                             [ROOT/'web/assets/room.glb',ROOT/'web/scene.json',ROOT/'web/standalone.html']}}
    (ROOT/'web/build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('Ready: web/standalone.html (local preview)')


if __name__ == '__main__':
    main()
