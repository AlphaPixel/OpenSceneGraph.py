#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/GraphicsContext>
#include <osgViewer/GraphicsWindow>

PYOSG_ENABLE_WARNINGS

namespace pyosg_linux {

// Creates an X11 window driven by EGL instead of GLX. Skeleton/proof port of
// ~/dev/misc/osg/src/miscosg-graphics-window-egl.cpp -- not a full implementation (no input/resize
// handling yet), just enough to prove an EGL-backed osgViewer::GraphicsWindow can be created and
// attached to a Camera from Python. checkEvents() DOES watch for a clean window-manager close
// (WM_DELETE_WINDOW), so clicking the window's close button shuts the viewer down properly instead
// of leaving a dead EGL surface behind.
osg::ref_ptr<osgViewer::GraphicsWindow> createEGLWindow(osg::GraphicsContext::Traits* traits);

void bind_GraphicsWindowEGL(py::module_& m);

}
