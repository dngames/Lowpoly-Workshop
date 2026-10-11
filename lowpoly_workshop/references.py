"""Optional reference completion. Original images are immutable; every invented view is recorded."""
from pathlib import Path
import base64,hashlib,json,mimetypes,os,urllib.request,uuid
from .spec import read_spec,local_path

VIEWS={"front":[0,0],"back":[180,0],"left":[-90,0],"right":[90,0],"top":[0,85],"bottom":[0,-85]}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def plan(folder,views=None):
    folder=Path(folder).resolve();spec=read_spec(folder)
    refs=spec.get("references",[])
    originals=[r for r in refs if r["source"]=="original"]
    if not originals:raise ValueError("Register at least one original in asset.json references")
    supplied={r.get("view") for r in refs}
    wanted=views or spec.get("reference_completion",{}).get("views",list(VIEWS))
    if any(v not in VIEWS for v in wanted):raise ValueError("Unknown reference view")
    jobs=[]
    for view in wanted:
        if view in supplied:continue
        jobs.append({"id":view,"view":view,"output":f"ref/generated/{view}.png",
            "inputs":[{"path":r["path"],"sha256":digest(local_path(folder,r["path"]))} for r in originals],
            "prompt":f"Create one clean {view} orthographic design reference of {spec.get('title',spec['name'])}. "
                "Preserve the supplied object's identity, proportions, palette, style and distinctive details. "
                "Invent plausible unseen geometry consistent with all supplied images. Show only this object, "
                "entirely in frame with margin on a plain light background, no labels, text, shadows or extra objects. "
                "This is an inferred design view, not a recovered photograph. "+spec.get("reference_completion",{}).get("notes","")})
    path=local_path(folder,spec.get("out_dir","out")+"/reference-jobs.json");path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"version":1,"jobs":jobs},indent=2),encoding="utf-8")
    return path,jobs

def openai_edit(inputs,prompt,model,api_key,request=None):
    """Images edit API using standard-library multipart HTTP; no SDK or hidden subprocess."""
    boundary="workshop-"+uuid.uuid4().hex;chunks=[]
    def field(name,value):
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    for name,value in (("model",model),("prompt",prompt),("n","1"),("output_format","png")):field(name,value)
    for i,path in enumerate(inputs):
        path=Path(path);mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image[]\"; filename=\"reference-{i}{path.suffix}\"\r\nContent-Type: {mime}\r\n\r\n".encode()+path.read_bytes()+b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    req=urllib.request.Request("https://api.openai.com/v1/images/edits",data=b"".join(chunks),
        headers={"Authorization":"Bearer "+api_key,"Content-Type":"multipart/form-data; boundary="+boundary})
    with (request or urllib.request.urlopen)(req,timeout=240) as response:payload=json.load(response)
    return base64.b64decode(payload["data"][0]["b64_json"],validate=True)

def register(folder,job,image,provider,model=None):
    from PIL import Image
    folder=Path(folder).resolve();spec=read_spec(folder)
    refs=spec.setdefault("references",[])
    for inp in job["inputs"]:
        if digest(local_path(folder,inp["path"]))!=inp["sha256"]:
            raise ValueError("Original reference changed after planning")
    if any(r.get("view")==job["view"] for r in refs):
        raise ValueError("This view already has a registered reference")
    target=local_path(folder,job["output"]);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError(f"Refusing to overwrite {target.name}")
    image_path=Path(image) if isinstance(image,(str,Path)) else None
    import io
    stream=image_path if image_path else io.BytesIO(image)
    with Image.open(stream) as im:im.convert("RGB").save(target,format="PNG")
    refs.append({"path":job["output"],"source":"generated","view":job["view"],"provider":provider,"model":model,
        "prompt":job["prompt"],"input_sha256":[i["sha256"] for i in job["inputs"]],"sha256":digest(target),
        "review_status":"pending","inferred":True})
    (folder/"asset.json").write_text(json.dumps(spec,indent=2)+"\n",encoding="utf-8")
    return target

def run(folder,model,max_jobs=1):
    key=os.environ.get("OPENAI_API_KEY")
    if not key:raise ValueError("Set OPENAI_API_KEY locally; never put it in asset.json")
    if not model:raise ValueError("Choose --model explicitly or set LOWPOLY_IMAGE_MODEL")
    if max_jobs<1 or max_jobs>24:raise ValueError("max-jobs must be between 1 and 24")
    _,jobs=plan(folder)
    output=[]
    for job in jobs[:max_jobs]:
        inputs=[local_path(folder,i["path"]) for i in job["inputs"]]
        image=openai_edit(inputs,job["prompt"],model,key)
        output.append(register(folder,job,image,"openai-images",model))
    return output
