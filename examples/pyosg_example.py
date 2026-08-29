#!/usr/bin/env python3

import os

# setdefault(), not update() -- same reason as pyosg_visitor.py: an example that already set its
# own OSG_WINDOW/OSG_THREADING/etc. (window size, a non-default GL version, ...) before importing
# this keeps what it set; this only fills in whatever it didn't. Importing this is now the ONE
# place "SingleThreaded is mandatory" (see feedback_viewer_close_threading_deadlock -- a live
# non-SingleThreaded draw thread can deadlock a Viewer's destructor) is declared -- an example
# that imports this for window_size() gets it whether or not its own env block remembers to say
# so, instead of a standing policy that only holds as well as 42 separate copy-pasted blocks do.
os.environ.setdefault("OSG_WINDOW", "50 50 800 600")
os.environ.setdefault("OSG_THREADING", "SingleThreaded")
os.environ.setdefault("OSG_GL_CONTEXT_PROFILE_MASK", "1")
os.environ.setdefault("OSG_GL_VERSION", "4.6")
os.environ.setdefault("OSG_GL_CONTEXT_VERSION", "4.6")

# Derives (width, height) from OSG_WINDOW ("x y width height", e.g. "50 50 800 600") instead of a
# second, separately-hardcoded W, H module constant -- one declared value per file instead of two
# that can silently drift apart. Standalone __main__ blocks call this; the pyosg/
# OpenSceneGraph.examples runners never do (they pass their own --width/--height straight into
# build_scene() and viewer.setUpViewInWindow()). See build_scene()'s own contract comment in
# pyosg-mrt.py: (w, h) stays an explicit argument on every build_scene(), never something it reads
# from the environment itself -- this function is the caller-side counterpart of that rule, not an
# exception to it.
def window_size(default=(800, 600)):
	spec = os.environ.get("OSG_WINDOW")

	if not spec:
		return default

	x, y, w, h = spec.split()

	return int(w), int(h)
