#include "../pyosg.hpp"

#include <string>
#include <vector>

namespace osgViewer { class Viewer; }

namespace pyosg_linux {

void alwaysOnTop(osgViewer::Viewer& viewer, bool enabled=true);

// A single XRandR monitor, in real (possibly non-adjacent/overlapping) root-window coordinates --
// see ai/context-todo-linuxwindow.md / reference_linuxwindow_todo memory for why this can't be
// assumed to be a flush left-to-right layout.
struct Monitor {
	std::string name;

	int x = 0;
	int y = 0;
	int width = 0;
	int height = 0;

	bool primary = false;
};

std::vector<Monitor> listMonitors();

// Repositions (and optionally resizes) an already-realized X11 window in one call: moves the real
// X11 window via XMoveResizeWindow, then calls GraphicsContext::resized() so OSG's own viewport/
// camera bookkeeping stays in sync. Pass width/height <= 0 to keep the window's current size.
void moveWindow(osgViewer::Viewer& viewer, int x, int y, int width=-1, int height=-1);

void bind(py::module_& m);

}
