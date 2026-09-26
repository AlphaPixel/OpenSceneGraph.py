"""End-to-end headless render + capture through aipython's ipykernel backend."""

import asyncio
import os
import time

import pytest

from .aipython_scene import require_headless, setup_source, verify_capture

NAME = f"osg-aipython-kernel-{os.getpid()}"

def test_kernel_headless_capture(tmp_path):
	require_headless()

	from aipython.backend import BackendManager

	manager = BackendManager()
	path = str(tmp_path / "kernel.png")

	async def execute(code, timeout=30.0):
		return await manager.execute_async(name=NAME, code=code, timeout=timeout)

	async def run():
		started = await manager.start_async(backend="kernel", name=NAME)

		assert started.ok, started.data

		try:
			result = await execute(setup_source())

			assert result.ok, result.data

			# Frames render between cells, driven by the kernel's GUI integration.
			first = await execute("print(_osg_repl_state['frames'])")

			time.sleep(0.3)

			second = await execute("print(_osg_repl_state['frames'])")

			assert int(second.data["stdout"]) > int(first.data["stdout"])

			result = await execute(
				f"r = _osg_repl_controller.complete("
				f"_osg_repl_controller.capture_framebuffer({path!r}, label='kernel')); "
				f"print(r['label'], r['size'])"
			)

			assert result.ok, result.data
			assert "kernel" in result.data["stdout"]

			# Awaiting a capture would deadlock this backend; it must fail cleanly instead,
			# and the kernel must survive it.
			result = await execute("await _osg_repl_controller.capture_framebuffer_image()")

			assert not result.ok
			assert result.data["error_name"] == "RuntimeError"

			result = await execute("print('alive')")

			assert result.ok and "alive" in result.data["stdout"]

		finally:
			await manager.shutdown_async(name=NAME)

	asyncio.run(run())

	verify_capture(path)
