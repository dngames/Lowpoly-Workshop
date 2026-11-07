"""Pixal3D (raven38/pixal3d.cpp) image-to-3D backend and Blender MCP decimation bridge.

Optional: a project that starts from a supplied base mesh skips generation and uses `lowpoly ASSET base ...`
(`base_mesh.py`). The reduction code and the GLB loader are shared with that path.

Workflow:
  1. Prepare reference image(s) as cropped RGBA PNG(s) (`pixal3d-prep`).
  2. Run `trellis-cli` (`raven38/pixal3d.cpp`) on CPU/GPU to generate `inputs/pixal3d_raw.glb` (`pixal3d-run`).
  3. Reduce polycount and normalize orientation/scale/ground in Blender MCP (`pixal3d-mcp-script` / `pixal3d-decimate`)
     to produce `inputs/pixal3d_lowpoly.glb` and `inputs/pixal3d_atlas.png`.
  4. Load `inputs/pixal3d_lowpoly.glb` in `gen.py` via `load_glb_node()` so Workshop's `build`, `check`, `review`,
     and `page` stages verify the reduced model against the project contract.
"""
from pathlib import Path
import glob
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import numpy as np

from .spec import read_spec, local_path
from .kit.atomic import replacing, write_json
from .kit.glb import load_glb
from .reduce import reduce_code
# The loader is general (any GLB, not only Pixal3D output); it lives in base_mesh and stays importable here.
from .base_mesh import _extract_glb_triangles_and_uvs, load_glb_node, read_rgb_path as _read_rgb_path  # noqa: F401

UPSTREAM_REPO = "https://github.com/raven38/pixal3d.cpp"
HF_SV_REPO = "raven38/pixal3d-sv-q8_0-v1"
HF_MV_REPO = "raven38/pixal3d-q8_0-v1"
DEFAULT_SV_FOV = 0.3490658503988659  # 20 degrees in radians
CANONICAL_MV_DISTANCE = 3.119
CANONICAL_MV_VIEWS = ("front", "right", "back", "left")

SHARED_FILES = (
    "dinov3.gguf",
    "pixal3d_naf.gguf",
    "ss_dec.gguf",
    "shape_dec.gguf",
    "tex_dec.gguf",
)


def required_model_files(family="sv"):
    if family not in ("sv", "mv"):
        raise ValueError(f"Pixal3D model family must be 'sv' or 'mv', got {family!r}")
    flows = (
        f"pixal3d_ss_flow_{family}.gguf",
        f"pixal3d_shape_flow_512_{family}.gguf",
        f"pixal3d_shape_flow_1024_{family}.gguf",
        f"pixal3d_tex_flow_1024_{family}.gguf",
    )
    return SHARED_FILES + flows


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def physical_threads():
    env = os.environ.get("LOWPOLY_PIXAL3D_THREADS")
    if env:
        val = int(env)
        if val < 1:
            raise ValueError("LOWPOLY_PIXAL3D_THREADS must be >= 1")
        return val
    logical = os.cpu_count() or 4
    return max(1, logical // 2)


def _studio_config():
    appdata = os.environ.get("APPDATA")
    candidates = []
    if appdata:
        candidates.append(Path(appdata) / "trellis-studio" / "config.json")
    candidates.append(Path.home() / ".config" / "trellis-studio" / "config.json")
    for cfg in candidates:
        if cfg.is_file():
            try:
                return json.loads(cfg.read_text(encoding="utf-8-sig"))
            except Exception:
                pass
    return {}


def find_pixal3d():
    for env in ("LOWPOLY_PIXAL3D_BIN", "TRELLIS_CLI", "PIXAL3D_CLI"):
        val = os.environ.get(env)
        if val and Path(val).is_file():
            return str(Path(val).resolve())
    cfg = _studio_config()
    if cfg.get("serverBin"):
        srv = Path(cfg["serverBin"])
        for name in ("trellis-cli.exe", "trellis-cli"):
            cand = srv.parent / name
            if cand.is_file():
                return str(cand.resolve())
    kit_home = Path(os.environ.get("LOWPOLY_KIT_HOME", Path.home() / ".lowpoly-kit"))
    local_app = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    patterns = [
        str(local_app / "trellis-studio" / "runtime" / "trellis-cli.exe"),
        str(local_app / "trellis-studio" / "runtime" / "trellis-cli"),
        str(kit_home / "pixal3d" / "**" / "trellis-cli.exe"),
        str(kit_home / "pixal3d" / "**" / "trellis-cli"),
    ]
    for pat in patterns:
        matches = glob.glob(pat, recursive=True)
        if matches:
            return str(Path(sorted(matches)[-1]).resolve())
    for exe in ("trellis-cli", "pixal3d"):
        found = shutil.which(exe)
        if found:
            return str(Path(found).resolve())
    raise FileNotFoundError(
        "Pixal3D CLI (trellis-cli from raven38/pixal3d.cpp) not found. "
        "Build or install raven38/pixal3d.cpp and set LOWPOLY_PIXAL3D_BIN to trellis-cli."
    )


def verify_models_dir(directory, family="sv"):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"Pixal3D {family.upper()} models directory not found: {directory}")
    manifest_path = directory / "pixal3d-models.json"
    manifest = None
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        mf_family = manifest.get("model_family")
        if mf_family and mf_family != family:
            raise ValueError(f"Manifest at {manifest_path} is for family {mf_family!r}, expected {family!r}")
    expected = required_model_files(family)
    missing = [name for name in expected if not (directory / name).is_file() or (directory / name).stat().st_size == 0]
    if missing:
        repo = HF_SV_REPO if family == "sv" else HF_MV_REPO
        raise FileNotFoundError(
            f"Pixal3D {family.upper()} models directory {directory} is missing required GGUF files: "
            f"{', '.join(missing)}. Download from https://huggingface.co/{repo}"
        )
    if manifest:
        for entry in manifest.get("files", []):
            fpath = directory / entry["name"]
            if fpath.is_file() and "size_bytes" in entry and fpath.stat().st_size != int(entry["size_bytes"]):
                raise ValueError(f"Model file size mismatch for {entry['name']} in {directory}")
    return str(directory)


def find_models(family="sv"):
    if family not in ("sv", "mv"):
        raise ValueError(f"Pixal3D model family must be 'sv' or 'mv', got {family!r}")
    env_specific = "LOWPOLY_PIXAL3D_MODELS_SV" if family == "sv" else "LOWPOLY_PIXAL3D_MODELS_MV"
    for env in (env_specific, "LOWPOLY_PIXAL3D_MODELS"):
        val = os.environ.get(env)
        if val and Path(val).is_dir():
            return verify_models_dir(val, family)
    cfg = _studio_config()
    cfg_key = "modelsDirSv" if family == "sv" else "modelsDir"
    if cfg.get(cfg_key) and Path(cfg[cfg_key]).is_dir():
        return verify_models_dir(cfg[cfg_key], family)
    kit_home = Path(os.environ.get("LOWPOLY_KIT_HOME", Path.home() / ".lowpoly-kit"))
    local_app = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    sub = "models-sv" if family == "sv" else "models"
    candidates = [
        kit_home / "pixal3d" / sub,
        kit_home / "pixal3d" / f"pixal3d-{family}-q8_0-v1",
        local_app / "trellis-studio" / sub,
    ]
    for cand in candidates:
        if cand.is_dir():
            try:
                return verify_models_dir(cand, family)
            except (FileNotFoundError, ValueError):
                continue
    repo = HF_SV_REPO if family == "sv" else HF_MV_REPO
    raise FileNotFoundError(
        f"Pixal3D {family.upper()} GGUF models not found. Download {repo} and set {env_specific}."
    )


def doctor_status():
    info = {"upstream": UPSTREAM_REPO, "threads": physical_threads(), "binary": None, "models_sv": None, "models_mv": None}
    try:
        info["binary"] = find_pixal3d()
    except FileNotFoundError as e:
        info["binary_error"] = str(e)
    for fam in ("sv", "mv"):
        try:
            info[f"models_{fam}"] = find_models(fam)
        except (FileNotFoundError, ValueError) as e:
            info[f"models_{fam}_error"] = str(e)
    return info


def cutout_rgba(image_or_path, box=None, size=1024, fill_ratio=0.85, thr=22):
    """Produce a centered square RGBA cutout suitable for Pixal3D conditioning.

    If the source image already has a non-opaque alpha channel, that alpha is preserved;
    otherwise border-median foreground detection (`fg_mask`) creates the alpha mask.
    """
    from PIL import Image
    from .kit.sheets import fg_mask
    if size < 64 or size > 4096:
        raise ValueError("Cutout size must be between 64 and 4096")
    if not (0.2 <= fill_ratio <= 0.98):
        raise ValueError("fill_ratio must be between 0.2 and 0.98")
    with Image.open(image_or_path) if isinstance(image_or_path, (str, Path)) else image_or_path as src:
        im = src.convert("RGBA")
        if box is not None:
            x0, y0, x1, y1 = [int(round(v)) for v in box]
            im = im.crop((x0, y0, x1, y1))
        arr = np.asarray(im, dtype=np.uint8).copy()
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]
    if int(alpha.min()) == 255 or int(alpha.max()) == 0:
        mask = fg_mask(rgb, thr=thr)
        if not mask.any():
            mask = np.ones(rgb.shape[:2], dtype=bool)
        alpha = np.where(mask, 255, 0).astype(np.uint8)
        arr[:, :, 3] = alpha
    else:
        mask = alpha > 8
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("Reference image has no foreground pixels after masking")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    crop = Image.fromarray(arr[y0:y1, x0:x1], mode="RGBA")
    cw, ch = crop.size
    target_span = max(1, int(round(size * fill_ratio)))
    scale = target_span / max(cw, ch)
    nw = max(1, min(size, int(round(cw * scale))))
    nh = max(1, min(size, int(round(ch * scale))))
    resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2))
    return canvas


def _resolve_view_source(folder, spec, view, set_name=None):
    for ref in spec.get("references", []):
        if ref.get("view") == view:
            return local_path(folder, ref["path"]), None
    sets = spec.get("sets", {})
    chosen_sets = [set_name] if set_name else list(sets)
    for sname in chosen_sets:
        st = sets.get(sname, {})
        views = st.get("views", {})
        if view in views:
            from .kit.asset import Asset
            a = Asset(folder)
            return local_path(folder, st["image"]), a.crop_box(sname, view)
    # A reference with a declared view (e.g. a turnaround sheet) is never a single front view
    if view == "front":
        for ref in spec.get("references", []):
            if not ref.get("view"):
                return local_path(folder, ref["path"]), None
    raise ValueError(
        f"No reference or sheet view {view!r} configured in asset.json; "
        "for a multi-view sheet, declare a set with a crop box per view"
    )


def _canonical_transform_matrix(azimuth_deg):
    """Blender/NeRF camera-to-world matrix at elevation 0 and canonical Pixal3D distance."""
    az = math.radians(azimuth_deg)
    # Canonical turntable around Y-up / Z-front in NeRF camera convention
    sin_a, cos_a = math.sin(az), math.cos(az)
    d = CANONICAL_MV_DISTANCE
    return [
        [cos_a, 0.0, sin_a, d * sin_a],
        [0.0, 1.0, 0.0, 0.0],
        [-sin_a, 0.0, cos_a, d * cos_a],
        [0.0, 0.0, 0.0, 1.0],
    ]


def prepare_inputs(folder, mode="sv", view="front", set_name=None, size=1024):
    """Prepare single-view (`sv`) or 4-view (`mv`) RGBA inputs under `inputs/pixal3d/`."""
    folder = Path(folder).resolve()
    spec = read_spec(folder)
    if mode not in ("sv", "mv"):
        raise ValueError("mode must be 'sv' or 'mv'")
    prep_dir = local_path(folder, "inputs/pixal3d")
    prep_dir.mkdir(parents=True, exist_ok=True)
    if mode == "sv":
        src_path, box = _resolve_view_source(folder, spec, view, set_name=set_name)
        rgba = cutout_rgba(src_path, box=box, size=size, fill_ratio=0.88)
        out_png = prep_dir / "sv_input.png"
        rgba.save(out_png, format="PNG")
        meta = {
            "mode": "sv",
            "view": view,
            "source_path": src_path.relative_to(folder).as_posix(),
            "source_sha256": file_sha256(src_path),
            "box": box,
            "input_file": out_png.relative_to(folder).as_posix(),
            "input_sha256": file_sha256(out_png),
            "size": size,
        }
        write_json(prep_dir / "prep.json", meta, indent=2)
        return meta

    views_dir = prep_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)
    azimuths = {"front": 0.0, "right": 90.0, "back": 180.0, "left": 270.0}
    frames = []
    sources = []
    for idx, vname in enumerate(CANONICAL_MV_VIEWS):
        src_path, box = _resolve_view_source(folder, spec, vname, set_name=set_name)
        rgba = cutout_rgba(src_path, box=box, size=size, fill_ratio=0.85)
        fname = f"view{idx:02d}_{vname}.png"
        out_png = views_dir / fname
        rgba.save(out_png, format="PNG")
        frames.append({
            "file_path": fname,
            "camera_angle_x": DEFAULT_SV_FOV,
            "transform_matrix": _canonical_transform_matrix(azimuths[vname]),
        })
        sources.append({
            "view": vname,
            "source_path": src_path.relative_to(folder).as_posix(),
            "source_sha256": file_sha256(src_path),
            "box": box,
            "file": out_png.relative_to(folder).as_posix(),
            "sha256": file_sha256(out_png),
        })
    transforms = {
        "camera_angle_x": DEFAULT_SV_FOV,
        "mesh_scale": 1.0,
        "frames": frames,
    }
    transforms_path = views_dir / "transforms.json"
    write_json(transforms_path, transforms, indent=2)
    meta = {
        "mode": "mv",
        "views_dir": views_dir.relative_to(folder).as_posix(),
        "transforms": transforms_path.relative_to(folder).as_posix(),
        "transforms_sha256": file_sha256(transforms_path),
        "sources": sources,
        "size": size,
    }
    write_json(prep_dir / "prep.json", meta, indent=2)
    return meta


def build_cli_command(
    folder,
    mode="sv",
    models_dir=None,
    binary=None,
    threads=None,
    gpu=-1,
    seed=42,
    decim=None,
    atlas=1024,
    fov=DEFAULT_SV_FOV,
    output_rel="inputs/pixal3d_raw.glb",
):
    folder = Path(folder).resolve()
    if mode not in ("sv", "mv"):
        raise ValueError("mode must be 'sv' or 'mv'")
    exe = binary or find_pixal3d()
    mdir = models_dir or find_models(mode)
    nthreads = int(threads if threads is not None else physical_threads())
    out_path = local_path(folder, output_rel)
    cmd = [str(exe)]
    if mode == "sv":
        sv_img = local_path(folder, "inputs/pixal3d/sv_input.png")
        cmd += ["--sv-image", str(sv_img), "--fov", f"{float(fov):.10f}"]
    else:
        views_dir = local_path(folder, "inputs/pixal3d/views")
        cmd += ["--views", str(views_dir), "--pixal3d-weights", "mv"]
    cmd += [
        "--models", str(mdir),
        "--gpu", str(int(gpu)),
        "--threads", str(nthreads),
        "--seed", str(int(seed)),
        "--res", "1024",
        "--atlas", str(int(atlas)),
        "--webp", "off",
    ]
    # --decim is a legacy cluster-grid size; omitting it keeps the Pixal3D quadric simplify to 1M faces
    if decim is not None:
        cmd += ["--decim", str(int(decim))]
    cmd.append(str(out_path))
    return cmd


def run_pixal3d(
    folder,
    mode="sv",
    view="front",
    set_name=None,
    threads=None,
    gpu=-1,
    seed=42,
    decim=None,
    atlas=1024,
    fov=DEFAULT_SV_FOV,
    force=False,
    runner=subprocess.run,
):
    """Prepare inputs and execute `trellis-cli` (`raven38/pixal3d.cpp`) with content-hash caching."""
    folder = Path(folder).resolve()
    prep = prepare_inputs(folder, mode=mode, view=view, set_name=set_name)
    raw_glb = local_path(folder, "inputs/pixal3d_raw.glb")
    meta_path = local_path(folder, "inputs/pixal3d_meta.json")
    nthreads = int(threads if threads is not None else physical_threads())
    cache_key = hashlib.sha256(
        json.dumps(
            {
                "prep": prep,
                "mode": mode,
                "seed": int(seed),
                "decim": None if decim is None else int(decim),
                "atlas": int(atlas),
                "fov": round(float(fov), 8) if mode == "sv" else None,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if not force and raw_glb.is_file() and meta_path.is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        if old.get("cache_key") == cache_key and old.get("raw_glb_sha256") == file_sha256(raw_glb):
            print("PIXAL3D cached;", raw_glb.relative_to(folder).as_posix())
            return meta_path, False

    exe = find_pixal3d()
    mdir = find_models(mode)
    raw_glb.parent.mkdir(parents=True, exist_ok=True)
    with replacing(str(raw_glb)) as tmp_glb:
        cmd = build_cli_command(
            folder,
            mode=mode,
            models_dir=mdir,
            binary=exe,
            threads=nthreads,
            gpu=gpu,
            seed=seed,
            decim=decim,
            atlas=atlas,
            fov=fov,
            output_rel=Path(tmp_glb).relative_to(folder).as_posix(),
        )
        proc = runner(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            tail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-4000:]
            raise RuntimeError(f"pixal3d.cpp failed (exit {proc.returncode}):\n{tail}")
        load_glb(tmp_glb)

    record = {
        "backend": "raven38/pixal3d.cpp",
        "mode": mode,
        "cache_key": cache_key,
        "prep": prep,
        "seed": int(seed),
        "decim": None if decim is None else int(decim),
        "atlas": int(atlas),
        "gpu": int(gpu),
        "threads": nthreads,
        "raw_glb": raw_glb.relative_to(folder).as_posix(),
        "raw_glb_sha256": file_sha256(raw_glb),
    }
    write_json(meta_path, record, indent=2)
    print("PIXAL3D generated", raw_glb.relative_to(folder).as_posix())
    return meta_path, True


def default_target_params(folder, budget=None, height=None, node_name=None):
    folder = Path(folder).resolve()
    spec = read_spec(folder)
    out0 = spec["outputs"][0]
    contract = out0.get("contract", {})
    target_budget = int(budget or contract.get("budget") or 1500)
    if target_budget < 12:
        raise ValueError("Target triangle budget must be at least 12")
    chosen_node = node_name
    target_height = float(height) if height is not None else None
    if chosen_node is None or target_height is None:
        try:
            from .kit.asset import Asset
            from .kit.mesh import triangles
            a = Asset(folder)
            nodes = a.build(out0.get("variant"), out0.get("scale", 1.0))
            mesh_names = [n for n, nd in nodes.items() if nd.get("faces")]
            if chosen_node is None:
                chosen_node = mesh_names[0] if mesh_names else "Body"
            if target_height is None and mesh_names:
                tris, _, _ = triangles(nodes)
                pts = tris.reshape(-1, 3)
                span_y = float(pts[:, 1].max() - pts[:, 1].min())
                if span_y > 1e-4:
                    target_height = round(span_y, 4)
        except Exception:
            pass
    return {
        "budget": target_budget,
        "height": target_height or 1.0,
        "node_name": chosen_node or "Body",
        "ground": bool(contract.get("ground")),
    }


def blender_mcp_decimate_code(
    folder,
    budget=None,
    height=None,
    node_name=None,
    ground=None,
    rotate_front=True,
    planar_deg=3.0,
    weld_dist=1e-4,
):
    """Return deterministic Blender Python code for `tools.blender.execute_blender_code`.

    Imports `inputs/pixal3d_raw.glb`, rotates 180 deg so Pixal3D's -Z front aligns with
    Workshop's +Z glTF front, welds close vertices, reduces polycount to `budget` via
    Blender's UV-preserving Collapse Decimate modifier, normalizes metric height and
    ground contact, and writes `inputs/pixal3d_lowpoly.glb` + `inputs/pixal3d_atlas.png`.
    """
    folder = Path(folder).resolve()
    defaults = default_target_params(folder, budget=budget, height=height, node_name=node_name)
    target_budget = defaults["budget"]
    target_height = float(defaults["height"])
    target_node = defaults["node_name"]
    do_ground = defaults["ground"] if ground is None else bool(ground)

    raw_glb = local_path(folder, "inputs/pixal3d_raw.glb")
    low_glb = local_path(folder, "inputs/pixal3d_lowpoly.glb")
    atlas_png = local_path(folder, "inputs/pixal3d_atlas.png")
    report_json = local_path(folder, "inputs/pixal3d_lowpoly.json")

    config = {
        "raw_glb": str(raw_glb),
        "low_glb": str(low_glb),
        "atlas_png": str(atlas_png),
        "report_json": str(report_json),
        "budget": int(target_budget),
        "height": float(target_height),
        "node_name": str(target_node),
        "ground": bool(do_ground),
        "rotate_front": bool(rotate_front),
        "planar_deg": float(planar_deg),
        "weld_dist": float(weld_dist),
    }
    return reduce_code(config)


def decimate_with_blender(folder, budget=None, height=None, node_name=None, ground=None, rotate_front=True):
    """Run the Blender decimation step via Workshop's headless Blender launcher."""
    from .pipeline import blender
    folder = Path(folder).resolve()
    defaults = default_target_params(folder, budget=budget, height=height, node_name=node_name)
    do_ground = defaults["ground"] if ground is None else bool(ground)
    blender(
        "decimate_pixal3d.py",
        str(folder),
        str(defaults["budget"]),
        str(defaults["height"]),
        str(defaults["node_name"]),
        "1" if do_ground else "0",
        "1" if rotate_front else "0",
    )
    return local_path(folder, "inputs/pixal3d_lowpoly.glb")


def make_decal_atlas(texture_path=None, cell="surface", base="#808080", size=1024, mask_channel=None):
    """Create a Workshop `Atlas` whose `cell` paints the Pixal3D texture PNG."""
    from .kit.atlas import Atlas, stretch, rgb

    def paint_tex(col, kit, rect, atlas):
        x0, y0, x1, y1 = rect
        arr = _read_rgb_path(texture_path) if texture_path else None
        if arr is not None:
            col[y0:y1, x0:x1] = stretch(arr, y1 - y0, x1 - x0)
        else:
            col[y0:y1, x0:x1] = rgb(base)
        if mask_channel:
            kit[y0:y1, x0:x1, atlas.mask_channels.index(mask_channel)] = 255

    pad = 16
    span = size - 2 * pad
    return Atlas(
        {cell: (base, mask_channel, cell)},
        decals={cell: ((span, span), paint_tex)},
        base=base,
        size=size,
        rects={cell: (pad, pad, pad + span, pad + span)},
        decal_margin=2,
    )
