"""Create and verify Tiny Tour's editable Station Rest House example."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lowpoly_workshop.templates import create


def create_project(destination):
    folder=create(destination,'static-prop','Tiny Tour Station Rest House')
    source=Path(__file__).resolve().parents[1]/'lowpoly_workshop/assets/examples/station-rest-house'
    for name in ('gen.py','asset.json','provenance.json','README.md'):
        shutil.copyfile(source/name,folder/name)
    shutil.copytree(source/'inputs',folder/'inputs',dirs_exist_ok=True)
    return folder


def run(destination,build=True):
    folder=create_project(destination)
    if not build:return folder
    for command in ('build','check','review','page','package'):
        subprocess.run([sys.executable,'-m','lowpoly_workshop',str(folder),command],check=True)
    index=json.loads((folder/'out/review/index.json').read_text())
    for shot in index['shots']:
        assert shot['sha256']==hashlib.sha256((folder/shot['output']).read_bytes()).hexdigest()
    print('BUILDING EXAMPLE',folder)
    return folder


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination');p.add_argument('--source-only',action='store_true')
    a=p.parse_args();run(a.destination,not a.source_only)
