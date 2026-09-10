"""A declarative, idempotent builder for Blender node trees.

Node graphs are described as pure data — constructing one never imports bpy — so
specs can be unit-tested outside Blender and serialized across the Modal
boundary. ``build()`` is the only bpy-touching entry point.

Idempotency is the point. Every node the builder creates is tagged with an owner
key, and rebuilding removes the previously owned nodes first. That replaces the
get-or-create + remove-existing-link dance that hand-wired node code accumulates.

    graph = NodeGraph("marionette.hdri")
    env = graph.node("ShaderNodeTexEnvironment", "env")
    bg = graph.node("ShaderNodeBackground", "bg", inputs={"Strength": 2.0})
    out = graph.node("ShaderNodeOutputWorld", "out", adopt=True)
    graph.link(env.out("Color"), bg.inp("Color"))
    graph.link(bg.out("Background"), out.inp("Surface"))
    graph.build(world.node_tree)
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

#: Custom property stamped onto every node the builder creates.
OWNER_PROP = "marionette_owner"

SocketKey = Union[str, int]


class NodeGraphError(RuntimeError):
    """Raised when a graph cannot be built against a real node tree."""


@dataclass(frozen=True)
class SocketRef:
    """A reference to one socket on one node in the graph."""

    node_key: str
    socket: SocketKey
    is_output: bool


@dataclass
class NodeSpec:
    """Pure description of a single node."""

    key: str
    bl_idname: str
    props: Dict[str, Any] = field(default_factory=dict)
    inputs: Dict[SocketKey, Any] = field(default_factory=dict)
    adopt: bool = False


@dataclass(frozen=True)
class LinkSpec:
    """Pure description of one link between two sockets."""

    src: SocketRef
    dst: SocketRef


class NodeRef:
    """Handle returned by :meth:`NodeGraph.node`, used to name sockets."""

    __slots__ = ("_graph", "key", "bl_idname")

    def __init__(self, graph: "NodeGraph", key: str, bl_idname: str):
        self._graph = graph
        self.key = key
        self.bl_idname = bl_idname

    def out(self, socket: SocketKey) -> SocketRef:
        """Reference an output socket by name or index."""
        return SocketRef(self.key, socket, True)

    def inp(self, socket: SocketKey) -> SocketRef:
        """Reference an input socket by name or index."""
        return SocketRef(self.key, socket, False)

    def set(self, socket: SocketKey, value: Any) -> "NodeRef":
        """Record a default value for an input socket. Chainable."""
        self._graph.spec(self.key).inputs[socket] = value
        return self

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<NodeRef {self.key} {self.bl_idname}>"


class NodeGraph:
    """Builds a node tree from a declarative spec, idempotently."""

    def __init__(self, owner: str):
        if not owner:
            raise ValueError("NodeGraph requires a non-empty owner key")
        self.owner = owner
        self._specs: Dict[str, NodeSpec] = {}
        self._links: List[LinkSpec] = []
        self._auto = 0

    # -- spec construction (pure) ------------------------------------------

    def node(
        self,
        bl_idname: str,
        key: Optional[str] = None,
        *,
        adopt: bool = False,
        inputs: Optional[Dict[SocketKey, Any]] = None,
        **props: Any,
    ) -> NodeRef:
        """Declare a node.

        Args:
            bl_idname: Blender node type, e.g. ``"ShaderNodeBackground"``.
            key: Stable identifier within this graph. Auto-generated if omitted.
            adopt: Bind to a pre-existing node of this type rather than creating
                one. Use for output nodes the graph should not own or delete.
            inputs: Default values keyed by socket name or index.
            **props: Attributes assigned to the node at build time. A value may
                be a zero-arg callable, evaluated during ``build()`` — that is
                how bpy datablocks (images, node groups) enter a pure spec.
        """
        if key is None:
            self._auto += 1
            key = f"{bl_idname}_{self._auto}"
        if key in self._specs:
            raise ValueError(f"duplicate node key {key!r} in graph {self.owner!r}")

        self._specs[key] = NodeSpec(
            key=key,
            bl_idname=bl_idname,
            props=dict(props),
            inputs=dict(inputs or {}),
            adopt=adopt,
        )
        return NodeRef(self, key, bl_idname)

    def link(self, src: SocketRef, dst: SocketRef) -> "NodeGraph":
        """Declare a link from an output socket to an input socket."""
        if not src.is_output:
            raise ValueError("link source must be an output socket (use .out(...))")
        if dst.is_output:
            raise ValueError("link destination must be an input socket (use .inp(...))")
        for ref in (src, dst):
            if ref.node_key not in self._specs:
                raise KeyError(f"unknown node key {ref.node_key!r} in graph {self.owner!r}")
        self._links.append(LinkSpec(src, dst))
        return self

    def spec(self, key: str) -> NodeSpec:
        """Return the NodeSpec registered under ``key``."""
        return self._specs[key]

    @property
    def node_count(self) -> int:
        return len(self._specs)

    @property
    def link_count(self) -> int:
        return len(self._links)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the graph. Callable props are reported as ``"<deferred>"``."""

        def encode(value: Any) -> Any:
            if callable(value):
                return "<deferred>"
            if isinstance(value, tuple):
                return list(value)
            return value

        return {
            "owner": self.owner,
            "nodes": [
                {
                    "key": s.key,
                    "bl_idname": s.bl_idname,
                    "adopt": s.adopt,
                    "props": {k: encode(v) for k, v in s.props.items()},
                    "inputs": {str(k): encode(v) for k, v in s.inputs.items()},
                }
                for s in self._specs.values()
            ],
            "links": [
                {
                    "from": [l.src.node_key, l.src.socket],
                    "to": [l.dst.node_key, l.dst.socket],
                }
                for l in self._links
            ],
        }

    # -- realization (bpy) --------------------------------------------------

    def build(self, tree, clear_others: bool = False) -> Dict[str, Any]:
        """Realize this graph onto ``tree``, replacing anything it owned before.

        Args:
            clear_others: Also remove nodes this graph neither owns nor adopts.
                Use when the graph defines the tree's entire output — otherwise
                a pre-existing shader is merely disconnected, not removed, and
                lingers as a confusing orphan.

        Returns a mapping of node key -> created/adopted bpy node.
        """
        nodes = tree.nodes
        links = tree.links

        # Drop what a previous build of this same owner left behind.
        for node in list(nodes):
            if node.get(OWNER_PROP) == self.owner:
                nodes.remove(node)

        built: Dict[str, Any] = {}
        adopted_ptrs = set()

        for key, spec in self._specs.items():
            node = None
            if spec.adopt:
                for candidate in nodes:
                    if (
                        candidate.bl_idname == spec.bl_idname
                        and candidate.as_pointer() not in adopted_ptrs
                    ):
                        node = candidate
                        adopted_ptrs.add(candidate.as_pointer())
                        break
            if node is None:
                try:
                    node = nodes.new(spec.bl_idname)
                except RuntimeError as exc:
                    raise NodeGraphError(
                        f"cannot create node {spec.bl_idname!r} for key {key!r}: {exc}"
                    ) from exc
                node[OWNER_PROP] = self.owner
                node.name = f"{self.owner}:{key}"

            for attr, value in spec.props.items():
                resolved = value() if callable(value) else value
                if not hasattr(node, attr):
                    raise NodeGraphError(
                        f"node {key!r} ({spec.bl_idname}) has no attribute {attr!r}"
                    )
                setattr(node, attr, resolved)

            built[key] = node

        # Defaults are applied after every node exists, so a socket that is
        # about to be linked can still carry a sensible fallback value.
        for key, spec in self._specs.items():
            for socket_key, value in spec.inputs.items():
                socket = _resolve_socket(built[key], socket_key, False, key)
                socket.default_value = value() if callable(value) else value

        if clear_others:
            keep = {node.as_pointer() for node in built.values()}
            for node in list(nodes):
                if node.as_pointer() not in keep:
                    nodes.remove(node)

        for link in self._links:
            src = _resolve_socket(built[link.src.node_key], link.src.socket, True, link.src.node_key)
            dst = _resolve_socket(built[link.dst.node_key], link.dst.socket, False, link.dst.node_key)
            # An adopted node may already be wired; a socket takes one input.
            for existing in list(dst.links):
                links.remove(existing)
            links.new(src, dst)

        return built

    def clear(self, tree) -> int:
        """Remove every node this graph owns from ``tree``. Returns the count."""
        removed = 0
        for node in list(tree.nodes):
            if node.get(OWNER_PROP) == self.owner:
                tree.nodes.remove(node)
                removed += 1
        return removed


def _resolve_socket(node, key: SocketKey, is_output: bool, node_key: str):
    collection = node.outputs if is_output else node.inputs
    side = "output" if is_output else "input"
    if isinstance(key, int):
        try:
            return collection[key]
        except IndexError as exc:
            raise NodeGraphError(
                f"node {node_key!r} has no {side} socket at index {key}"
            ) from exc
    socket = collection.get(key)
    if socket is None:
        available = [s.name for s in collection]
        raise NodeGraphError(
            f"node {node_key!r} has no {side} socket named {key!r}; available: {available}"
        )
    return socket
