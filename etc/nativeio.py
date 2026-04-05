# nativeio.py

import os
import io
import ctypes
import contextlib

libc = ctypes.CDLL(None)

@contextlib.contextmanager
def silence(fds=(1, 2)):
	"""
	Temporarily silence ALL native output (C/C++, printf, std::cout, write()).

	fds: tuple of file descriptors to silence (default: stdout=1, stderr=2)
	"""

	# Flush everything BEFORE redirect
	libc.fflush(None)

	saved = []
	devnull = os.open(os.devnull, os.O_WRONLY)

	try:
		# Duplicate originals
		for fd in fds:
			saved.append((fd, os.dup(fd)))
			os.dup2(devnull, fd)

		yield

	finally:
		# Flush any remaining buffered output INTO /dev/null
		libc.fflush(None)

		# Restore original FDs
		for fd, old in saved:
			os.dup2(old, fd)
			os.close(old)

		os.close(devnull)

		# Final safety flush
		libc.fflush(None)

@contextlib.contextmanager
def capture(fds=(1, 2)):
	"""
	Capture ALL native output from given FDs into a buffer.
	Returns an io.BytesIO buffer containing binary output.
	"""
	# Flush before capturing
	libc.fflush(None)

	buf = io.BytesIO()
	read_fds = []
	saved = []

	# Create a pipe to capture the output
	pipes = [os.pipe() for _ in fds]

	try:
		# Redirect each fd to its pipe write end
		for (fd, (r, w)) in zip(fds, pipes):
			saved.append((fd, os.dup(fd)))
			os.dup2(w, fd)
			read_fds.append(r)
			os.close(w)

		yield buf

	finally:
		# Flush BEFORE restoring FDs
		libc.fflush(None)

		# Close write ends & restore original FDs
		for (fd, old) in saved:
			os.dup2(old, fd)
			os.close(old)

		# Read captured data
		for r in read_fds:
			try:
				chunk = os.read(r, 65536)

				while chunk:
					buf.write(chunk)
					chunk = os.read(r, 65536)

			finally:
				os.close(r)

		libc.fflush(None)

EXAMPLES = [
"""
from nativeio import silence

with silence():
    import OpenSceneGraph
""",

"""
from nativeio import capture

with capture() as cap:
    import noisy_native_module

print(f"Captured: {cap.getvalue()}")
""",

"""
from nativeio import silence

with silence(fds=(2,)):
    import module_that_spams_errors
"""
]
