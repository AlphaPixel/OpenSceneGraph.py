"""CLI backing the `pyosg` console script and `python -m OpenSceneGraph.examples <name>`.

Runs one of this package's example modules standalone (no Qt, no aipython) by creating a
bare osgViewer.Viewer, calling the example's build_scene(w, h), and its
configure_viewer(viewer, root) if it defines one. Adapted from the pyosg-cli
proof-of-concept in the project's repository root, which loads examples by file path out of
examples/ instead -- useful for the full example sandbox, most of which doesn't implement
this module's build_scene()/configure_viewer() contract (yet).
"""

import argparse
import importlib
import pkgutil
import sys

from OpenSceneGraph import *


def _load_module(name):
	try:
		return importlib.import_module(f"OpenSceneGraph.examples.{name}")

	except ModuleNotFoundError:
		import OpenSceneGraph.examples as _examples

		available = sorted(
			mod.name for mod in pkgutil.iter_modules(_examples.__path__)
			if not mod.name.startswith("_")
		)

		sys.exit(f"error: no such example: {name!r} (available: {', '.join(available)})")


def run(name, width=800, height=600, extra_argv=()):
	module = _load_module(name)

	if not hasattr(module, "build_scene"):
		sys.exit(f"error: OpenSceneGraph.examples.{name} has no build_scene(w, h)")

	viewer = osgViewer.Viewer()

	viewer.cameraManipulator = osgGA.TrackballManipulator()

	# Sandbox sys.argv for the duration of both hook calls below: some examples (e.g.
	# blur's create_scene()) read sys.argv[1] lazily, from inside build_scene() itself, not
	# just at module-import time. extra_argv forwards e.g. `pyosg blur -- foo.gltf` through
	# to the example's own sys.argv[1:], matching `python -m OpenSceneGraph.examples.blur
	# foo.gltf`.
	saved_argv = sys.argv

	sys.argv = [name, *extra_argv]

	try:
		root = module.build_scene(width, height)

		viewer.sceneData = root

		if hasattr(module, "configure_viewer"):
			module.configure_viewer(viewer, root)

	finally:
		sys.argv = saved_argv

	viewer.TODO()

	while not viewer.done:
		viewer.frame()


def main():
	parser = argparse.ArgumentParser(
		prog="pyosg",
		description="Run an OpenSceneGraph.examples module standalone, no Qt required"
	)

	parser.add_argument("name", help="Example module name, e.g. 'mrt' for OpenSceneGraph.examples.mrt")
	parser.add_argument("--width", type=int, default=800)
	parser.add_argument("--height", type=int, default=600)

	# Split on the FIRST literal "--" ourselves, before argparse ever sees it, and hand it
	# only the part before that. argparse.add_argument("extra", nargs="*") looks like the
	# obvious way to do this instead, but has a real, confirmed bug: "mrt -- foo.osgt" parses
	# fine, but "mrt --width 640 -- foo.osgt" fails with "unrecognized arguments: -- foo.osgt"
	# -- a known CPython argparse limitation around "--" interacting with a nargs="*"
	# positional when other flags are interspersed, not something fixable by reordering our
	# own argument definitions.
	argv = sys.argv[1:]

	if "--" in argv:
		i = argv.index("--")
		own_argv, extra_argv = argv[:i], argv[i + 1:]

	else:
		own_argv, extra_argv = argv, []

	args = parser.parse_args(own_argv)

	run(args.name, args.width, args.height, extra_argv)


if __name__ == "__main__":
	main()
