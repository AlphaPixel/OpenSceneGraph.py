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
	# progress, complete, etc.
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

async def faux_load(queue, job_id, seconds):
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
		value=f"result-{job_id}"
	))

async def cpp_load(queue, job_id, seconds):
	stop = StopEvent()
	task = asyncio.create_task(asyncio.to_thread(load_heavy, seconds, stop))

	try:
		result = await task

		await queue.put(Event(
			type=EventType.COMPLETE,
			id=job_id,
			value=result
		))

	except asyncio.CancelledError:
		stop.stop()

		task.cancel()

		try:
			await task

		except asyncio.CancelledError:
			pass

		raise

async def cpp_load_loop_queue(queue, job_id, seconds):
	stop = StopEvent()
	loop = asyncio.get_running_loop()
	task = asyncio.create_task(asyncio.to_thread(
		load_heavy_loop_queue,
		seconds,
		stop,
		loop,
		queue,
		job_id
	))

	try:
		result = await task

		# NOTE: completion already emitted from C++
		return result

	except asyncio.CancelledError:
		print("python: cancellation requested")

		stop.stop()

		try:
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
				# print("heartbeat tick")

				await asyncio.sleep(1.0)

		except asyncio.CancelledError:
			print("heartbeat cancelled")

			raise

	tasks = [
		loop.create_task(heartbeat()),
		loop.create_task(faux_load(queue, 0, 2)),
		loop.create_task(cpp_load(queue, 1, 4)),
		loop.create_task(cpp_load_loop_queue(queue, 2, 6))
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
						# print(f"{ev} {time.time() - t}")

						if ev.type == EventType.PROGRESS:
							print(f"[{ev.id}] {ev.value * 100:.0f}%")

						elif ev.type == EventType.COMPLETE:
							print(f"[{ev.id}] COMPLETE -> {ev.value}")

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

		# flush pending callbacks from C++
		loop.run_until_complete(asyncio.sleep(0))

		loop.stop()
		loop.close()

		print("loop closed")

if __name__ == "__main__":
	viewer = osgViewer.Viewer()

	viewer.cameraManipulator = osgGA.TrackballManipulator()
	viewer.sceneData = osgDB.readNodeFile("glsl_simple.osgt")

	run(viewer)
