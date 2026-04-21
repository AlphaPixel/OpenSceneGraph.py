#!/usr/bin/env -S ipython3 -i
#vimrun! ipython3 -i ../examples/pyosg-repl.py

import os

os.environ.update({
	"OSG_WINDOW": "50 50 800 600",
	"OSG_THREADING": "SingleThreaded",
})

import time

from OpenSceneGraph import *

class DebugHandler(osgGA.GUIEventHandler):
	debug = False

	def handle(self, ea, aa):
		if self.debug:
			if not ea.type == osgGA.GUIEventAdapter.FRAME:
				print(f"DebugHandler.handle(self={self}, ea={ea}, aa={aa}) type={ea.type}")

class REPLCameraManipulator(osgGA.CameraManipulator):
	def __init__(self):
		super().__init__()

		self._matrix = osg.Matrixd()

	def getMatrix(self):
		return self._matrix

	def setByMatrix(self, m):
		self._matrix = m

	def getInverseMatrix(self):
		return osg.Matrix.inverse(self._matrix)

	def setByInverseMatrix(self, m):
		self._matrix = osg.Matrix.inverse(m)

# ------------------------------------------------------------------------------
# Viewer setup (nothing fancy)
# ------------------------------------------------------------------------------

viewer = osgViewer.Viewer()

viewer.sceneData = osg.Geode()
viewer.cameraManipulator = osgGA.TrackballManipulator()
# viewer.cameraManipulator = REPLCameraManipulator()
viewer.addEventHandler(DebugHandler())

# ------------------------------------------------------------------------------
# INPUTHOOK (ABSOLUTE MINIMUM)
# ------------------------------------------------------------------------------

from IPython.terminal.pt_inputhooks import register
from IPython import get_ipython

def osg_inputhook(context):
	while not context.input_is_ready() and not viewer.done:
		viewer.frame()

		# Let's shoot for 30FPS...
		time.sleep(1.0 / 30.0)

register("osg", osg_inputhook)

# ------------------------------------------------------------------------------
# ACTIVATE (MUST BE LAST)
# ------------------------------------------------------------------------------

ip = get_ipython()

if ip is None:
	raise RuntimeError("Run inside IPython using `%run` or via `ipython3 -i`")

ip.enable_gui("osg")

print("\nMINIMAL OSG REPL READY! Bring the 🔥!")
print("Try interacting with the `viewer` variable!\n")
