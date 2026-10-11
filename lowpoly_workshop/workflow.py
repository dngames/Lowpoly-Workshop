"""Resumable visual review bound to source, exports, images and prior decisions.

Reviewers make visual decisions. This module enforces evidence and ordering only.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import itertools
import json
import os
import tempfile
from .spec import read_spec, local_path
from .features import STAGES, enabled, requirements
from .approval import export_hashes
from .runner import fingerprint


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path(folder, spec):
    return local_path(folder, spec.get("out_dir", "out") + "/workflow.json")


def _load(folder, spec):
    path = _path(folder, spec)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"version": 1, "features": {}, "stages": {}}
    if (data.get("version") != 1 or not isinstance(data.get("features"), dict) or
            not isinstance(data.get("stages"), dict)):
        raise ValueError("Invalid saved workflow")
    return data


def _save(folder, spec, data):
    path = _path(folder, spec)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".workflow-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _context(folder, spec):
    """Read current evidence once; no generator execution or rendering."""
    folder = Path(folder)
    result = {"source": fingerprint(folder), "errors": []}
    try:
        result["exports"] = export_hashes(folder)
    except FileNotFoundError:
        result["exports"] = {}
        result["errors"].append("Build the declared exports")
    build_path = local_path(folder, ".workshop/build.json")
    result["build_outputs"] = {}
    if not build_path.exists():
        result["errors"].append("Build evidence missing; rerun build")
    else:
        build = json.loads(build_path.read_text(encoding="utf-8"))
        declared = {local_path(folder, o["file"]).relative_to(folder.resolve()).as_posix() for o in spec["outputs"]}
        recorded = build.get("outputs", {})
        valid = isinstance(recorded, dict) and declared <= set(recorded)
        if valid:
            for name, expected in recorded.items():
                path = local_path(folder, name)
                if not path.is_file() or file_hash(path) != expected:
                    valid = False
        if build.get("source") != result["source"] or not valid:
            result["errors"].append("Build evidence is stale; rerun build")
        else:
            result["build_outputs"] = recorded
    review = local_path(folder, spec.get("out_dir", "out") + "/review/index.json")
    result["shots"] = {}
    result["review_hash"] = None
    if not review.exists():
        result["errors"].append("Render current review evidence with review")
        return result
    index = json.loads(review.read_text(encoding="utf-8"))
    result["review_hash"] = file_hash(review)
    if index.get("source") != result["source"] or index.get("exports") != result["exports"]:
        result["errors"].append("Review index is stale; rerun review")
    for shot in index.get("shots", []):
        path = local_path(folder, shot["file"])
        if not path.is_relative_to(review.parent):
            raise ValueError("Review image must be inside the review output folder")
        if (not path.is_file() or file_hash(path) != shot.get("image_sha256") or
                shot.get("sha256") != result["exports"].get(shot.get("output")) or
                shot.get("source") != "exported-model-render"):
            continue
        key = tuple(shot.get(k) for k in ("output", "pose", "region", "mode", "view"))
        result["shots"][key] = shot
    return result


def _snapshot(context, keys, feature_id=None, nodes=None):
    if context["errors"]:
        raise ValueError("; ".join(context["errors"]))
    missing = []
    images = {}
    for key in keys:
        shot = context["shots"].get(key)
        if (shot is None or (feature_id and (shot.get("feature_id") != feature_id or
                shot.get("nodes") != nodes))):
            missing.append(" / ".join(key))
        else:
            images[shot["file"]] = shot["image_sha256"]
    if missing:
        raise ValueError("Missing current review images: " + "; ".join(missing))
    return dict(source=context["source"], exports=context["exports"], build_outputs=context["build_outputs"],
                review_index=context["review_hash"], images=images)


def _feature_keys(feature):
    return [(feature["output"], p, "feature-" + feature["id"], m, v)
            for p, m, v in itertools.product(feature["poses"], feature["modes"], feature["views"])]


def _feature_status(feature, saved, context):
    row = {**feature, "status": "pending", "next_action": "Render and inspect the required feature views"}
    old = saved.get(feature["id"])
    if old:
        row["note"] = old["note"]
        row["status"] = old["decision"]
        row["next_action"] = "Repair the feature and render again" if old["decision"] == "repair" else "Feature reviewed"
    try:
        current = _snapshot(context, _feature_keys(feature), feature["id"], feature["nodes"])
        if old and old["decision"] in ("accepted", "waived") and old.get("snapshot") != current:
            raise ValueError("Feature evidence changed; inspect and review again")
    except ValueError as error:
        row["evidence_issue"] = str(error)
        if old and old["decision"] in ("accepted", "waived"):
            row["status"] = "stale"
        row["next_action"] = str(error)
    return row


def review_feature(folder, feature_id, decision, note):
    spec = read_spec(folder)
    feature = next((f for f in spec.get("features", []) if f["id"] == feature_id), None)
    if feature is None:
        raise ValueError("Unknown feature: " + feature_id)
    if decision not in ("accepted", "repair", "waived") or not note.strip():
        raise ValueError("Feature review needs accepted/repair/waived and a nonempty note")
    if decision == "waived" and feature.get("required", True):
        raise ValueError("Required features cannot be waived")
    context = _context(folder, spec)
    snapshot = _snapshot(context, _feature_keys(feature), feature_id, feature["nodes"]) if decision != "repair" else None
    data = _load(folder, spec)
    record = dict(decision=decision, note=note, snapshot=snapshot,
                  reviewed_at=datetime.now(timezone.utc).isoformat())
    data["features"][feature_id] = record
    _save(folder, spec, data)
    return record


def _checks(folder, spec, context):
    root = local_path(folder, spec.get("out_dir", "out"))
    rows_path, meta_path = root / "check.json", root / "check-meta.json"
    if not rows_path.exists() or not meta_path.exists():
        raise ValueError("Run check before accepting this stage")
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("source") != context["source"] or meta.get("exports") != context["exports"]:
        raise ValueError("Check evidence is stale; rerun check")
    if not isinstance(rows, list) or not rows or any(r.get("ok") is not True for r in rows):
        raise ValueError("Automated checks have unresolved failures")
    return {p.name: file_hash(p) for p in (rows_path, meta_path)}


def _stage_snapshot(folder, spec, stage, context, data, feature_rows, previous, extra):
    snapshot = _snapshot(context, requirements(spec, stage))
    required = [f for f in feature_rows if f["stage"] == stage and f.get("required", True)]
    failures = [f["id"] + ": " + f["status"] for f in required if f["status"] != "accepted"]
    if failures:
        raise ValueError("Review required features: " + "; ".join(failures))
    snapshot["feature_reviews"] = {f["id"]: digest(data["features"][f["id"]]) for f in required}
    snapshot["previous_stages"] = previous.copy()
    if stage in ("construction", "motion-export"):
        snapshot["checks"] = _checks(folder, spec, context)
    snapshot["extra_evidence"] = {}
    output = local_path(folder, spec.get("out_dir", "out"))
    if stage == "motion-export" and (output / "skinned.glb").exists() and not extra:
        raise ValueError("Skinned export needs separate deformation evidence: use --evidence out/your-pose-image.png and explain the review in --note")
    for name in extra:
        path = local_path(folder, name)
        if not path.is_relative_to(output) or path == _path(folder, spec) or path.name == "approval.json":
            raise ValueError("Additional evidence must be a separate file inside out_dir")
        if not path.is_file():
            raise ValueError("Additional review evidence is missing: " + name)
        snapshot["extra_evidence"][name] = file_hash(path)
    return snapshot


def status(folder):
    spec = read_spec(folder)
    if not enabled(spec):
        return dict(status="disabled", features=[], stages=[], current_stage=None, next_command="lowpoly new FOLDER --guided", next_action="Use new --guided or add features to opt in")
    data, context = _load(folder, spec), _context(folder, spec)
    features = [_feature_status(f, data["features"], context) for f in spec.get("features", [])]
    stages, previous = [], {}
    for stage in STAGES:
        old = data["stages"].get(stage)
        row = dict(id=stage, status="pending", next_action="Inspect the required views, then accept this stage")
        if old:
            row["note"] = old["note"]
        try:
            if any(r["status"] != "accepted" for r in stages):
                raise ValueError("Accept the earlier stages first")
            current = _stage_snapshot(folder, spec, stage, context, data, features, previous,
                                      list(old.get("snapshot", {}).get("extra_evidence", {})) if old else [])
            if old:
                if old.get("snapshot") != current:
                    raise ValueError("Stage evidence or earlier decisions changed; review again")
                row.update(status="accepted", next_action="Stage reviewed")
                previous[stage] = digest(old)
        except ValueError as error:
            row.update(status="stale" if old else "blocked", next_action=str(error))
        stages.append(row)
    pending = next((s for s in stages if s["status"] != "accepted"), None)
    next_command = "lowpoly ASSET approve --note REVIEW_NOTE"
    if pending:
        stage = pending["id"]
        unresolved = next((f for f in features if f["stage"] == stage and f.get("required", True) and f["status"] != "accepted"), None)
        if not context["exports"] or any("build" in error.lower() for error in context["errors"]):
            next_command = "lowpoly ASSET build"
        elif context["errors"] or "Missing current review images" in pending["next_action"]:
            next_command = "lowpoly ASSET review"
        elif "check" in pending["next_action"].lower() or "failures" in pending["next_action"]:
            next_command = "lowpoly ASSET check"
        elif unresolved and "Missing current review images" in unresolved.get("evidence_issue", ""):
            next_command = "lowpoly ASSET review"
        elif unresolved:
            next_command = f"lowpoly ASSET features review {unresolved['id']} --decision accepted --note REVIEW_NOTE"
        else:
            next_command = f"lowpoly ASSET workflow accept {stage} --note REVIEW_NOTE"
    return dict(status="complete" if pending is None else "in-progress", features=features, stages=stages,
                next_command=next_command,
                current_stage=pending["id"] if pending else None,
                next_action=pending["next_action"] if pending else "Review the target runtime and record final approval")


def accept_stage(folder, stage, note, evidence=()):
    if stage not in STAGES or not note.strip():
        raise ValueError("Stage acceptance needs a known stage and a nonempty review note")
    spec = read_spec(folder)
    if not enabled(spec):
        raise ValueError("Guided workflow is not enabled")
    state = status(folder)
    if any(s["status"] != "accepted" for s in state["stages"][:STAGES.index(stage)]):
        raise ValueError("Accept the earlier stages first")
    data = _load(folder, spec)
    previous = {s: digest(data["stages"][s]) for s in STAGES[:STAGES.index(stage)]}
    context = _context(folder, spec)
    snapshot = _stage_snapshot(folder, spec, stage, context, data, state["features"], previous, evidence)
    record = dict(note=note, snapshot=snapshot, reviewed_at=datetime.now(timezone.utc).isoformat())
    data["stages"][stage] = record
    _save(folder, spec, data)
    return record


def approval_token(folder):
    spec = read_spec(folder)
    if not enabled(spec):
        return None
    if status(folder)["status"] != "complete":
        raise ValueError("Complete the current guided review stages before final approval")
    return digest(_load(folder, spec))
