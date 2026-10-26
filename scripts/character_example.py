"""Create and verify an original, editable trail-guide character tutorial."""
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
    folder=create(destination,'character','Trail guide character example')
    example=Path(__file__).resolve().parents[1]/'lowpoly_workshop/assets/examples/trail-guide'
    for name in ('gen.py','asset.json'):
        shutil.copyfile(example/name,folder/name)
    return folder


def run(destination, build=True):
    folder=create_project(destination)
    if not build:return folder
    for command in ('build','check','review','page','package'):
        subprocess.run([sys.executable,'-m','lowpoly_workshop',str(folder),command],check=True)
    model=folder/'out/guide.glb';index=json.loads((folder/'out/review/index.json').read_text())
    sha=hashlib.sha256(model.read_bytes()).hexdigest()
    assert all(s['sha256']==sha for s in index['shots'])
    print('CHARACTER EXAMPLE',folder)
    return folder


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination');parser.add_argument('--source-only',action='store_true')
    args=parser.parse_args();run(args.destination,not args.source_only)
