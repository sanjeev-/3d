"""Integration checks that require a real Blender.

Not collected by plain pytest (see ../conftest.py) — bpy only exists inside
Blender, and Blender ships its own Python. Run with:

    blender --background --python marionette/tests/blender/test_bpy_integration.py

Blender's bundled Python has no pydantic. Point MARIONETTE_DEPS at a directory
holding it, e.g.:

    /Applications/Blender.app/Contents/Resources/5.1/python/bin/python3.13 \
        -m pip install --target=/tmp/bdeps pydantic pyyaml
    MARIONETTE_DEPS=/tmp/bdeps blender --background --python <this file>
"""

import os
import sys
import traceback
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "marionette" / "src"))
_deps = os.environ.get("MARIONETTE_DEPS")
if _deps:
    sys.path.insert(0, _deps)

import bpy

results = []
def check(name, fn):
    try:
        fn(); results.append(("PASS", name, ""))
    except Exception as e:
        results.append(("FAIL", name, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))

from marionette.configs import LightConfig, LightType, HDRIConfig
from marionette.lighting import Light, clear_lights
from marionette.rigs import ThreePointRig, ArcRig, DirectionProxyRig, HDRIRig, SceneBounds
from marionette.shading import NodeGraph
from marionette.shading.graph import OWNER_PROP
from marionette.looks import LookPipeline, PBRLook, PBRParams, get_look

def t_light_create():
    clear_lights()
    lt = Light.create(LightConfig(name="TestKey", type=LightType.AREA, energy=250.0,
                                  location=(1,2,3), rotation=(90,0,0), size=0.5))
    assert lt.obj.name == "TestKey", lt.obj.name
    assert lt.data.type == "AREA"
    assert abs(lt.energy - 250.0) < 1e-6
    assert abs(lt.obj.location.x - 1.0) < 1e-6
    assert abs(lt.rotation[0] - 90.0) < 1e-4, lt.rotation
check("Light.create applies config", t_light_create)

def t_light_keyframe():
    clear_lights()
    lt = Light.create(LightConfig(name="Anim"))
    lt.location = (0,0,0); lt.keyframe("location", frame=1)
    lt.location = (5,0,0); lt.keyframe("location", frame=10)
    assert lt.obj.animation_data.action is not None
check("Light animates via Animatable mixin", t_light_keyframe)

def t_clear_lights():
    Light.create(LightConfig(name="A")); Light.create(LightConfig(name="B"))
    n = clear_lights()
    assert n >= 2, n
    assert [o for o in bpy.data.objects if o.type=='LIGHT'] == []
check("clear_lights removes all lights", t_clear_lights)

def t_three_point():
    clear_lights()
    lights = ThreePointRig(key_energy=800.0).apply(bounds=SceneBounds(extent=2.0))
    assert len(lights) == 3, len(lights)
    assert {l.obj.name for l in lights} == {"Key","Fill","Rim"}
check("ThreePointRig.apply creates 3 lights", t_three_point)

def t_arc_keyframes():
    clear_lights()
    lights = ArcRig(axis="x", num_frames=5).apply(bounds=SceneBounds(extent=2.0))
    from marionette.mixins import iter_fcurves
    fc = list(iter_fcurves(lights[0].obj.animation_data.action))
    kf = max(len(c.keyframe_points) for c in fc)
    assert kf == 5, kf
    xs = sorted(p.co.y for p in [c for c in fc if c.data_path=='location'][0].keyframe_points)
    assert xs[0] < xs[-1], "arc must actually move the light in X"
check("ArcRig keyframes the sweep", t_arc_keyframes)

def t_direction_proxy():
    clear_lights()
    lights = DirectionProxyRig().apply(bounds=SceneBounds())
    l = lights[0]
    assert l.data.type == "SUN" and l.energy == 0.0
    assert abs(l.obj.rotation_euler[0] - 0.7853981) < 1e-4, l.obj.rotation_euler[0]
check("DirectionProxyRig matches zen sun rotation", t_direction_proxy)

# --- NodeGraph ---------------------------------------------------------------
def _fresh_world():
    w = bpy.data.worlds.new("GraphTest"); w.use_nodes = True
    return w

def t_graph_build():
    w = _fresh_world()
    g = NodeGraph("test.build")
    env = g.node("ShaderNodeTexEnvironment", "env")
    bg = g.node("ShaderNodeBackground", "bg", inputs={"Strength": 4.0})
    out = g.node("ShaderNodeOutputWorld", "out", adopt=True)
    g.link(env.out("Color"), bg.inp("Color"))
    g.link(bg.out("Background"), out.inp("Surface"))
    built = g.build(w.node_tree)
    assert abs(built["bg"].inputs["Strength"].default_value - 4.0) < 1e-6
    assert built["out"].inputs["Surface"].links[0].from_node == built["bg"]
check("NodeGraph.build wires nodes and defaults", t_graph_build)

def t_graph_idempotent():
    w = _fresh_world()
    def make():
        g = NodeGraph("test.idem")
        e = g.node("ShaderNodeTexEnvironment", "env")
        b = g.node("ShaderNodeBackground", "bg")
        o = g.node("ShaderNodeOutputWorld", "out", adopt=True)
        g.link(e.out("Color"), b.inp("Color")); g.link(b.out("Background"), o.inp("Surface"))
        return g
    make().build(w.node_tree); first = len(w.node_tree.nodes)
    make().build(w.node_tree); second = len(w.node_tree.nodes)
    make().build(w.node_tree); third = len(w.node_tree.nodes)
    assert first == second == third, (first, second, third)
    owned = [n for n in w.node_tree.nodes if n.get(OWNER_PROP) == "test.idem"]
    assert len(owned) == 2, len(owned)   # output was adopted, not owned
check("NodeGraph.build is idempotent across rebuilds", t_graph_idempotent)

def t_graph_adopt_preserves():
    w = _fresh_world()
    original_out = [n for n in w.node_tree.nodes if n.bl_idname=="ShaderNodeOutputWorld"][0]
    ptr = original_out.as_pointer()
    g = NodeGraph("test.adopt")
    b = g.node("ShaderNodeBackground", "bg")
    o = g.node("ShaderNodeOutputWorld", "out", adopt=True)
    g.link(b.out("Background"), o.inp("Surface"))
    built = g.build(w.node_tree)
    assert built["out"].as_pointer() == ptr, "adopt must reuse the user's output node"
check("NodeGraph adopts rather than duplicating output nodes", t_graph_adopt_preserves)

def t_graph_bad_socket():
    w = _fresh_world()
    g = NodeGraph("test.bad")
    b = g.node("ShaderNodeBackground", "bg")
    o = g.node("ShaderNodeOutputWorld", "out", adopt=True)
    g.link(b.out("NoSuchSocket"), o.inp("Surface"))
    from marionette.shading.graph import NodeGraphError
    try:
        g.build(w.node_tree)
    except NodeGraphError as e:
        assert "available" in str(e), str(e)
        return
    raise AssertionError("expected NodeGraphError for unknown socket")
check("NodeGraph raises a helpful error on unknown sockets", t_graph_bad_socket)

def t_graph_clear():
    w = _fresh_world()
    g = NodeGraph("test.clear")
    g.node("ShaderNodeBackground", "bg")
    g.build(w.node_tree)
    assert g.clear(w.node_tree) == 1
check("NodeGraph.clear removes owned nodes", t_graph_clear)

# --- HDRI --------------------------------------------------------------------
def t_hdri_rig():
    hdri = str(_REPO / "shared/assets/hdris/moonless_golf_4k.exr")
    import os
    assert os.path.exists(hdri), hdri
    sc = bpy.context.scene
    sc.world = bpy.data.worlds.new("HDRITest"); sc.world.use_nodes = True
    rig = HDRIRig(HDRIConfig(path=hdri, strength=2.5, rotation=45.0))
    rig.apply(sc)
    nodes = sc.world.node_tree.nodes
    env = [n for n in nodes if n.bl_idname=="ShaderNodeTexEnvironment"]
    assert len(env) == 1 and env[0].image is not None
    bg = [n for n in nodes if n.bl_idname=="ShaderNodeBackground"][0]
    assert abs(bg.inputs["Strength"].default_value - 2.5) < 1e-6
    before = len(nodes)
    rig.apply(sc)  # re-apply must not duplicate
    assert len(sc.world.node_tree.nodes) == before, (before, len(sc.world.node_tree.nodes))
check("HDRIRig builds world + is idempotent", t_hdri_rig)

def t_scene_set_hdri_compat():
    from marionette.scene import Scene
    hdri = str(_REPO / "shared/assets/hdris/moonless_golf_4k.exr")
    s = Scene()
    s.set_hdri(HDRIConfig(path=hdri, strength=1.5, rotation=10.0))
    bg = [n for n in s.scene.world.node_tree.nodes if n.bl_idname=="ShaderNodeBackground"][0]
    assert abs(bg.inputs["Strength"].default_value - 1.5) < 1e-6
check("Scene.set_hdri still works (backwards compatible)", t_scene_set_hdri_compat)

def t_scene_add_light():
    from marionette.scene import Scene
    s = Scene()
    clear_lights()
    lt = s.add_light(LightConfig(name="ViaScene", energy=42.0))
    assert lt.obj.name == "ViaScene" and abs(lt.energy-42.0) < 1e-6
    lights = s.apply_rig(ThreePointRig(), bounds=SceneBounds(extent=2.0))
    assert len(lights) == 3
check("Scene.add_light / Scene.apply_rig", t_scene_add_light)

# --- Look pipeline -----------------------------------------------------------
def t_pbr_look():
    sc = bpy.context.scene
    look = PBRLook(PBRParams(engine="CYCLES", samples=17, resolution=(640,360), view_transform="Standard"))
    res = LookPipeline(look).apply(sc)
    assert res.stages_run == list(__import__("marionette.looks", fromlist=["STAGES"]).STAGES), res.stages_run
    assert sc.render.engine == "CYCLES"
    assert sc.cycles.samples == 17
    assert (sc.render.resolution_x, sc.render.resolution_y) == (640,360)
    assert sc.view_settings.view_transform == "Standard"
check("PBRLook pipeline configures render", t_pbr_look)

def t_look_with_rig():
    clear_lights()
    sc = bpy.context.scene
    look = PBRLook(PBRParams(samples=8), rig=ThreePointRig(key_energy=123.0))
    res = LookPipeline(look).apply(sc)
    assert res.context.data.get("lighting") == "three_point", res.context.data
    assert len([o for o in bpy.data.objects if o.type=='LIGHT']) == 3
check("PBRLook drives a light rig", t_look_with_rig)

def t_look_validation_fails_loudly():
    from marionette.looks import LookRequirements, LookValidationError, Look
    class StrictLook(Look):
        name = "strict-test"
        requirements = LookRequirements(view_transform="ThisIsNotAViewTransform")
    try:
        LookPipeline(StrictLook()).apply(bpy.context.scene, strict=True)
    except LookValidationError as e:
        assert "view transform" in str(e), str(e)
        return
    raise AssertionError("strict validation should have raised")
check("Look validation refuses to run on unmet requirements", t_look_validation_fails_loudly)

def t_look_skip_stages():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    res = LookPipeline(get_look("pbr"), skip=("configure_render",)).apply(sc)
    assert "configure_render" in res.stages_skipped
    assert sc.render.engine == "BLENDER_EEVEE", "skipped stage must not run"
check("LookPipeline honors skipped stages", t_look_skip_stages)

def t_role_resolution_live():
    from marionette.shading import anime_character_roles, MaterialRole
    bpy.ops.wm.read_homefile(use_empty=True)
    for nm in ("5_face_x","5_hair_x","body out","7_faceLINES_x","5_body_x"):
        me = bpy.data.meshes.new(nm)
        bpy.context.collection.objects.link(bpy.data.objects.new(nm, me))
    resolved = anime_character_roles().resolve_scene(bpy.context.scene)
    assert resolved[MaterialRole.FACE] == ["5_face_x"], resolved[MaterialRole.FACE]
    assert resolved[MaterialRole.OUTLINE] == ["body out"], resolved[MaterialRole.OUTLINE]
    assert resolved[MaterialRole.LINEART] == ["7_faceLINES_x"], resolved[MaterialRole.LINEART]
check("RoleMap.resolve_scene against live objects", t_role_resolution_live)

print("\n" + "="*66)
for status, name, err in results:
    print(f"{status}  {name}")
    if err: print("      " + err.splitlines()[0])
failed = [r for r in results if r[0]=="FAIL"]
print("="*66)
print(f"{len(results)-len(failed)} passed, {len(failed)} failed")
for _, name, err in failed:
    print(f"\n--- {name} ---\n{err}")
sys.exit(1 if failed else 0)
