#!/usr/bin/env python3
#vimrun! ../examples/pyosg-async-gltf.py

# Proves the "viewer pops up immediately, model pops in a few seconds later"
# idea: osgx.gltf.readNodeFileAsync() runs the glTF reader off the GIL on a
# background thread (asyncio.to_thread), reporting real per-stage progress
# through the same loop/queue call_soon_threadsafe bridge as
# examples/pyosg-async.py's pyosg_async_task_example. The render loop keeps
# pumping viewer.frame() the whole time - nothing blocks.
#
# Progress stages mirror osgx::gltf::Reader::Stage: PARSING ->
# LOADING_TEXTURES -> BUILDING_NODES, strictly sequential, current
# non-decreasing within a stage, every stage ends at current==total before
# the next stage's first event. total is always a real known count - a
# cheap metadata-only pre-pass learns the image count before the real
# (per-image-ticking) decode pass runs, so there's no indeterminate/unknown
# total to represent.

import os
import sys
import time

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6",
})

import asyncio

from dataclasses import dataclass
from enum import Enum

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import osgx

PATH = sys.argv[1] if len(sys.argv) >= 2 else os.path.expanduser(
	"~/tmp/3dmodels/deadspace00/scene.gltf"
)

class GLTFStage(Enum):
	PARSING = "parsing"
	LOADING_TEXTURES = "loading_textures"
	BUILDING_NODES = "building_nodes"

@dataclass
class GLTFProgress:
	stage: GLTFStage
	current: int
	total: int

def run(viewer, path):
	loop = asyncio.new_event_loop()
	queue = asyncio.Queue()

	asyncio.set_event_loop(loop)

	stop = StopEvent()
	job_id = 1
	t0 = time.time()

	load_task = loop.create_task(asyncio.to_thread(
		osgx.gltf.readNodeFileAsync,
		path,
		stop,
		loop,
		queue,
		job_id
	))

	loaded = {"done": False}

	try:
		while not viewer.done:
			viewer.frame()

			# Non-blocking pump - this is the only thing asyncio needs to keep
			# the background thread's messages flowing into `queue`.
			loop.run_until_complete(asyncio.sleep(0))

			try:
				while True:
					ev = queue.get_nowait()

					if ev[0] == "progress":
						_, jid, stage, current, total = ev

						progress = GLTFProgress(GLTFStage(stage), current, total)

						print(
							f"[{time.time()-t0:6.2f}s] "
							f"{progress.stage.value}: {progress.current}/{progress.total}",
							flush=True
						)

					elif ev[0] == "complete":
						_, jid, node = ev

						elapsed = time.time() - t0

						if node is None:
							print(f"[{elapsed:6.2f}s] load FAILED or cancelled", flush=True)

						else:
							print(f"[{elapsed:6.2f}s] COMPLETE; attaching to scene", flush=True)

							viewer.sceneData.children.append(node)
							viewer.cameraManipulator.home(0.0)

							loaded["done"] = True

			except asyncio.QueueEmpty:
				pass

	finally:
		if not load_task.done():
			load_task.cancel()
			stop.stop()

			try:
				loop.run_until_complete(load_task)

			except asyncio.CancelledError:
				pass

		loop.run_until_complete(asyncio.sleep(0))
		loop.stop()
		loop.close()

if __name__ == "__main__":
	osg.setNotifyLevel(osg.NotifySeverity.NOTICE)

	print(f"Loading (async, in the background): {PATH}", flush=True)

	viewer = osgViewer.Viewer()
	root = osg.Group()

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	run(viewer, PATH)
