#!/usr/bin/env python3
#vimrun! ../examples/pyosg-async.py

import os

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
	"OSG_GL_CONTEXT_PROFILE_MASK": "1",
	"OSG_GL_VERSION": "4.6",
	"OSG_GL_CONTEXT_VERSION": "4.6"
	# "__GL_SYNC_TO_VBLANK": "1"
})

import time
import asyncio

from dataclasses import dataclass
from typing import Any
from enum import Enum

from OpenSceneGraph import *
from OpenSceneGraph.GL import *

import pyosg_async

class EventType(Enum):
	PROGRESS = 1
	COMPLETE = 2

@dataclass
class Event:
	type: EventType
	id: int
	value: Any = None

	@staticmethod
	def from_tuple(ev):
		return Event(
			type=ev[0] == "progress" and EventType.PROGRESS or EventType.COMPLETE,
			id=ev[1],
			value=ev[2]
		)

async def task_py_example(queue, job_id, seconds):
	steps = 10

	for i in range(steps):
		await asyncio.sleep(seconds / steps)

		await queue.put(Event(
			type=EventType.PROGRESS,
			id=job_id,
			value=(i + 1) / steps
		))

	await queue.put(Event(
		type=EventType.COMPLETE,
		id=job_id,
		value=f"result-from-python"
	))

async def task_cpp_example(queue, job_id, seconds):
	stop = StopEvent()
	loop = asyncio.get_running_loop()
	task = asyncio.create_task(asyncio.to_thread(
		pyosg_async_task_example,
		seconds,
		stop,
		loop,
		queue,
		job_id
	))

	try:
		result = await task

		# NOTE: The result was also pushed through queue.
		return result

	except asyncio.CancelledError:
		print("python: cancellation requested")

		stop.stop()

		try:
			# TODO: Investigate more about what `shield` actually does!
			result = await asyncio.shield(task)

			print("C++ exited with:", result)

		except asyncio.CancelledError:
			print("python: task was force-cancelled")

			pass

		raise

def run(viewer):
	queue = asyncio.Queue()
	t = time.time()

	# This DOES NOT USE the `queue` above!
	async def heartbeat():
		while not viewer.done:
			print("heartbeat tick")

			await asyncio.sleep(1.0)

	# The queue-draining half of the OLD push-based pattern (queue.put() -> call_soon_threadsafe
	# -> queue.get_nowait()) is still exactly right for THIS kind of event -- irregular,
	# Python-shaped values a C++ background thread genuinely needs to hand back, not a hot
	# native loop's numeric progress ticks. Contrast with osgx.gltf.AsyncProgress (see
	# pyosg-async-gltf.py), which polls instead of pushing because its update shape is simple
	# enough not to need the GIL-crossing queue machinery at all. Both are legitimate; pick the
	# one that matches what's actually being reported.
	async def drain_queue():
		while not viewer.done:
			try:
				while True:
					ev = queue.get_nowait()

					if type(ev) == tuple:
						ev = Event.from_tuple(ev)

					try:
						elapsed = time.time() - t

						if ev.type == EventType.PROGRESS:
							print(f"[{ev.id}]({elapsed:.5f}s) {ev.value * 100:.0f}%")

						elif ev.type == EventType.COMPLETE:
							print(f"[{ev.id}]({elapsed:.5f}s) COMPLETE -> {ev.value}")

							viewer.sceneData.drawables.append(
								osg.ShapeDrawable(osg.Sphere(osg.Vec3(0, 2.0, 0), 1.0))
							)

							viewer.cameraManipulator.home(0.0)

					except Exception as e:
						print(f"EXCEPTION: {e}")

			except asyncio.QueueEmpty:
				pass

			await asyncio.sleep(0)

	async def main():
		await asyncio.gather(
			heartbeat(),
			drain_queue(),
			task_py_example(queue, 0, 2),
			task_cpp_example(queue, 1, 5)
		)

	asyncio.run(pyosg_async.run(viewer, main()))

	print("loop closed")

if __name__ == "__main__":
	SEVERITY_MAP = {
		osg.NotifySeverity.FATAL: "\033[31m",
		osg.NotifySeverity.WARN: "\033[33m",
		osg.NotifySeverity.NOTICE: "\033[32m",
		osg.NotifySeverity.INFO: "\033[0m",
		osg.NotifySeverity.DEBUG_INFO: "\033[36m",
		osg.NotifySeverity.DEBUG_FP: "\033[36m"
	}

	def notify(sev, msg):
		msg = msg.strip()

		if not msg:
			return

		print(f"{SEVERITY_MAP[sev]}{sev}: {msg}\033[0m")

	osg.setNotifyLevel(osg.NotifySeverity.INFO)
	osg.setNotifyHandler(notify)

	viewer = osgViewer.Viewer()

	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.sceneData = osg.Geode() # osgDB.readNodeFile("glsl_simple.osgt")

	run(viewer)
