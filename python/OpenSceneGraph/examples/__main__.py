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

	except ModuleNotFoundError as error:
		# Only turn failure to locate the requested example itself into the
		# friendly availability list. A ModuleNotFoundError raised by one of the
		# example's own imports is a real diagnostic and must not be disguised as
		# an unknown runner name.
		if error.name != f"OpenSceneGraph.examples.{name}":
			raise

		import OpenSceneGraph.examples as _examples

		available = sorted(
			mod.name for mod in pkgutil.iter_modules(_examples.__path__)
			if not mod.name.startswith("_")
		)

		sys.exit(f"error: no such example: {name!r} (available: {', '.join(available)})")


def run_module(module, width=800, height=600, extra_argv=(), name=None):
	"""Shared runner core: viewer construction, window setup, build_scene()/configure_viewer(),
	and the frame loop. Deliberately takes an already-loaded module object rather than a name --
	`run()` below loads it from the installed OpenSceneGraph.examples package, while pyosg-cli
	(repo root) loads an arbitrary examples/*.py file by path and calls this directly, so the
	actual viewer-setup/frame-loop logic exists in exactly one place instead of two copies that
	can silently drift (this bit pyosg-cli once already -- see PYOSG_BUILD_PACKAGE_OVERLAY/
	setUpViewInWindow ordering history in project_pyosg_contract_conversion for the pyosg-
	polyhaven.py --hdr bug that ordering mismatch caused)."""

	if not hasattr(module, "build_scene"):
		sys.exit(f"error: {name or module.__name__} has no build_scene(w, h)")

	viewer = osgViewer.Viewer()

	# Explicit window setup, driven by the same width/height build_scene() receives -- a single
	# source of truth instead of every example hardcoding its own OSG_WINDOW env var string that
	# has to be kept in sync by hand (and silently isn't, the moment --width/--height differs from
	# an example's own hardcoded default). x/y match the "50 50 ..." every example's old OSG_WINDOW
	# used.
	viewer.setUpViewInWindow(50, 50, width, height)

	viewer.cameraManipulator = osgGA.TrackballManipulator()

	# Sandbox sys.argv for the duration of both hook calls below: some examples (e.g.
	# blur's create_scene()) read sys.argv[1] lazily, from inside build_scene() itself, not
	# just at module-import time. extra_argv forwards e.g. `pyosg blur -- foo.gltf` through
	# to the example's own sys.argv[1:], matching `python -m OpenSceneGraph.examples.blur
	# foo.gltf`.
	saved_argv = sys.argv

	sys.argv = [name or module.__name__, *extra_argv]

	try:
		root = module.build_scene(width, height)

		viewer.sceneData = root

		if hasattr(module, "configure_viewer"):
			module.configure_viewer(viewer, root)

	finally:
		sys.argv = saved_argv

	viewer.TODO()

	# KNOWN ISSUE, deliberately not "fixed" with a sleep() here -- see feedback_runner_unthrottled_loop
	# for the full writeup. Short version: a sleep() here treats the symptom (starves anything else
	# on the process needing the GIL on a regular cadence, confirmed via audible clicking in
	# pyosg-animusic-grid.py's sounddevice callback thread); the real fix under consideration is
	# releasing the GIL inside viewer.frame()'s own pybind11 binding instead.
	while not viewer.done:
		viewer.frame()


def run(name, width=800, height=600, extra_argv=()):
	module = _load_module(name)

	run_module(module, width, height, extra_argv, name=name)


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
	#
	# KNOWN FRICTION (deferred, not fixed, same as pyosg-cli): every one of the target example's
	# own arguments -- including its OWN required positionals/flags -- has to go after this "--",
	# since this parser only knows about name/--width/--height. A `parse_known_args()`-based
	# two-pass parse could remove the need for "--" in the common case; not attempted, needs real
	# testing against the SAME argparse quirk documented above first.
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
