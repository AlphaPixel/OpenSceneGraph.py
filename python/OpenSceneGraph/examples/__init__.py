"""Curated, runnable examples installed with the OpenSceneGraph wheel.

Each module here exposes ``build_scene(width, height) -> osg.Node`` and, optionally,
``configure_viewer(viewer, root)``; see ``OpenSceneGraph.examples.__main__`` (the
implementation behind the ``pyosg`` console script) for the shared runner that drives both
hooks. Every module is also directly runnable on its own, e.g.
``python -m OpenSceneGraph.examples.mrt``.

This is a small, curated subset of the full example sandbox in the project's `examples/`
source directory -- not everything there implements the build_scene()/configure_viewer()
contract (yet), and most of that directory (the Lighting Series, GLSL experiments, data
files, etc.) isn't meant to ship in the wheel at all.
"""

import sys as _sys
from pathlib import Path as _Path

# A couple of these examples do a bare `from pyosg_visitor import GatherVisitor` rather than
# a package-relative import, matching how they're written to also run standalone straight out
# of the project's examples/ directory (see pyosg-cli). Put this package's own directory on
# sys.path so that resolves the same way here.
_sys.path.insert(0, str(_Path(__file__).parent))

del _sys, _Path
