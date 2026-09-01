"""NodeGraph spec tests. Pure — these run without Blender."""

import pytest

from marionette.shading import NodeGraph
from marionette.shading.graph import NodeGraphError, OWNER_PROP


def test_nodes_and_links_are_recorded():
    g = NodeGraph("test.owner")
    env = g.node("ShaderNodeTexEnvironment", "env")
    bg = g.node("ShaderNodeBackground", "bg", inputs={"Strength": 2.0})
    g.link(env.out("Color"), bg.inp("Color"))

    assert g.node_count == 2
    assert g.link_count == 1
    assert g.spec("bg").inputs["Strength"] == 2.0


def test_auto_generated_keys_are_unique():
    g = NodeGraph("test.owner")
    a = g.node("ShaderNodeBackground")
    b = g.node("ShaderNodeBackground")
    assert a.key != b.key


def test_duplicate_key_rejected():
    g = NodeGraph("test.owner")
    g.node("ShaderNodeBackground", "bg")
    with pytest.raises(ValueError, match="duplicate node key"):
        g.node("ShaderNodeBackground", "bg")


def test_link_direction_is_validated():
    g = NodeGraph("test.owner")
    a = g.node("ShaderNodeBackground", "a")
    b = g.node("ShaderNodeBackground", "b")
    with pytest.raises(ValueError, match="source must be an output"):
        g.link(a.inp("Color"), b.inp("Color"))
    with pytest.raises(ValueError, match="destination must be an input"):
        g.link(a.out("Background"), b.out("Background"))


def test_link_to_unknown_node_rejected():
    g = NodeGraph("test.owner")
    a = g.node("ShaderNodeBackground", "a")
    from marionette.shading.graph import SocketRef

    with pytest.raises(KeyError):
        g.link(a.out("Background"), SocketRef("nope", "Color", False))


def test_set_is_chainable_and_records_defaults():
    g = NodeGraph("test.owner")
    n = g.node("ShaderNodeBackground", "bg")
    assert n.set("Strength", 3.0).set("Color", (1.0, 0.0, 0.0, 1.0)) is n
    assert g.spec("bg").inputs == {"Strength": 3.0, "Color": (1.0, 0.0, 0.0, 1.0)}


def test_empty_owner_rejected():
    with pytest.raises(ValueError):
        NodeGraph("")


def test_to_dict_is_serializable():
    import json

    g = NodeGraph("test.owner")
    env = g.node("ShaderNodeTexEnvironment", "env", image=lambda: "deferred-image")
    bg = g.node("ShaderNodeBackground", "bg", inputs={"Strength": 1.5})
    g.link(env.out("Color"), bg.inp("Color"))

    payload = g.to_dict()
    json.dumps(payload)  # must not raise

    assert payload["owner"] == "test.owner"
    assert {n["key"] for n in payload["nodes"]} == {"env", "bg"}
    # Callables are placeholders, not serialized values.
    env_node = next(n for n in payload["nodes"] if n["key"] == "env")
    assert env_node["props"]["image"] == "<deferred>"
    assert payload["links"] == [{"from": ["env", "Color"], "to": ["bg", "Color"]}]


def test_hdri_rig_builds_expected_graph_shape():
    from marionette.configs import HDRIConfig
    from marionette.rigs import HDRIRig

    rig = HDRIRig(HDRIConfig(path="/tmp/does-not-need-to-exist.hdr", strength=3.0, rotation=90.0))
    g = rig.build_graph()

    assert g.owner == HDRIRig.OWNER
    assert g.spec("background").inputs["Strength"] == 3.0
    # The world output is adopted, never owned, so we don't delete the user's.
    assert g.spec("output").adopt is True
    assert g.spec("env").adopt is False
    assert g.link_count == 4


def test_owner_prop_constant_is_stable():
    # Changing this silently orphans nodes from prior builds.
    assert OWNER_PROP == "marionette_owner"
