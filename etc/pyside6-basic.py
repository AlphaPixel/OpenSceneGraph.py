#!/usr/bin/env python3

import sys
import math

from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QSurfaceFormat

from OpenGL.GL import *

from OpenSceneGraph import *

class GLWidget(QOpenGLWidget):
	def __init__(self, parent=None):
		super().__init__(parent)

		self._viewer = None
		self._gw = None
		self._timer = QTimer(self)

		self._timer.timeout.connect(self.update)
		self._timer.start(1000 // 20)

	def initializeGL(self):
		self._viewer = osgViewer.Viewer()

		self._viewer.threadingModel = osgViewer.Viewer.ThreadingModel.SingleThreaded
		self._viewer.cameraManipulator = osgGA.TrackballManipulator()
		self._viewer.sceneData = osgDB.readNodeFile("cow.osgt")

		self._gw = self._viewer.setUpViewerAsEmbeddedInWindow(0, 0, self.width(), self.height())

	def resizeGL(self, w, h):
		dpr = self.devicePixelRatio()
		fbw = int(round(w * dpr))
		fbh = int(round(h * dpr))

		print(f"resizeGL logical={w}x{h} framebuffer={fbw}x{fbh} dpr={dpr}")

		self._viewer.camera.viewport = osg.Viewport(0, 0, fbw, fbh)
		self._viewer.camera.projectionMatrix = osg.Matrix.perspective(30.0, fbw / fbh, 1.0, 1000.0)

		self._viewer.eventQueue.windowResize(0, 0, fbw, fbh)
		self._viewer.eventQueue.currentEventState.mouseYOrientation = osgGA.GUIEventAdapter.Y_INCREASING_UPWARDS

		self._gw.resized(0, 0, fbw, fbh)

	def paintGL(self):
		self._viewer.frame()

def main():
	QApplication.setAttribute(Qt.AA_UseDesktopOpenGL)

	# TODO: I've had ... varied ... success with influencing how QT6 sets up the GL context. In
	# most cases, it's better to just let it do whatever it will.
	#
	# fmt = QSurfaceFormat()
    #
	# fmt.setRenderableType(QSurfaceFormat.OpenGL)
	# fmt.setProfile(QSurfaceFormat.CoreProfile)
	# fmt.setVersion(4, 6)
    #
	# QSurfaceFormat.setDefaultFormat(fmt)

	app = QApplication(sys.argv)

	win = QMainWindow()

	win.setCentralWidget(GLWidget())
	win.resize(800, 600)
	win.show()

	sys.exit(app.exec())

if __name__ == "__main__":
	main()
