import json,tempfile,unittest
from pathlib import Path
from lowpoly_workshop.templates import create
from lowpoly_workshop.spec import read_spec

class PalettePolicyTests(unittest.TestCase):
    def project(self,root):
        folder=create(Path(root)/'palette');path=folder/'asset.json'
        return folder,path,json.loads(path.read_text())
    def test_vertex_palette_is_explicit_and_mask_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s=self.project(tmp);out=s['outputs'][0];out.pop('kit_mask');out['vertex_surfaces']={'body':'painted_body'};out['runtime_uv']=True;path.write_text(json.dumps(s))
            self.assertTrue(read_spec(folder)['outputs'][0]['runtime_uv'])
    def test_mask_and_vertex_palette_are_incompatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s=self.project(tmp);s['outputs'][0]['vertex_surfaces']={'body':'paint'};path.write_text(json.dumps(s))
            with self.assertRaises(ValueError):read_spec(folder)
    def test_runtime_uv_requires_vertex_palette(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s=self.project(tmp);s['outputs'][0]['runtime_uv']=True;path.write_text(json.dumps(s))
            with self.assertRaises(ValueError):read_spec(folder)
    def test_empty_mapping_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s=self.project(tmp);s['outputs'][0]['vertex_surfaces']={};path.write_text(json.dumps(s))
            with self.assertRaises(ValueError):read_spec(folder)
    def test_view_distance_must_be_finite_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s=self.project(tmp);s['outputs'][0]['contract']['view_m']=-1;path.write_text(json.dumps(s))
            with self.assertRaises(ValueError):read_spec(folder)
