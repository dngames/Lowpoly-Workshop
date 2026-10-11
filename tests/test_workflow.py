"""Evidence lifecycle regressions. Images/contract records here are synthetic fixtures.
Actual Blender export/render coverage is documented separately in VALIDATION.md.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from lowpoly_workshop import workflow
from lowpoly_workshop.approval import record, status as approval_status, export_hashes
from lowpoly_workshop.cli import main
from lowpoly_workshop.features import STAGES, requirements, regions
from lowpoly_workshop.runner import fingerprint
from lowpoly_workshop.spec import read_spec
from lowpoly_workshop.templates import create


class GuidedReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.asset = create(Path(self.tmp.name) / "asset", guided=True)
        self.out = self.asset / "out"
        self.out.mkdir()
        (self.out / "model.glb").write_bytes(b"synthetic export fixture")
        self.evidence()

    def save_spec(self, spec):
        (self.asset / "asset.json").write_text(json.dumps(spec), encoding="utf-8")

    def evidence(self):
        spec = read_spec(self.asset)
        root = self.out / "review"
        root.mkdir(exist_ok=True)
        keys = {key: None for stage in STAGES for key in requirements(spec, stage)}
        for feature in spec["features"]:
            for key in workflow._feature_keys(feature):
                keys[key] = feature
        shots = []
        for i, (key, feature) in enumerate(sorted(keys.items())):
            output, pose, region, mode, view = key
            image = root / f"shot-{i}.png"
            Image.new("RGB", (16, 16), (100, i % 255, 70)).save(image)
            shots.append(dict(output=output, pose=pose, region=region, mode=mode, view=view,
                              nodes=feature["nodes"] if feature else ["Crate"],
                              feature_id=feature["id"] if feature else None,
                              file=image.relative_to(self.asset).as_posix(),
                              image_sha256=workflow.file_hash(image),
                              sha256=export_hashes(self.asset)[output], source="exported-model-render"))
        cache=self.asset / ".workshop";cache.mkdir(exist_ok=True)
        (cache / "build.json").write_text(json.dumps(dict(source=fingerprint(self.asset), outputs={"out/model.glb":workflow.file_hash(self.out / "model.glb")})))
        self.index = root / "index.json"
        self.index.write_text(json.dumps(dict(source=fingerprint(self.asset), exports=export_hashes(self.asset), shots=shots)))
        (self.out / "check.json").write_text(json.dumps([dict(ok=True, text="Synthetic contract fixture")]))
        (self.out / "check-meta.json").write_text(json.dumps(dict(source=fingerprint(self.asset), exports=export_hashes(self.asset))))

    def accept(self, stage):
        for f in read_spec(self.asset)["features"]:
            if f["stage"] == stage:
                workflow.review_feature(self.asset, f["id"], "accepted", "Synthetic regression review")
        workflow.accept_stage(self.asset, stage, "Synthetic regression stage")

    def complete(self):
        for stage in STAGES:
            self.accept(stage)

    def test_complete_resume_and_final_approval(self):
        self.accept("proportions")
        self.assertEqual(workflow.status(str(self.asset))["current_stage"], "construction")
        for stage in STAGES[1:]:
            self.accept(stage)
        self.assertEqual(workflow.status(self.asset)["status"], "complete")
        record(self.asset, "Synthetic approval")
        self.assertEqual(approval_status(self.asset)["status"], "approved")
        saved=json.loads((self.out / "workflow.json").read_text())
        self.assertEqual(len(saved["stages"]), 4)
        self.assertFalse(list(self.out.glob(".workflow-*")))

    def test_cannot_skip_stages_or_unreviewed_features(self):
        with self.assertRaisesRegex(ValueError, "earlier"):
            workflow.accept_stage(self.asset, "appearance", "Review")
        with self.assertRaisesRegex(ValueError, "features"):
            workflow.accept_stage(self.asset, "proportions", "Review")
        with self.assertRaisesRegex(ValueError, "guided"):
            record(self.asset, "Premature approval")

    def test_repair_decision_invalidates_accepted_stages_and_approval(self):
        self.complete();record(self.asset, "Synthetic approval")
        workflow.review_feature(self.asset, "proportions-1", "repair", "Shape needs correction")
        state=workflow.status(self.asset)
        self.assertEqual(state["features"][0]["status"], "repair")
        self.assertEqual(state["stages"][0]["status"], "stale")
        self.assertEqual(approval_status(self.asset)["status"], "stale")

    def test_required_feature_cannot_be_waived(self):
        with self.assertRaisesRegex(ValueError, "cannot be waived"):
            workflow.review_feature(self.asset, "proportions-1", "waived", "Skip it")

    def test_optional_feature_can_be_waived_with_note(self):
        spec=read_spec(self.asset);spec["features"][0]["required"]=False;self.save_spec(spec);self.evidence()
        workflow.review_feature(self.asset, "proportions-1", "waived", "Not needed for this design")
        workflow.accept_stage(self.asset, "proportions", "Reviewed whole-model evidence")
        self.assertEqual(workflow.status(self.asset)["stages"][0]["status"], "accepted")

    def test_empty_notes_rejected(self):
        with self.assertRaises(ValueError):workflow.review_feature(self.asset, "proportions-1", "accepted", " ")
        with self.assertRaises(ValueError):workflow.accept_stage(self.asset, "proportions", " ")

    def test_source_edit_invalidates_even_when_export_unchanged(self):
        self.complete();record(self.asset, "Synthetic approval")
        path=self.asset / "gen.py";path.write_text(path.read_text()+"\n# changed design\n")
        self.assertEqual(workflow.status(self.asset)["features"][0]["status"], "stale")
        self.assertEqual(approval_status(self.asset)["status"], "stale")

    def test_export_edit_invalidates_all_acceptance(self):
        self.complete();(self.out / "model.glb").write_bytes(b"changed export")
        self.assertEqual(workflow.status(self.asset)["stages"][0]["status"], "stale")

    def test_tampered_or_missing_image_cannot_be_accepted(self):
        feature=read_spec(self.asset)["features"][0]
        index=json.loads(self.index.read_text());shot=next(s for s in index["shots"] if s["feature_id"]==feature["id"])
        path=self.asset / shot["file"];path.write_bytes(b"tampered")
        self.assertEqual(workflow.status(self.asset)["next_command"], "lowpoly ASSET review")
        with self.assertRaisesRegex(ValueError,"Missing current"):
            workflow.review_feature(self.asset,feature["id"],"accepted","Review")
        path.unlink()
        with self.assertRaises(ValueError):workflow.review_feature(self.asset,feature["id"],"accepted","Review")

    def test_tampered_review_after_acceptance_becomes_stale(self):
        self.accept("proportions")
        index=json.loads(self.index.read_text());shot=next(s for s in index["shots"] if s["feature_id"]=="proportions-1")
        (self.asset / shot["file"]).write_bytes(b"tampered")
        self.assertEqual(workflow.status(self.asset)["features"][0]["status"], "stale")

    def test_wrong_feature_node_binding_cannot_be_accepted(self):
        index=json.loads(self.index.read_text())
        for shot in index["shots"]:
            if shot["feature_id"]=="proportions-1":shot["nodes"]=["OtherMesh"]
        self.index.write_text(json.dumps(index))
        with self.assertRaises(ValueError):workflow.review_feature(self.asset,"proportions-1","accepted","Review")

    def test_failed_or_stale_checks_block_construction(self):
        self.accept("proportions")
        workflow.review_feature(self.asset,"construction-1","accepted","Synthetic review")
        (self.out / "check.json").write_text(json.dumps([dict(ok=False,text="Gap")]))
        with self.assertRaisesRegex(ValueError,"failures"):workflow.accept_stage(self.asset,"construction","Review")
        self.evidence();(self.out / "check-meta.json").write_text('{}')
        with self.assertRaisesRegex(ValueError,"stale"):workflow.accept_stage(self.asset,"construction","Review")

    def test_missing_declared_pose_blocks_motion_stage(self):
        spec=read_spec(self.asset);spec["poses"]={"stress":{"Crate":[0,0,0]}};self.save_spec(spec);self.evidence()
        index=json.loads(self.index.read_text());index["shots"]=[s for s in index["shots"] if s["pose"]!="stress"]
        self.index.write_text(json.dumps(index))
        for stage in STAGES[:3]:self.accept(stage)
        workflow.review_feature(self.asset,"motion-export-1","accepted","Synthetic review")
        with self.assertRaisesRegex(ValueError,"stress"):workflow.accept_stage(self.asset,"motion-export","Review")

    def test_additional_evidence_is_bound_and_contained(self):
        self.complete()
        p=self.out / "runtime.png";Image.new("RGB",(16,16),"red").save(p)
        workflow.accept_stage(self.asset,"motion-export","Runtime review",["out/runtime.png"])
        self.assertEqual(workflow.status(self.asset)["status"], "complete")
        p.write_bytes(b"changed")
        self.assertEqual(workflow.status(self.asset)["stages"][-1]["status"], "stale")
        with self.assertRaises(ValueError):workflow.accept_stage(self.asset,"motion-export","Review",["../outside.png"])
        with self.assertRaises(ValueError):workflow.accept_stage(self.asset,"motion-export","Review",["out/workflow.json"])

    def test_skinned_export_requires_separate_deformation_evidence(self):
        (self.out / "skinned.glb").write_bytes(b"synthetic skin");self.evidence()
        for stage in STAGES[:3]:self.accept(stage)
        workflow.review_feature(self.asset,"motion-export-1","accepted","Synthetic review")
        with self.assertRaisesRegex(ValueError,"deformation evidence"):
            workflow.accept_stage(self.asset,"motion-export","Review")
        (self.out / "pose.png").write_bytes(b"synthetic posed screenshot")
        workflow.accept_stage(self.asset,"motion-export","Inspected separate deformation evidence",["out/pose.png"])
        self.assertEqual(workflow.status(self.asset)["status"],"complete")

    def test_generated_reference_cannot_be_claimed_as_observed(self):
        Image.new("RGB",(16,16),"green").save(self.asset / "ref/generated.png")
        spec=read_spec(self.asset);spec["references"]=[dict(path="ref/generated.png",source="generated")]
        spec["features"][0].update(basis="observed",evidence=[dict(path="ref/generated.png")]);self.save_spec(spec)
        with self.assertRaisesRegex(ValueError,"cannot establish"):read_spec(self.asset)

    def test_original_reference_crop_and_changes_invalidate_review(self):
        p=self.asset / "ref/front.png";Image.new("RGB",(20,20),"green").save(p)
        spec=read_spec(self.asset);spec["references"]=[dict(path="ref/front.png",source="original")]
        spec["features"][0].update(basis="observed",evidence=[dict(path="ref/front.png",box=[2,2,18,18])]);self.save_spec(spec);self.evidence()
        self.accept("proportions")
        Image.new("RGB",(20,20),"red").save(p)
        self.assertEqual(workflow.status(self.asset)["features"][0]["status"],"stale")

    def test_feature_schema_rejects_invalid_links_and_crops(self):
        baseline=read_spec(self.asset)
        for update in (dict(id="../unsafe"),dict(nodes=[]),dict(views=["unknown"]),dict(poses=["unknown"]),
                       dict(output="out/missing.glb"),dict(evidence=[dict(path="../outside.png")]),dict(required="yes")):
            spec=json.loads(json.dumps(baseline));spec["features"][0].update(update);self.save_spec(spec)
            with self.subTest(update=update),self.assertRaises(ValueError):read_spec(self.asset)
        self.save_spec(baseline)
        Image.new("RGB",(20,20)).save(self.asset / "ref/front.png")
        baseline["references"]=[dict(path="ref/front.png",source="original")]
        baseline["features"][0].update(basis="observed",evidence=[dict(path="ref/front.png",box=[0,0,30,30])]);self.save_spec(baseline)
        with self.assertRaisesRegex(ValueError,"exceeds"):read_spec(self.asset)

    def test_review_and_checks_cannot_hide_an_old_build(self):
        p=self.asset / "gen.py";p.write_text(p.read_text()+"\n# changed geometry\n")
        # Simulate refreshed renders/checks, without rebuilding the old exported mesh.
        cache=self.asset / ".workshop/build.json";old=cache.read_bytes()
        self.evidence();cache.write_bytes(old)
        with self.assertRaisesRegex(ValueError,"Build evidence is stale"):
            workflow.review_feature(self.asset,"proportions-1","accepted","Review")
        self.assertEqual(workflow.status(self.asset)["next_command"],"lowpoly ASSET build")

    def test_feature_regions_are_output_specific(self):
        spec=read_spec(self.asset)
        self.assertEqual(len(regions(spec,"out/model.glb")),4)
        self.assertEqual(regions(spec,"out/other.glb"),[])

    def test_cli_and_page_show_guided_state(self):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):main([str(self.asset),"workflow","next"])
        self.assertEqual(json.loads(stream.getvalue())["status"],"in-progress")
        from lowpoly_workshop.kit.page import build_page
        path=build_page(self.asset);manifest=json.loads((path.parent / "manifest.json").read_text())
        self.assertEqual(len(manifest["workflow"]["features"]),4)
        self.assertFalse(any(s["stale"] for s in manifest["shots"]))
        self.assertIn("guided-review",path.read_text(encoding="utf-8"))

    def test_legacy_project_remains_usable_without_guided_mode(self):
        path=create(Path(self.tmp.name) / "legacy")
        (path / "out").mkdir();(path / "out/model.glb").write_bytes(b"legacy export")
        self.assertEqual(workflow.status(path)["status"],"disabled")
        record(path,"Legacy review");self.assertEqual(approval_status(path)["status"],"approved")
