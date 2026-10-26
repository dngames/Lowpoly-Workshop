"""Blender entry point: clay/textured exported views with the reference's right-side convention.

blender -b --factory-startup --python scripts/render_building_reference.py -- PROJECT
This only changes review cameras; geometry comes from the project's actual GLBs.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lowpoly_workshop.kit.blender import review
original_setup=review.setup
def setup(scene):
    result=original_setup(scene)
    scene.view_settings.exposure=-.5
    return result
review.setup=setup
review.VIEWS.update(front=(0,10),side=(90,10),quarter=(35,18),top=(0,85))
if __name__=='__main__':review.main()
