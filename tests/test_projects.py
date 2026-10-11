import unittest,tempfile,json,hashlib,io,base64,zipfile,struct
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from lowpoly_workshop.templates import create
from lowpoly_workshop.spec import KINDS,read_spec,local_path
from lowpoly_workshop.kit.asset import Asset
from lowpoly_workshop.kit.mesh import triangles
from lowpoly_workshop.quality import topology,check_relations
from lowpoly_workshop.references import plan,register,run,openai_edit
from lowpoly_workshop.runner import fingerprint,build
from lowpoly_workshop.approval import record,status
from lowpoly_workshop.distribution import package_asset,release
from lowpoly_workshop.kit.glb import load_glb

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.asset=create(self.root/'project','static-prop')
    def save(self,s): (self.asset/'asset.json').write_text(json.dumps(s))
    def test_all_templates_closed_and_relations(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                p=create(self.root/kind,kind);a=Asset(p);nodes=a.build()
                for n in a.spec['outputs'][0]['contract']['closed']:
                    t=topology(triangles({n:nodes[n]})[0]);self.assertFalse(any(t[k] for k in ('boundary_edges','nonmanifold_edges','winding_edges','duplicates','degenerate')),f'{n}: {t}')
                rows=[];check_relations(nodes,a.spec['relations'],a.spec['poses'],lambda ok,*_:rows.append(ok));self.assertTrue(all(rows))
    def test_nonempty_destination_refused(self):
        before=(self.asset/'gen.py').read_bytes()
        with self.assertRaises(ValueError):create(self.asset)
        self.assertEqual((self.asset/'gen.py').read_bytes(),before)
    def test_escape_rejected(self):
        for value in ('../outside','/outside','C:/outside','C:outside'):
            with self.subTest(value=value),self.assertRaises(ValueError):local_path(self.asset,value)
    def test_output_escape_rejected(self):
        s=read_spec(self.asset);s['outputs'][0]['file']='../bad.glb';self.save(s)
        with self.assertRaises(ValueError):read_spec(self.asset)
    def test_unsafe_name_rejected(self):
        s=read_spec(self.asset);s['name']='../../bad';self.save(s)
        with self.assertRaises(ValueError):read_spec(self.asset)
    def test_schema_version_required(self):
        s=read_spec(self.asset);s['schema_version']=1;self.save(s)
        with self.assertRaises(ValueError):read_spec(self.asset)
    def test_changed_source_invalidates_fingerprint(self):
        first=fingerprint(self.asset);p=self.asset/'gen.py';p.write_text(p.read_text()+'\n# edit\n');self.assertNotEqual(first,fingerprint(self.asset))
    def test_output_does_not_invalidate_fingerprint(self):
        first=fingerprint(self.asset);(self.asset/'out').mkdir();(self.asset/'out/a').write_text('output');self.assertEqual(first,fingerprint(self.asset))
    def test_cache_checks_companion_hashes(self):
        exe=self.root/'blender.exe';exe.write_text('fake executable');calls=[]
        def fake(*args):
            calls.append(args);d=self.asset/'out';d.mkdir(exist_ok=True)
            for name in ('model.glb','model.blend','model_atlas.png','kit_mask.png'):(d/name).write_bytes(b'output')
        with patch('lowpoly_workshop.pipeline.find_blender',return_value=str(exe)),patch('lowpoly_workshop.pipeline.blender',side_effect=fake):
            self.assertTrue(build(self.asset));self.assertFalse(build(self.asset));(self.asset/'out/kit_mask.png').write_bytes(b'tampered');self.assertTrue(build(self.asset));self.assertEqual(len(calls),2)
    def test_approval_expires_when_export_changes(self):
        (self.asset/'out').mkdir();p=self.asset/'out/model.glb';p.write_bytes(b'first');record(self.asset,'Reviewed by artist');self.assertEqual(status(self.asset)['status'],'approved');p.write_bytes(b'second');self.assertEqual(status(self.asset)['status'],'stale')
    def test_asset_bundle_hashes_and_relative_paths(self):
        (self.asset/'.env').write_text('PRIVATE_TOKEN=example');p=package_asset(self.asset)
        with zipfile.ZipFile(p) as z:
            self.assertFalse(any('.env' in n for n in z.namelist()));m=json.loads(z.read('manifest.json'))
            for n,h in m['files'].items():self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),h);self.assertFalse(Path(n).is_absolute())
            self.assertIn('toolkit/lowpoly_workshop/viewer/vendor/LICENSE',z.namelist());self.assertIn('toolkit/LICENSE',z.namelist())
    def test_source_release_manifest(self):
        p=release(self.root/'release.zip')
        with zipfile.ZipFile(p) as z:
            m=json.loads(z.read('Lowpoly-Workshop/RELEASE-MANIFEST.json'))
            for n,h in m['files'].items():self.assertEqual(hashlib.sha256(z.read(n)).hexdigest(),h)
            self.assertFalse(any('.egg-info' in n or '__pycache__' in n for n in z.namelist()))
            self.assertIn('Lowpoly-Workshop/lowpoly_workshop/viewer/vendor/build/three.core.js',z.namelist())
            self.assertIn('Lowpoly-Workshop/lowpoly_workshop/viewer/vendor/build/three.module.js',z.namelist())
        self.assertEqual(p.with_suffix('.zip.sha256').read_text().split()[0],hashlib.sha256(p.read_bytes()).hexdigest())
    def test_nested_output_folder_excludes_generated_files(self):
        s=read_spec(self.asset);s['out_dir']='build/models';s['outputs'][0]['file']='build/models/model.glb';self.save(s)
        before=fingerprint(self.asset);d=self.asset/'build/models';d.mkdir(parents=True);(d/'model.glb').write_bytes(b'export')
        self.assertEqual(before,fingerprint(self.asset));p=package_asset(self.asset)
        with zipfile.ZipFile(p) as z:self.assertFalse(any(n.endswith('.zip') for n in z.namelist()))
    def test_outputs_cannot_live_in_source_tree(self):
        s=read_spec(self.asset);s['outputs'][0]['file']='model.glb';self.save(s)
        with self.assertRaises(ValueError):read_spec(self.asset)
    def test_generator_reloads_changed_source(self):
        first=Asset(self.asset).build()['Crate']['faces'][0][0].copy()
        p=self.asset/'gen.py';p.write_text(p.read_text().replace('(.4,.5,.3)','(.8,.5,.3)'))
        second=Asset(self.asset).build()['Crate']['faces'][0][0]
        self.assertFalse((first==second).all())
    def test_page_marks_old_checks_stale(self):
        from lowpoly_workshop.kit.page import build_page
        from lowpoly_workshop.approval import export_hashes
        d=self.asset/'out';d.mkdir();(d/'model.glb').write_bytes(b'first')
        (d/'check.json').write_text(json.dumps([dict(ok=True,text='check passed')]))
        (d/'check-meta.json').write_text(json.dumps(dict(exports=export_hashes(self.asset),source=fingerprint(self.asset))))
        page=build_page(self.asset);manifest=page.parent/'manifest.json';self.assertEqual(len(json.loads(manifest.read_text())['checks']),1)
        (d/'model.glb').write_bytes(b'changed');build_page(self.asset);self.assertFalse(json.loads(manifest.read_text())['checks'][0]['ok'])
    def test_truncated_glb_rejected(self):
        p=self.root/'bad.glb';p.write_bytes(b'glTF')
        with self.assertRaises(ValueError):load_glb(p)
    def test_wrong_glb_length_rejected(self):
        p=self.root/'bad.glb';p.write_bytes(struct.pack('<III',0x46546c67,2,100))
        with self.assertRaises(ValueError):load_glb(p)

class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.asset=create(self.root/'asset')
        p=self.asset/'ref/front.png';Image.new('RGB',(32,32),(100,80,70)).save(p);self.original=p.read_bytes()
        s=read_spec(self.asset);s['references']=[dict(path='ref/front.png',source='original',view='front')];(self.asset/'asset.json').write_text(json.dumps(s));self.png=io.BytesIO();Image.new('RGB',(16,16),'green').save(self.png,format='PNG')
    def test_missing_views_only(self):
        _,jobs=plan(self.asset,['front','back']);self.assertEqual([j['view'] for j in jobs],['back'])
    def test_register_keeps_original_and_provenance(self):
        _,jobs=plan(self.asset,['back']);p=register(self.asset,jobs[0],self.png.getvalue(),'mock','image-model');self.assertTrue(p.exists());self.assertEqual((self.asset/'ref/front.png').read_bytes(),self.original)
        r=read_spec(self.asset)['references'][-1];self.assertTrue(r['inferred']);self.assertEqual(r['review_status'],'pending');self.assertEqual(r['sha256'],hashlib.sha256(p.read_bytes()).hexdigest());self.assertEqual(plan(self.asset,['back'])[1],[])
    def test_changed_original_refused(self):
        _,jobs=plan(self.asset,['back']);Image.new('RGB',(32,32),'red').save(self.asset/'ref/front.png')
        with self.assertRaises(ValueError):register(self.asset,jobs[0],self.png.getvalue(),'mock')
    def test_duplicate_generated_view_refused(self):
        _,jobs=plan(self.asset,['back']);register(self.asset,jobs[0],self.png.getvalue(),'mock')
        with self.assertRaises(ValueError):register(self.asset,jobs[0],self.png.getvalue(),'mock')
    def test_provider_multipart_and_image_decode(self):
        response=io.BytesIO(json.dumps({'data':[{'b64_json':base64.b64encode(self.png.getvalue()).decode()}]}).encode())
        seen=[]
        def request(req,timeout):seen.append(req);self.assertEqual(timeout,240);return response
        result=openai_edit([self.asset/'ref/front.png'],'back view','explicit-model','mock-key',request=request)
        self.assertEqual(result,self.png.getvalue());self.assertEqual(seen[0].full_url,'https://api.openai.com/v1/images/edits');self.assertIn(b'name="image[]"',seen[0].data);self.assertIn(b'explicit-model',seen[0].data)
    def test_run_bounded_and_resumable(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'mock'}),patch('lowpoly_workshop.references.openai_edit',return_value=self.png.getvalue()) as mock:
            self.assertEqual(len(run(self.asset,'explicit-model',1)),1);self.assertEqual(mock.call_count,1);self.assertEqual(len(run(self.asset,'explicit-model',1)),1);self.assertEqual(mock.call_count,2)
    def test_provider_not_called_without_model(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'mock'}),patch('lowpoly_workshop.references.openai_edit') as mock:
            with self.assertRaises(ValueError):run(self.asset,None)
            mock.assert_not_called()
