"""Hyper3D Rodin image-to-3D through fal.ai's queue API: an optional hosted alternative to `pixal3d run`.

One `run` is one paid generation. It uploads the RGBA cutouts written by `pixal3d prep` to fal's CDN (or
sends them inline as data URIs, or passes hosted `--image-url`s), submits them to
`https://queue.fal.run/<endpoint>`, waits for the job, downloads the
returned `model_mesh` GLB to `inputs/rodin_raw.glb` and records the request in `inputs/rodin_meta.json`.
A submitted but unfinished job is kept in `inputs/rodin_pending.json`, so a timed-out or interrupted run
resumes the same paid request instead of submitting another. Standard-library HTTP only; no SDK.
"""
from pathlib import Path
import base64
import datetime
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from .spec import local_path
from .kit.atomic import replacing, write_json
from .kit.glb import load_glb

QUEUE_URL = "https://queue.fal.run/"
UPLOAD_URL = "https://rest.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3"
DEFAULT_ENDPOINT = "fal-ai/hyper3d/rodin"
# Image-list input of each known endpoint (other endpoints need --image-field), and whether it takes
# `condition_mode` (only the original endpoint does; v2 and v2.5 combine several views on their own).
IMAGE_FIELDS = {
    "fal-ai/hyper3d/rodin": "input_image_urls",
    "fal-ai/hyper3d/rodin/v2": "input_image_urls",
    "fal-ai/hyper3d/rodin/v2.5": "image_urls",
}
CONDITION_MODE = {"fal-ai/hyper3d/rodin"}
KEY_ENV = ("FAL_KEY",)
RAW_GLB = "inputs/rodin_raw.glb"
META = "inputs/rodin_meta.json"
PENDING = "inputs/rodin_pending.json"
RUNNING = ("IN_QUEUE", "IN_PROGRESS")


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def api_key():
    for name in KEY_ENV:
        if os.environ.get(name):
            return os.environ[name]
    return None


def endpoint_name(endpoint=None):
    endpoint = (endpoint or os.environ.get("LOWPOLY_RODIN_ENDPOINT") or DEFAULT_ENDPOINT).strip("/")
    if not endpoint or any(part in ("", ".", "..") for part in endpoint.split("/")) or "?" in endpoint or "#" in endpoint:
        raise ValueError(f"Invalid fal endpoint {endpoint!r}")
    return endpoint


def image_field(endpoint, override=None):
    field = override or IMAGE_FIELDS.get(endpoint)
    if not field:
        raise ValueError(f"Unknown image input for {endpoint}; pass --image-field (known: {sorted(IMAGE_FIELDS)})")
    return field


def data_uri(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode("ascii")


def input_images(folder, prep):
    """Prepared cutouts in a stable order: the single view, or front/right/back/left."""
    if prep["mode"] == "sv":
        return [local_path(folder, prep["input_file"])]
    return [local_path(folder, s["file"]) for s in prep["sources"]]


def parse_params(pairs):
    """`key=value` pairs; values are JSON when they parse (numbers, booleans, lists), otherwise strings."""
    out = {}
    for pair in pairs or ():
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise ValueError(f"--param needs key=value, got {pair!r}")
        try:
            out[key] = json.loads(value)
        except json.JSONDecodeError:
            out[key] = value
    return out


def build_payload(images, field, mode="sv", seed=None, quality=None, material=None, tier=None, params=None,
                  condition_mode=False):
    """Request body. Only options that were asked for are sent, so one builder fits every Rodin endpoint."""
    payload = {field: list(images), "geometry_file_format": "glb"}
    if mode == "mv" and condition_mode:
        payload["condition_mode"] = "concat"  # several views of one object
    for name, value in (("seed", seed), ("quality", quality), ("material", material), ("tier", tier)):
        if value is not None:
            payload[name] = value
    payload.update(params or {})
    return payload


def redacted(payload, field, digests):
    """The payload as recorded: local images (inline or uploaded) replaced by the SHA-256 of their PNG,
    so the record and the cache key do not depend on upload URLs."""
    out = dict(payload)
    out[field] = [("sha256:" + d) if d else u for u, d in zip(payload[field], digests)]
    return out


def _is_fal_host(url):
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    return parts.scheme == "https" and (host in ("fal.run", "rest.fal.ai") or host.endswith(".fal.run"))


def _http_json(url, key, body=None, method=None, request=None, timeout=120):
    if not _is_fal_host(url):
        raise ValueError(f"Refusing to send the fal key to {url}")
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers={"Authorization": "Key " + key, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with (request or urllib.request.urlopen)(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:2000]
        raise RuntimeError(f"fal {req.get_method()} {url} failed ({e.code}): {detail}") from None


def upload(path, key, request=None):
    """Two-step fal CDN upload: initiate with the key, then PUT the bytes to the signed URL without it.
    Uploaded files are public to anyone holding the URL."""
    path = Path(path)
    reply = _http_json(UPLOAD_URL, key, {"file_name": path.name, "content_type": "image/png"}, request=request)
    if not reply.get("upload_url") or not reply.get("file_url"):
        raise RuntimeError(f"fal upload reply has no upload_url/file_url: {reply}")
    if urllib.parse.urlsplit(reply["upload_url"]).scheme != "https":
        raise RuntimeError("fal returned a non-HTTPS upload URL")
    req = urllib.request.Request(reply["upload_url"], data=path.read_bytes(), method="PUT",
                                 headers={"Content-Type": "image/png"})
    try:
        with (request or urllib.request.urlopen)(req, timeout=300) as response:
            response.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"fal CDN upload of {path.name} failed ({e.code})") from None
    return reply["file_url"]


def submit(endpoint, payload, key, request=None):
    reply = _http_json(QUEUE_URL + endpoint, key, payload, request=request)
    for field in ("request_id", "status_url", "response_url"):
        if not reply.get(field):
            raise RuntimeError(f"fal submit reply has no {field}: {reply}")
    return reply


def wait(job, key, timeout=1800, poll=5.0, request=None, sleep=time.sleep, clock=time.monotonic, log=print):
    """Poll `status_url` until COMPLETED; a timeout leaves the job pending for the next run."""
    deadline = clock() + timeout
    last = None
    while True:
        status = _http_json(job["status_url"], key, request=request)
        state = status.get("status")
        if state == "COMPLETED":
            return status
        if state not in RUNNING:
            raise RuntimeError(f"Rodin job {job['request_id']} has unexpected status: {status}")
        if state != last:
            log(f"RODIN {job['request_id']} {state}", flush=True)
            last = state
        if clock() >= deadline:
            raise TimeoutError(f"Rodin job {job['request_id']} still {state} after {timeout:.0f}s; "
                               "run again to keep waiting for the same request (no new charge)")
        sleep(poll)


def download(url, dest, request=None, timeout=300):
    """Fetch the generated file. The key is never sent; result files are served from fal's media CDN."""
    if urllib.parse.urlsplit(url).scheme != "https":
        raise ValueError(f"Refusing non-HTTPS download {url}")
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    with (request or urllib.request.urlopen)(req, timeout=timeout) as response:
        Path(dest).write_bytes(response.read())


def cache_key(endpoint, payload, field, digests):
    return hashlib.sha256(json.dumps({"endpoint": endpoint, "payload": redacted(payload, field, digests)},
                                     sort_keys=True).encode("utf-8")).hexdigest()


def status(folder):
    folder = Path(folder).resolve()
    meta, pending = local_path(folder, META), local_path(folder, PENDING)
    return {
        "endpoint": endpoint_name(),
        "key": "set (FAL_KEY)" if api_key() else "missing: set FAL_KEY locally",
        "raw_glb": RAW_GLB if local_path(folder, RAW_GLB).is_file() else None,
        "generated": json.loads(meta.read_text(encoding="utf-8")) if meta.is_file() else None,
        "pending": json.loads(pending.read_text(encoding="utf-8")) if pending.is_file() else None,
    }


def run_rodin(folder, mode="sv", view="front", set_name=None, endpoint=None, field=None, seed=None, quality=None,
              material=None, tier=None, params=None, image_urls=None, force=False, dry_run=False, timeout=1800,
              poll=5.0, inline=False, request=None, sleep=time.sleep, clock=time.monotonic, log=print):
    """Prepare inputs, generate once through fal (cached by input and parameter hash) and validate the GLB."""
    from .pixal3d import prepare_inputs
    folder = Path(folder).resolve()
    endpoint = endpoint_name(endpoint)
    field = image_field(endpoint, field)
    paths = []
    if image_urls:
        images, digests, prep = list(image_urls), [None] * len(image_urls), {"mode": mode, "image_urls": list(image_urls)}
        for url in images:
            if urllib.parse.urlsplit(url).scheme != "https":
                raise ValueError(f"--image-url must be https: {url}")
    else:
        prep = prepare_inputs(folder, mode=mode, view=view, set_name=set_name)
        paths = input_images(folder, prep)
        digests = [file_sha256(p) for p in paths]
        images = ["sha256:" + d for d in digests]  # replaced by uploaded or inline images before submitting
    options = dict(seed=seed, quality=quality, material=material, tier=tier, params=params,
                   condition_mode=endpoint in CONDITION_MODE)
    payload = build_payload(images, field, mode, **options)
    record_payload = redacted(payload, field, digests)
    key_hash = cache_key(endpoint, payload, field, digests)
    raw_glb, meta_path, pending_path = (local_path(folder, r) for r in (RAW_GLB, META, PENDING))

    if dry_run:
        return {"endpoint": QUEUE_URL + endpoint, "payload": record_payload, "cache_key": key_hash}
    if not force and raw_glb.is_file() and meta_path.is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old.get("cache_key") == key_hash and old.get("raw_glb_sha256") == file_sha256(raw_glb):
            log("RODIN cached;", RAW_GLB)
            return meta_path, False
    key = api_key()
    if not key:
        raise ValueError("Set FAL_KEY locally (never in asset.json); `--dry-run` shows the request without it")

    job = None
    if pending_path.is_file():
        old = json.loads(pending_path.read_text(encoding="utf-8"))
        if old.get("cache_key") == key_hash:
            job = old
            log(f"RODIN resuming {job['request_id']} (already paid for)", flush=True)
        elif not force:
            raise ValueError(f"{PENDING} holds unfinished request {old.get('request_id')} with other inputs; "
                             "run again with its settings to collect it, or pass --force to abandon it")
    if job is None:
        if paths and inline:
            payload = build_payload([data_uri(p) for p in paths], field, mode, **options)
        elif paths:
            log(f"RODIN uploading {len(paths)} input image(s) to fal's CDN", flush=True)
            payload = build_payload([upload(p, key, request=request) for p in paths], field, mode, **options)
        log(f"RODIN submitting one paid generation to {endpoint}", flush=True)
        reply = submit(endpoint, payload, key, request=request)
        job = {"cache_key": key_hash, "endpoint": endpoint, "request_id": reply["request_id"],
               "status_url": reply["status_url"], "response_url": reply["response_url"],
               "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
        local_path(folder, "inputs").mkdir(parents=True, exist_ok=True)
        write_json(pending_path, job, indent=2)

    wait(job, key, timeout=timeout, poll=poll, request=request, sleep=sleep, clock=clock, log=log)
    try:
        # a failed or cancelled request is COMPLETED too; its result carries the error
        result = _http_json(job["response_url"], key, request=request)
    except RuntimeError:
        pending_path.unlink(missing_ok=True)
        raise
    mesh = result.get("model_mesh") or {}
    if not mesh.get("url"):
        raise RuntimeError(f"Rodin result for {job['request_id']} has no model_mesh.url: {result}")
    with replacing(str(raw_glb)) as tmp:
        download(mesh["url"], tmp, request=request)
        load_glb(tmp)

    record = {
        "backend": "fal.ai/" + endpoint,
        "provider": "hyper3d-rodin",
        "endpoint": endpoint,
        "request_id": job["request_id"],
        "submitted_at": job.get("submitted_at"),
        "cache_key": key_hash,
        "prep": prep,
        "payload": record_payload,
        "image_transport": "urls" if image_urls else ("inline" if inline else "fal-cdn"),
        "result": {k: v for k, v in result.items() if k != "model_mesh"} | {"model_mesh": mesh},
        "raw_glb": RAW_GLB,
        "raw_glb_sha256": file_sha256(raw_glb),
        "inferred": True,
        "review_status": "pending",
    }
    write_json(meta_path, record, indent=2)
    pending_path.unlink(missing_ok=True)
    log("RODIN generated", RAW_GLB)
    return meta_path, True
