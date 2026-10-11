"""Content-based build cache; a changed generator, reference, profile or tool invalidates it."""
from pathlib import Path
import hashlib,json
from . import __version__
from .spec import read_spec

def fingerprint(folder):
    folder=Path(folder).resolve();spec=read_spec(folder);h=hashlib.sha256(__version__.encode())
    excluded={spec.get("out_dir","out"),"__pycache__",".git",".workshop"}
    for base in (folder,Path(__file__).parent):
        for p in sorted(base.rglob("*")):
            if not p.is_file() or (base==folder and (p.is_relative_to(folder/spec.get("out_dir","out")))) or any(part in excluded for part in p.relative_to(base).parts) or p.suffix in (".pyc",".blend1"):
                continue
            # Package data and runtime code participate, except generated application caches.
            h.update(p.relative_to(base).as_posix().encode());h.update(p.read_bytes())
    return h.hexdigest()

def build(folder,force=False):
    from .pipeline import blender,find_blender
    folder=Path(folder).resolve();spec=read_spec(folder)
    stamp=folder/".workshop/build.json"
    exe=Path(find_blender())
    source_key=fingerprint(folder)
    key=source_key+str(exe.stat().st_mtime_ns)
    old=json.loads(stamp.read_text()) if stamp.exists() else {}
    outputs=[folder/o["file"] for o in spec["outputs"]]
    expected={}
    companions=[p.with_suffix(".blend") for p in outputs]
    for o,p in zip(spec["outputs"],outputs):
        companions.append(p.with_name(p.stem+"_atlas.png"))
        if o.get("kit_mask"):companions.append(p.parent/o["kit_mask"])
    all_files=outputs+companions
    expected={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files if p.exists()}
    if not force and old.get("key")==key and old.get("source")==source_key and len(expected)==len(all_files) and old.get("outputs")==expected and all(p.exists() for p in companions):
        print("BUILD cached; source and output hashes match")
        return False
    blender("build.py",folder)
    stamp.parent.mkdir(exist_ok=True)
    expected={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in all_files}
    if fingerprint(folder)!=source_key:raise ValueError("Source changed during build; rebuild before review")
    stamp.write_text(json.dumps({"key":key,"source":source_key,"outputs":expected},indent=2))
    return True
