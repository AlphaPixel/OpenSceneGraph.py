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
	loop = asyncio.new_event_loop()
	queue = asyncio.Queue()

	asyncio.set_event_loop(loop)

	# This DOES NOT USE the `queue` above!
	async def heartbeat():
		try:
			while not viewer.done:
				print("heartbeat tick")

				await asyncio.sleep(1.0)

		except asyncio.CancelledError:
			print("heartbeat cancelled")

			raise

	tasks = [
		loop.create_task(heartbeat()),
		loop.create_task(task_py_example(queue, 0, 2)),
		loop.create_task(task_cpp_example(queue, 1, 5))
	]

	t = time.time()

	try:
		while not viewer.done:
			viewer.frame()

			# pump asyncio (non-blocking)
			loop.run_until_complete(asyncio.sleep(0))

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

	finally:
		for task in tasks:
			task.cancel()

		try:
			for task in tasks:
				loop.run_until_complete(task)

		except asyncio.CancelledError:
			pass

		# Flush pending callbacks from C++, if any.
		loop.run_until_complete(asyncio.sleep(0))

		loop.stop()
		loop.close()

		print("loop closed")

if __name__ == "__main__":
	viewer = osgViewer.Viewer()

	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.sceneData = osg.Geode() # osgDB.readNodeFile("glsl_simple.osgt")

	run(viewer)
