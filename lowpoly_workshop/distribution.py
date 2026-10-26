"""Self-contained archives with relative checksums and explicit provenance."""
from pathlib import Path
import hashlib,json,zipfile
from .spec import read_spec
from . import __version__
from .kit.atomic import replacing

def add_tree(z,base,prefix,exclude=()):
    manifest={}
    for p in sorted(Path(base).rglob("*")):
        rel=p.relative_to(base)
        if not p.is_file() or any(rel==Path(e) or Path(e) in rel.parents for e in exclude) or any(x in ("__pycache__",".git",".venv",".workshop","node_modules") for x in rel.parts) or p.suffix in (".pyc",".blend1") or p.name.startswith(".env") or p.name.endswith(".egg-info") or any(x.endswith(".egg-info") for x in rel.parts) or p.suffix in (".pem",".key"):
            continue
        resolved=p.resolve()
        if not resolved.is_relative_to(Path(base).resolve()):raise ValueError(f"External symlink: {rel}")
        name=(Path(prefix)/rel).as_posix();data=p.read_bytes();z.writestr(name,data);manifest[name]=hashlib.sha256(data).hexdigest()
    return manifest

def package_asset(folder):
    folder=Path(folder).resolve();spec=read_spec(folder)
    out=folder/spec.get("out_dir","out");out.mkdir(parents=True,exist_ok=True)
    path=out/(spec["name"]+"_package.zip")
    from .approval import status
    with replacing(str(path)) as temporary, zipfile.ZipFile(temporary,"w",zipfile.ZIP_DEFLATED) as z:
        hashes=add_tree(z,folder,"project",exclude=(spec.get("out_dir","out"),))
        hashes.update(add_tree(z,Path(__file__).parent,"toolkit/lowpoly_workshop"))
        # Only declared deliverables/review evidence; never recursively include previous archives.
        for p in out.rglob("*"):
            if p.is_file() and p.suffix.lower() not in (".zip",".blend1") and ".workshop" not in p.parts and not p.name.startswith(".env") and p.suffix not in (".pem",".key"):
                if not p.resolve().is_relative_to(folder):raise ValueError("External output symlink")
                name="project/"+p.relative_to(folder).as_posix();z.write(p,name);hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
        for notice in ("LICENSE","THIRD_PARTY_NOTICES.md","PROVENANCE.json"):
            source=Path(__file__).parent/"notices"/notice
            if source.exists():
                name="toolkit/"+notice;data=source.read_bytes();z.writestr(name,data);hashes[name]=hashlib.sha256(data).hexdigest()
        z.writestr("rebuild.py","from pathlib import Path\nimport sys\nr=Path(__file__).resolve().parent\nsys.path.insert(0,str(r/'toolkit'))\nfrom lowpoly_workshop.cli import main\nmain([str(r/'project'),'all'])\n")
        z.writestr("README.txt","Install Python dependencies numpy scipy Pillow opencv-python-headless; set KIT_BLENDER; run python rebuild.py.\nGenerators execute Python. Review their code before running. See toolkit/lowpoly_workshop/SKILL.md.\n")
        for name in ("rebuild.py","README.txt"):
            hashes[name]=hashlib.sha256(z.read(name)).hexdigest()
        z.writestr("manifest.json",json.dumps({"version":__version__,"files":hashes,"references":spec.get("references",[]),"visual_approval":status(folder)},indent=2))
    print("PACKAGE",path)
    return path

def release(destination):
    root=Path(__file__).resolve().parent.parent
    if not (root/"pyproject.toml").exists():raise ValueError("Source releases require a source checkout")
    path=Path(destination).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_relative_to(root):raise ValueError("Write source release outside the package tree")
    with replacing(str(path)) as temporary, zipfile.ZipFile(temporary,"w",zipfile.ZIP_DEFLATED) as z:
        hashes=add_tree(z,root,"Lowpoly-Workshop",exclude=("dist","build",".egg-info","out",".runtime","work",".pytest_cache","node_modules"))
        z.writestr("Lowpoly-Workshop/RELEASE-MANIFEST.json",json.dumps({"version":__version__,"files":hashes},indent=2))
    path.with_suffix(path.suffix+".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest()+"  "+path.name+"\n")
    print("RELEASE",path)
    return path
