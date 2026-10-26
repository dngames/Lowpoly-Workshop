"""Command-line frontend. AI agents and artists use the same portable pipeline."""
import argparse,json,os,sys,subprocess
from pathlib import Path
from . import __version__
from .spec import KINDS,read_spec

def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    try:return dispatch(args)
    except (ValueError,FileNotFoundError,KeyError) as e:
        print("ERROR:",e,file=sys.stderr);raise SystemExit(2)

def dispatch(args):
    if not args or args[0] in ("-h","--help"):
        print("""Lowpoly Workshop
  lowpoly new FOLDER --kind static-prop|hollow-prop|wearable|articulated|character [--guided]
  lowpoly doctor
  lowpoly selftest [--blender]
  lowpoly release DESTINATION.zip
  lowpoly serve FOLDER [--port 8000]
  lowpoly ASSET build [--force]
  lowpoly ASSET check | review | skin | all | page | package | inspect
  lowpoly ASSET features list
  lowpoly ASSET features review ID --decision accepted|repair|waived --note NOTE
  lowpoly ASSET workflow status | next
  lowpoly ASSET workflow accept STAGE --note NOTE [--evidence out/pose.png]
  lowpoly ASSET references plan [--views front back ...]
  lowpoly ASSET references run --model MODEL [--max-jobs 1]
  lowpoly ASSET references import JOB_ID IMAGE
  lowpoly ASSET coverage [SET] [--size 256] [--budget 4]
  lowpoly ASSET paint | pieces | shell-lods
  lowpoly ASSET fit all --grid | render views | render show | compose
""");return
    if args[0]=="--version":print(__version__);return
    if args[0]=="new":
        from .templates import create
        parser=argparse.ArgumentParser();parser.add_argument("folder");parser.add_argument("--kind",choices=KINDS,default="static-prop");parser.add_argument("--title",default=None);parser.add_argument("--guided",action="store_true")
        ns=parser.parse_args(args[1:]);create(ns.folder,ns.kind,ns.title,guided=ns.guided);return
    if args[0]=="release":
        from .distribution import release
        if len(args)!=2:raise ValueError("release needs destination.zip")
        release(args[1]);return
    if args[0]=="doctor":
        from .pipeline import find_blender
        import numpy,scipy,PIL,cv2
        print("Python",sys.version.split()[0],"Workshop",__version__)
        print("Blender",find_blender());return
    if args[0]=="selftest":
        from .selftest import run
        raise SystemExit(run("--blender" in args))
    if args[0]=="serve":
        parser=argparse.ArgumentParser();parser.add_argument("folder");parser.add_argument("--port",type=int,default=8000)
        ns=parser.parse_args(args[1:])
        subprocess.run([sys.executable,"-m","http.server",str(ns.port),"--bind","127.0.0.1","--directory",str(Path(ns.folder).resolve())],check=True);return
    if args[0]=="sheets":
        from .kit.sheets import main as sheets
        sheets(args[1:]);return
    if len(args)<2:raise ValueError("Expected asset folder and command")
    folder=str(Path(args[0]).resolve());command=args[1]
    spec=read_spec(folder)
    if command in ("features", "workflow"):
        from . import workflow
        action = args[2] if len(args) > 2 else ("list" if command == "features" else "status")
        if command == "features" and action == "list":
            print(json.dumps(workflow.status(folder)["features"], indent=2));return
        if command == "workflow" and action in ("status", "next"):
            state = workflow.status(folder)
            print(json.dumps(state if action == "status" else {k: state[k] for k in ("status", "current_stage", "next_action", "next_command")}, indent=2));return
        parser = argparse.ArgumentParser()
        parser.add_argument("id");parser.add_argument("--note",required=True)
        if command == "features" and action == "review":
            parser.add_argument("--decision",required=True,choices=("accepted","repair","waived"))
            ns=parser.parse_args(args[3:]);result=workflow.review_feature(folder,ns.id,ns.decision,ns.note)
        elif command == "workflow" and action == "accept":
            parser.add_argument("--evidence",nargs="*",default=[])
            ns=parser.parse_args(args[3:]);result=workflow.accept_stage(folder,ns.id,ns.note,ns.evidence)
        else:raise ValueError("Unknown guided review action")
        print(json.dumps(result,indent=2));return
    if command=="approve":
        from .approval import record
        parser=argparse.ArgumentParser();parser.add_argument('--note',required=True)
        ns=parser.parse_args(args[2:]);print(json.dumps(record(folder,ns.note),indent=2));return
    if command=="references":
        from . import references as refs
        action=args[2] if len(args)>2 else "plan"
        if action=="plan":
            views=args[args.index("--views")+1:] if "--views" in args else None
            path,jobs=refs.plan(folder,views);print(path,len(jobs),"missing views");return
        if action=="run":
            parser=argparse.ArgumentParser();parser.add_argument("--model",default=os.environ.get("LOWPOLY_IMAGE_MODEL"));parser.add_argument("--max-jobs",type=int,default=1)
            ns=parser.parse_args(args[3:])
            for p in refs.run(folder,ns.model,ns.max_jobs):print(p)
            return
        if action=="import":
            if len(args)!=5:raise ValueError("references import JOB_ID IMAGE")
            jobs=json.loads((Path(folder)/spec.get("out_dir","out")/"reference-jobs.json").read_text())["jobs"]
            job=next((j for j in jobs if j["id"]==args[3]),None)
            if not job:raise ValueError("Unknown planned job")
            print(refs.register(folder,job,args[4],"external-image-provider"));return
        raise ValueError("Unknown references action")
    from . import pipeline
    if command=="build":
        from .runner import build
        build(folder,"--force" in args);return
    if command == "coverage":
        from .kit import coverage
        parser = argparse.ArgumentParser(description="Geometric camera coverage; does not paint or approve")
        parser.add_argument("set", nargs="?")
        parser.add_argument("--size", type=int, default=256)
        parser.add_argument("--budget", type=int, default=4)
        ns = parser.parse_args(args[2:])
        coverage.run(folder, ns.set, ns.size, ns.budget);return
    if command == "paint":
        from .kit.paintcheck import run
        run(folder);return
    if command == "pieces":
        from .kit.pieces import run
        from .kit.asset import Asset
        run(Asset(folder));return
    if command=="inspect":
        from .kit.asset import Asset
        from .kit.mesh import triangles
        from .quality import topology,uv_diagnostics
        a=Asset(folder);nodes=a.build(spec.get("review",{}).get("variant"))
        print(json.dumps({"nodes":{n:topology(triangles({n:nd})[0]) for n,nd in nodes.items() if nd["faces"]},"uv":uv_diagnostics(nodes,a.gen.ATLAS)},indent=2));return
    if command=="shell-lods":pipeline.blender("shell_lods.py",folder);return
    if command=="review":pipeline.blender("review.py",folder);return
    if command=="skin":pipeline.blender("skin_export.py",folder);return
    if command=="all":
        from .runner import build
        from .kit import check,compose,page
        from .distribution import package_asset
        build(folder,"--force" in args)
        okay=check.run(folder)
        if spec.get("sets"):
            pipeline.blender("render.py",folder,"views");compose.run(folder)
        pipeline.blender("render.py",folder,"show")
        pipeline.blender("review.py",folder)
        page.build_page(folder,str(Path(pipeline.__file__).parent))
        package_asset(folder)
        raise SystemExit(0 if okay else 1)
    if command not in ("check","render","fit","refine","compose","page","package"):
        raise ValueError("Unknown asset command: "+command)
    old=sys.argv
    try:sys.argv=[pipeline.__file__,folder,command,*args[2:]];pipeline.main()
    finally:sys.argv=old
