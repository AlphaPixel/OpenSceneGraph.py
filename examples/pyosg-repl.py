#!/usr/bin/env -S ipython3 -i

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
		if not ea.type == osgGA.GUIEventAdapter.FRAME:
		# if self.debug:
			# print(f"DebugHandler.handle(self={self}, ea={ea}, aa={aa}) type={ea.type}")
			print(f"DebugHandler.handle(self={self}, ea={ea}, aa={aa}) type={ea.type}")

# ------------------------------------------------------------------------------
# Viewer setup (nothing fancy)
# ------------------------------------------------------------------------------

viewer = osgViewer.Viewer()

viewer.sceneData = osg.Geode()
viewer.cameraManipulator = osgGA.TrackballManipulator()
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
