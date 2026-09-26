"""End-to-end headless render + capture through aipython's tmux (terminal IPython) backend."""

import os
import shlex
import sys

from .aipython_scene import require_headless, require_tmux, setup_source, verify_capture

NAME = f"osg-aipython-tmux-{os.getpid()}"

def test_tmux_headless_capture(tmp_path):
	require_headless()
	require_tmux()

	import aipython.tmux as tmux

	script = tmp_path / "scene.py"
	complete_path = str(tmp_path / "complete.png")
	await_path = str(tmp_path / "await.png")

	script.write_text(setup_source())

	# The tmux server's environment (not this process's) is what the session inherits, so
	# DISPLAY is removed on the command line; sys.path comes from the script itself.
	command = (
		f"cd {shlex.quote(str(tmp_path))} && env -u DISPLAY OSG_NOTIFY_LEVEL=WARN "
		f"{shlex.quote(sys.executable)} {shlex.quote(str(script))}"
	)

	tmux.start(name=NAME, command=command)

	try:
		ready = tmux.wait_for_idle(name=NAME, timeout=30.0)

		assert ready.idle, ready.text

		result = tmux.execute(
			name=NAME,
			text=(
				f"r = _osg_repl_controller.complete("
				f"_osg_repl_controller.capture_framebuffer({complete_path!r})); "
				f"print('COMPLETED', r['size'])"
			),
			timeout=30.0,
		)

		assert "COMPLETED (160, 120)" in result.text, result.text

		# The terminal backend pumps frames on the asyncio loop while a cell awaits.
		result = tmux.execute(
			name=NAME,
			text=(
				f"r = await _osg_repl_controller.capture_framebuffer({await_path!r}); "
				f"print('AWAITED', r['size'])"
			),
			timeout=30.0,
		)

		assert "AWAITED (160, 120)" in result.text, result.text

	finally:
		tmux.stop(name=NAME)

	verify_capture(complete_path)
	verify_capture(await_path)
