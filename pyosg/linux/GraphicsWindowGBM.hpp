#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/GraphicsContext>
#include <osgViewer/GraphicsWindow>

PYOSG_ENABLE_WARNINGS

namespace pyosg_linux {

// Direct-scanout (no X11, no window manager) DRM/KMS + GBM window, kiosk/embedded-style.
// Skeleton/proof port of ~/dev/misc/osg/src/miscosg-graphics-window-gbm.cpp -- requires exclusive
// access to a DRM master node (/dev/dri/cardN), so it will fail to initialize if an X server or
// Wayland compositor already holds the display; not testable inside a nested X11 session.
osg::ref_ptr<osgViewer::GraphicsWindow> createGBMWindow(osg::GraphicsContext::Traits* traits);

void bind_GraphicsWindowGBM(py::module_& m);

}
