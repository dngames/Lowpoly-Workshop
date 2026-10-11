# gen.py: the generator

A generator is plain Python (numpy only, so it also runs inside Blender) that builds the asset from
parameters. Faces are kept in world coordinates of the rest pose; each node has a pivot (its joint).

```python
import os, sys
sys.path.insert(0, os.environ.get("LOWPOLY_KIT_SCRIPTS", "<kit>/scripts"))   # the template sets this
from kit.atlas import Atlas, image_decal, rgb
from kit.mesh import X, Y, Z, Mesh, tube, sweep, loft, hexa, ring, nrm, newell

CELLS = {                       # name: (sRGB hex, kit channel "R"/"G"/"B" or None[, decal name])
    "frame": ("#3daa4a", "R"),
    "tyre": ("#3b3842", None),
    "reflector": ("#2b2833", None, "reflector"),
}
ATLAS = Atlas(CELLS, decals={"reflector": ((256, 128), paint_reflector)})

def params(variant=None, overrides=None):  -> dict      # all numbers in metres / degrees
def build(p) -> {name: {"parent": str|None, "pivot": np.array(3), "faces": [...], "rot": 3x3 (optional)}}
```

Order nodes parents-first. `rot` is a rest rotation (only when the game rotates a node about a tilted
axis, e.g. a raked steering axis: local +Y = the axis). Everything else rests at identity.

## Optional hooks
| hook | used by | returns |
|---|---|---|
| `extras(p, scale)` | build | `{node: {key: value}}` written as glTF extras (mount points, sockets) |
| `clips(nodes, p)` | build (output `"clips": true`) | `{name: {"fps": 24, "frames": [pose, ...]}}` |
| `fit_extra(set, view)` | fit | `{"init": [...], "steps": [...], "limits": [[lo, hi], ...]}` extra fit parameters |
| `fit_scene(set, view, extra, asset)` | fit, render | `(nodes, pose)` the view shows; may merge another asset's nodes |
| `show_scenes(asset)` | render show | `{name: (nodes, pose, focus or None)}` hand-over shots |
| `extra_checks(asset, report)` | check | calls `report(ok, text, detail)` for asset-specific rules |

`asset.build(variant, scale)` is the cached way to get nodes inside hooks (it also tags each node with
its atlas, which matters when a scene mixes two assets).

## Primitives (kit.mesh)
All take a `Mesh` `m`, add faces with a cell name, and orient faces outward automatically.
- `tube(m, p0, p1, r0, r1=None, n=8, cell, caps=(False, False), up=Y, rx=None, rx1=None, top={k: cell}, thin=False)`
  prism between two points; `r` along `up`, `rx` across; `n=4` gives a rotated square (divide by 0.7071
  for a box of half-size r); `top` recolours facet k (a highlight line).
- `sweep(m, points, radii, n=6, cell, caps)` tube along a polyline with mitred joints (bars, bent tubes).
- `loft(m, rings, cells, caps)` skin between rings of equal size (saddles, shoes, bottles, torsos).
- `hexa(m, centre, axes, half, cell, skip=("+y",), cells={face: cell}, uvs={face: uv})` box.
- `ring(c, d, u, w, rx, ry, n)` points of an ellipse; `nrm`, `basis`, `newell`, `zy([z, y])`.
- `m.face(points, cell, inside_point, uv=None, thin=False)` any polygon; `uv` in 0..1 for decal cells.
- `kit.mesh.scaled(nodes, k)`, `triangles(nodes)`, `tri_count(node)`.

Typical budgets: tyre 16-20 sides x 4-6 section; tubes 6-8 sides; limbs 6; heads 8-10 x 7 rings.
Remove faces nobody sees (tube ends inside other tubes, the inside of a tyre behind its rim).

## Atlas and decals (kit.atlas)
Flat cells pack into a grid of 88 px squares with 8 px padding; decals shelf-pack below (or pin them
with `rects=`). A decal painter `paint(col, kit, rect, atlas)` draws into the colour array and may set
kit channels. `image_decal(npy, kit_rules)` stretches a quantized image (faces, printed shirts, helmet
stripes made with `kit.sheets.quantize`). The kit mask is painted from the same layout: R main colour,
G accent, B third colour; the game recolours by it.

## Rigs, poses and clips (kit.rig)
A pose is `{node: [rx, ry, rz] degrees or 3x3, "_root_t": [x, y, z], "_root_for": ["Hips"]}`: rotations
about each node's pivot in world-aligned axes, relative to the parent's posed frame. Characters are
rigid nodes (no skinning): limbs rotate at joints like the bike's parts, which is cheap, stable and
matches the low-poly look. `two_bone(A, B, C, target, pole)` and `frame_rot(...)` solve a two-segment
limb between a root and a target. `clips()` returns per-frame
poses; the builder keys them on NLA tracks and exports one glTF animation per clip, plus a one-frame
"Stand" clip that keeps the file's rest pose at identity.

## Making two things fit together
Put named contact points on the host as extras and
let the dependent asset read them through the host's generator (`load_gen("../host/gen.py")`). Check
the result on the exported files with `extra_checks`, sampling the complete supported motion.

For smooth surfaces, a node may set `"smooth": True`. The builder and preview preserve smooth corner normals across connected edges and omit preview outlines when every node requests smoothing. Triangle counts are unchanged.


## Closed shoulders and elbows (required for organic characters)

Use `kit.organic.closed_limb(m, points, radii, n=5, cells=['shirt','skin','skin'])` for a
shoulder/sleeve, elbow and wrist path. It shares every bend ring and caps both ends; the two
caps cost only `2*(n-2)` triangles. Recess the first point inside the torso, preserve the
contract shoulder pivot, and overlap the wrist with the hand. Use the same pattern for legs.
The returned face list is the limb shell, excluding hand and carried props. Report
`closed_surface(shell)` from `extra_checks` to catch missing end caps or open bends. Also
sample the full animation range: the root stays in the torso and the hand/props clear the head.
This rule applies to all new character assets; smooth shading is the default for organic forms.
Run `python scripts/test_organic.py` to verify the helper without Blender.


For skinned riders, use either shared rings with identical skin weights, or separately capped,
overlapping parts that stay connected throughout animation. Never weld across independent
rigid bone weights. Preserve any joint caps needed when the parts rotate. Audit shoulders,
elbows, hips and knees in straight and deeply bent poses before removing hidden faces.

### Rigid rider cleanup and leg-band seams

Call `kit.character_cleanup.finish_character(nodes)` before export coordinate conversion.
It joins matching limb-band rings at the same station (same rigid bone) without adding
triangles, caps remaining planar leg ends, and conservatively removes fully buried faces.
A face can be removed only inside another closed solid within the SAME rigid node. Every
vertex must be strictly inside and the entire face must not intersect the enclosing surface;
checking vertices alone fails for concave bodies. Independently moving parts and removable
accessories must never serve as occluders. Joint-part caps are retained. The small ring
alignment is valid for rigid single-bone parts; do not apply it across different skin weights.

Use declared contact relations and stress poses to inspect joint attachment across motion.
Run `test_character_cleanup.py` to cover buried geometry, independent bones, colour-band
seams and concave occluders.


### Hands and feet supporting held props

Inspect the consuming runtime's animation conventions before exporting a character with held props.
A hand gripping a fixed handle or a foot standing on a platform must remain attached to its support.
Use explicit parent relationships and separate moving and stationary parts. Preserve authored
joint origins and closed continuous limb shells; animate only the intended parts. Audit support
contacts at rest and throughout the supported range. Keep caps wherever movement can expose them.
