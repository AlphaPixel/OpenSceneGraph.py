#!/usr/bin/env python3

import os

# setdefault(), not update() -- this module is imported by other examples (pyosg-mrt.py,
# etc.) that configure their own OSG_WINDOW/OSG_THREADING before importing pyosg_visitor for
# its GatherVisitor. update() here would silently clobber whatever the caller already set.
# Only pyosg_visitor.py's own standalone __main__ use below relies on these being filled in.
os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

from OpenSceneGraph import *

# GatherVisitor: a scene-graph inspector, proof-of-concept for a future "active state" panel
# (e.g. showing every live shader/uniform in a GUI alongside the viewport). Walks the graph
# and reports every attached Program/Uniform via `osg.notice()`. Meant to be imported --
# `from pyosg_visitor import GatherVisitor` -- and fired at any live scene, same shape as
# `pyosg_repl.py`'s `repl()` helper.
#
# This originally surfaced two real binding gaps -- osg.Node had no non-creating
# getStateSet(), and osg.StateSet had no way to read a Program back out once attached --
# both since fixed (osg.getStateSet(node) and StateSet.attributes[], respectively).

VERTEX_SHADER = """#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;

void main() {
	vNormal = normalize(osg_NormalMatrix * osg_Normal);

	gl_Position = osg_ModelViewProjectionMatrix * osg_Vertex;
}
"""

FRAGMENT_SHADER = """#version 460 core

in vec3 vNormal;

out vec4 fragColor;

uniform vec3 lightDir;

void main() {
	vec3 N = normalize(vNormal);
	float diff = max(dot(N, normalize(lightDir)), 0.0);

	fragColor = vec4(vec3(0.9, 0.6, 0.3) * diff, 1.0);
}
"""

class GatherVisitor(osg.NodeVisitor):
	"""`namespace`, if given (e.g. `locals()`/`globals()` at the call site), is scanned ONCE for
	`.addr`-bearing values; any gathered object whose `.addr` matches gets an extra "bound to
	local: 'x'" hint. Only finds BARE top-level names in that dict -- an object only reachable
	via a chain (e.g. `hudCam.stateSet.attributes[PROGRAM]`) won't get a hint, and that's fine.
	"""

	def __init__(self, namespace=None):
		super().__init__(osg.NodeVisitor.TraversalMode.TRAVERSE_ALL_CHILDREN)

		self._by_addr = {}

		for name, value in (namespace or {}).items():
			addr = getattr(value, "addr", None)

			if addr is not None:
				self._by_addr.setdefault(addr, []).append(name)

	def _hint(self, obj):
		names = self._by_addr.get(obj.addr)

		if not names:
			return ""

		plural = "s" if len(names) > 1 else ""

		return f" (bound to local{plural}: {', '.join(repr(n) for n in names)})"

	def apply(self, node):
		osg.notice(f"[gather] {type(node).__name__} '{node.name}'{self._hint(node)}")

		ss = osg.getStateSet(node)

		if ss is None:
			return

		if osg.StateAttribute.PROGRAM in ss.attributes:
			program = ss.attributes[osg.StateAttribute.PROGRAM]

			osg.notice(f"  [gather] Program: {program.name}{self._hint(program)}")

			for shader in program.shaders:
				lines = shader.source.splitlines()
				preview = next((l.strip() for l in lines if l.strip()), "")

				osg.notice(f"    {shader.type}: {len(lines)} lines, starts: {preview!r}")

		names = list(ss.uniforms.keys())

		osg.notice(f"  [gather] Uniforms: {names or '(none)'}")

		for name in names:
			u = ss.uniforms[name]

			osg.notice(f"    {name}: type={u.type}{self._hint(u)}")

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	geode = osg.Geode(drawables=(
		osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 0, 0), 1.0)),
	))

	p = osg.Program(name="visitor-proof", shaders=(
		osg.Shader(osg.Shader.VERTEX, VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, FRAGMENT_SHADER)
	))

	geode.stateSet.attributes.append(p)
	geode.stateSet.uniforms["lightDir"] = osg.Vec3(0.5, 0.8, 0.3)

	geode.accept(GatherVisitor(namespace=locals()))

	v = osgViewer.Viewer()
	v.sceneData = geode
	v.cameraManipulator = osgGA.TrackballManipulator()

	while not v.done:
		v.frame()
