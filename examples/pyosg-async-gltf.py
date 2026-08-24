#!/usr/bin/env python3
#vimrun! ../examples/pyosg-async-gltf.py

# Proves the "viewer pops up immediately, model pops in a few seconds later" idea, AND
# demonstrates the fully decoupled progress-display pattern: osgx.gltf.readNodeFile() runs the
# glTF reader off the GIL via asyncio.to_thread, writing progress into osgx.gltf.AsyncProgress
# (a lock-free struct -- no GIL touch from the background thread, ever, see
# aipython/25-async-osgpy.md), and pyosg_async.ProgressBar.watch() polls that SAME object as
# its own independent task, entirely separate from the load coroutine. Neither one knows the
# other exists: `load()` below never mentions the bar, and ProgressBar.watch() never mentions
# glTF. Both are just entries in pyosg_async.run()'s task list, alongside the render loop --
# "add progress display to the task stack like any other async thing and it just works."
#
# This is deliberately NOT run through pyosg_async.run_with_progress() -- that couples the wait
# for the blocking call to a single coroutine's own on_progress callback, which is the right
# shape for simple inline console output but the wrong shape here: only ONE thing may poll a
# given AsyncProgress (its "last seen" cursor lives inside the C++ object itself, not per
# caller -- two independent pollers would steal updates from each other). ProgressBar.watch()
# is that one poller; if you want console output too, drive it from watch()'s own to_fraction
# callback (it sees every update before converting to a fraction) rather than adding a second
# poller.
#
# Progress stages mirror osgx::gltf::Reader::Stage: PARSING -> BUILDING_NODES. There's no
# separate texture-loading stage - tinygltf v3 decodes images inline during the single real
# parse, not as a separable phase. During PARSING, current/total/section are a real (never
# fabricated) item index/count within one JSON section at a time (e.g. "meshes 3/7", then
# "images 1/8"). During BUILDING_NODES, current/total are nodes built so far / the total node
# count, and section is empty.

import argparse
import os
import pathlib
import time

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

import asyncio

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx
import pyosg_async

WIDTH = 800
HEIGHT = 600

def resolve_model(value):
	"""Accepts a bare model name (searched via OSG_FILE_PATH / glTF-Sample-Assets, same as
	Khronos's own sample set) as well as a real path -- so callers don't have to type the full
	path every time. Identical to pyosg-khronos-viewer.py's resolve_model()."""

	path = pathlib.Path(value).expanduser()

	if path.is_file():
		return path

	resolved = osgx.findDataFile(value)

	if resolved:
		return pathlib.Path(resolved)

	resolved = osgx.findDataFile(
		path.stem,
		("glTF-Sample-Assets/Models/{}/glTF/{}.gltf",)
	)

	if resolved:
		return pathlib.Path(resolved)

	raise FileNotFoundError(f"Cannot find glTF model {value!r}")

# argparse, not ad-hoc sys.argv filtering -- a plain "skip anything starting with --" (the
# previous approach) breaks the moment a flag TAKES a value (`--frames 30 Cube.gltf` vs.
# `Cube.gltf --frames 30` would parse differently), the exact class of bug that already bit
# --repl once before --frames even existed.
_parser = argparse.ArgumentParser()

_parser.add_argument("path", help="glTF model path or bare name (searched via OSG_FILE_PATH)")
_parser.add_argument(
	"--repl", action="store_true",
	help="drive by hand from a live IPython prompt instead of running automatically"
)
_parser.add_argument(
	"--frames", type=int, default=None,
	help="close the viewer after exactly this many frames, for deterministic/scripted runs"
)
_parser.add_argument(
	"--sync", action="store_true",
	help="bypass asyncio ENTIRELY (no asyncio.run(), no tasks, no event loop) -- tests whether "
	"asyncio.run()'s own teardown machinery is a necessary ingredient for the crash this file "
	"exists to investigate, see NEXT_SESSION.md"
)
_parser.add_argument(
	"--manual", action="store_true",
	help="replicate asyncio.run()'s own steps by hand, one at a time, with a print marker "
	"between each -- confirmed (2026-08-23) that asyncio.run() specifically (not asyncio in "
	"general -- --repl's real asyncio loop doesn't crash) is necessary for the crash; this "
	"narrows down WHICH of its internal steps actually triggers it"
)

ARGS = _parser.parse_args()
PATH = str(resolve_model(ARGS.path))

async def load(viewer, path, stop, progress, bar, t0):
	node = await asyncio.to_thread(osgx.gltf.readNodeFile, path, stop, progress)

	elapsed = time.time() - t0

	if node is None:
		print(f"[{elapsed:6.2f}s] load FAILED or cancelled", flush=True)

	else:
		print(f"[{elapsed:6.2f}s] COMPLETE; attaching to scene", flush=True)

		viewer.sceneData.children.append(node)
		viewer.cameraManipulator.home(0.0)

	# The load is over either way (success or failure) -- the progress display's job is done,
	# so it comes back out of the scene graph. bar.watch(progress) (still running as its own
	# task) keeps polling harmlessly after this; nothing needs to cancel it separately.
	print(f"[diag] bar.referenceCount BEFORE remove: {bar.referenceCount}", flush=True)

	viewer.sceneData.children.remove(bar)

	print(f"[diag] bar.referenceCount AFTER remove: {bar.referenceCount}", flush=True)

	# CONFIRMED FIX 2026-08-23 (see NEXT_SESSION.md): force bar's C++ destructor to run NOW,
	# deterministically, instead of leaving it to whatever order Python's interpreter shutdown
	# happens to destroy it in later -- that's the actual root cause, not anything about bar
	# itself or asyncio. `bar.watch(progress)` (still running as its own task) only holds a
	# reference to `bar` for as long as ITS OWN coroutine keeps running, so this del alone isn't
	# enough by itself -- see the note at the call site below.
	del bar

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	print(f"Loading (async, in the background): {PATH}", flush=True)

	viewer = osgViewer.Viewer()
	root = osg.Group()
	bar = pyosg_async.ProgressBar(WIDTH, HEIGHT, debug=True)

	root.children.append(bar)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	stop = StopEvent()
	progress = osgx.gltf.AsyncProgress()

	if ARGS.repl:
		# repl() owns viewer.frame() pumping on IPython's own asyncio event loop -- don't ALSO
		# start pyosg_async.run()'s separate asyncio.run() loop, they'd conflict. `load`,
		# `stop`, `progress`, `bar`, `viewer` are all in globals() here for driving BY HAND from
		# the live prompt, one step at a time, e.g.:
		#
		#   t = asyncio.ensure_future(load(viewer, PATH, stop, progress, bar, time.time()))
		#   bar.referenceCount
		#   viewer.sceneData.children.remove(bar)   # or skip this and let load() do it
		#   bar.referenceCount
		#   del bar   # or don't, to reproduce the original uncontrolled-lifetime bug on purpose
		#
		# See aipython/20-object-lifetime.md for .referenceCount/.dumps()/debug= -- the whole
		# point of --repl here is inspecting each of those steps individually instead of
		# guessing from a post-hoc log.
		from pyosg_repl import repl

		repl(viewer, globals())

	elif ARGS.sync:
		# ZERO asyncio -- no asyncio.run(), no tasks, no event loop, not even bar.watch() (it's
		# a coroutine, can't run here at all). Same real bar, same real readNodeFile() call, same
		# orphan-without-del pattern, just driven by a plain procedural script + frame loop.
		# Tests whether asyncio.run()'s own teardown (task cancellation, shutdown_asyncgens(),
		# loop.close()) is a NECESSARY ingredient for the crash, or whether it reproduces even
		# with nothing async involved whatsoever.
		t0 = time.time()
		node = osgx.gltf.readNodeFile(PATH, stop, progress)
		elapsed = time.time() - t0

		if node is None:
			print(f"[{elapsed:6.2f}s] load FAILED or cancelled", flush=True)

		else:
			print(f"[{elapsed:6.2f}s] COMPLETE; attaching to scene", flush=True)

			viewer.sceneData.children.append(node)
			viewer.cameraManipulator.home(0.0)

		print(f"[diag] bar.referenceCount BEFORE remove: {bar.referenceCount}", flush=True)

		viewer.sceneData.children.remove(bar)

		print(f"[diag] bar.referenceCount AFTER remove: {bar.referenceCount}", flush=True)

		while not viewer.done:
			viewer.frame()

	elif ARGS.manual:
		# Replicates asyncio.run()'s real implementation (cpython Lib/asyncio/runners.py) by
		# hand, one step at a time, with a print marker + bar.referenceCount after each -- to
		# find out WHICH specific step is where the crash actually happens, now that we've
		# confirmed asyncio.run() itself (not asyncio in general) is necessary for it.
		loop = asyncio.new_event_loop()

		asyncio.set_event_loop(loop)

		main_coro = pyosg_async.run(
			viewer,
			load(viewer, PATH, stop, progress, bar, time.time()),
			bar.watch(progress),
			max_frames=ARGS.frames
		)

		loop.run_until_complete(main_coro)

		print(f"[manual] main coroutine returned -- {bar.referenceCount}", flush=True)

		# Step 1: cancel any still-remaining tasks (pyosg_async.run()'s own finally block
		# should have already cancelled+awaited bar.watch()/render() before returning, so this
		# is likely a no-op here -- confirming that is itself useful).
		to_cancel = asyncio.all_tasks(loop)

		print(f"[manual] {len(to_cancel)} remaining task(s) to cancel", flush=True)

		for task in to_cancel:
			task.cancel()

		loop.run_until_complete(asyncio.gather(*to_cancel, return_exceptions=True))

		print(f"[manual] STEP 1 done (cancel remaining tasks) -- {bar.referenceCount}", flush=True)

		# Step 2: shut down async generators.
		loop.run_until_complete(loop.shutdown_asyncgens())

		print(f"[manual] STEP 2 done (shutdown_asyncgens) -- {bar.referenceCount}", flush=True)

		# Step 3: shut down the default ThreadPoolExecutor (the one asyncio.to_thread uses).
		if hasattr(loop, "shutdown_default_executor"):
			loop.run_until_complete(loop.shutdown_default_executor())

		print(f"[manual] STEP 3 done (shutdown_default_executor) -- {bar.referenceCount}", flush=True)

		# Step 4: unset the event loop.
		asyncio.set_event_loop(None)

		print(f"[manual] STEP 4 done (set_event_loop(None)) -- {bar.referenceCount}", flush=True)

		# Step 5: close the loop -- the actual OS-level teardown (closes the selector/epoll fd
		# and asyncio's internal self-pipe). This is the LAST thing asyncio.run() does.
		loop.close()

		print(f"[manual] STEP 5 done (loop.close()) -- {bar.referenceCount}", flush=True)
		print("[manual] ALL asyncio.run()-equivalent steps completed with no crash", flush=True)

	else:
		asyncio.run(pyosg_async.run(
			viewer,
			load(viewer, PATH, stop, progress, bar, time.time()),
			bar.watch(progress),
			max_frames=ARGS.frames
		))
