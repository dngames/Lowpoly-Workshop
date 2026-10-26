import sys, unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from lowpoly_workshop.blender_module import main

class BlenderModuleTests(unittest.TestCase):
    def fake(self):
        return SimpleNamespace(app=SimpleNamespace(background=True,version_string='4.5.test'),
            ops=SimpleNamespace(wm=SimpleNamespace(read_factory_settings=Mock())),
            context=SimpleNamespace(scene=SimpleNamespace(render=SimpleNamespace())))
    def test_thread_and_script_arguments_survive(self):
        bpy=self.fake();args=['launcher','-t','2','-b','--factory-startup','--python-exit-code','9','-P','task.py','--','asset']
        with patch.dict(sys.modules,bpy=bpy),patch.object(sys,'argv',args),patch('runpy.run_path') as run:
            self.assertEqual(main(),0)
            self.assertEqual(sys.argv[-2:],['--','asset'])
            run.assert_called_once_with('task.py',run_name='__main__')
        self.assertEqual(bpy.context.scene.render.threads,2)
        bpy.ops.wm.read_factory_settings.assert_called_once()
    def test_render_failure_uses_requested_exit_code(self):
        with patch.dict(sys.modules,bpy=self.fake()),patch.object(sys,'argv',['launcher','--python-exit-code','7','-P','task.py']),patch('runpy.run_path',side_effect=RuntimeError('render failed')),patch('traceback.print_exc'):
            self.assertEqual(main(),7)
    def test_unknown_flags_fail_instead_of_being_ignored(self):
        with patch.dict(sys.modules,bpy=self.fake()),patch.object(sys,'argv',['launcher','--unknown']),patch('traceback.print_exc'):
            self.assertEqual(main(),1)
