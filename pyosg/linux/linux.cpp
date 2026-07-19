#include "linux.hpp"

#include "GraphicsWindowEGL.hpp"
#include "GraphicsWindowGBM.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgViewer/Viewer>
#include <osgViewer/api/X11/GraphicsWindowX11>

#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/extensions/Xrandr.h>

PYOSG_ENABLE_WARNINGS

namespace pyosg_linux {

namespace detail {

// The EWMH `_NET_WM_STATE` ClientMessage protocol every X11 window manager is expected to
// honor; see: https://specifications.freedesktop.org/wm-spec/latest/ar01s05.html#NETWMSTATE
void send_net_wm_state(Display* display, Window window, bool add, const char* state_name) {
	Atom wm_state = XInternAtom(display, "_NET_WM_STATE", False);
	Atom state = XInternAtom(display, state_name, False);

	XEvent event{};

	event.xclient.type = ClientMessage;
	event.xclient.window = window;
	event.xclient.message_type = wm_state;
	event.xclient.format = 32;
	event.xclient.data.l[0] = add ? 1 : 0; // _NET_WM_STATE_ADD : _NET_WM_STATE_REMOVE
	event.xclient.data.l[1] = static_cast<long>(state);
	event.xclient.data.l[2] = 0;
	event.xclient.data.l[3] = 1; // source indication: normal application
	event.xclient.data.l[4] = 0;

	XSendEvent(
		display,
		DefaultRootWindow(display),
		False,
		SubstructureRedirectMask | SubstructureNotifyMask,
		&event
	);

	XFlush(display);
}

}

void alwaysOnTop(osgViewer::Viewer& viewer, bool enabled) {
	auto* camera = viewer.getCamera();

	if(!camera) return;

	auto* gw = dynamic_cast<osgViewer::GraphicsWindowX11*>(camera->getGraphicsContext());

	if(!gw) return;

	detail::send_net_wm_state(gw->getEventDisplay(), gw->getWindow(), enabled, "_NET_WM_STATE_ABOVE");
}

std::vector<Monitor> listMonitors() {
	std::vector<Monitor> monitors;

	Display* display = XOpenDisplay(nullptr);

	if(!display) return monitors;

	int count = 0;
	XRRMonitorInfo* info = XRRGetMonitors(display, DefaultRootWindow(display), True, &count);

	if(info) {
		for(int i = 0; i < count; i++) {
			Monitor monitor;

			char* name = XGetAtomName(display, info[i].name);

			monitor.name = name ? name : "";
			monitor.x = info[i].x;
			monitor.y = info[i].y;
			monitor.width = info[i].width;
			monitor.height = info[i].height;
			monitor.primary = info[i].primary != 0;

			if(name) XFree(name);

			monitors.push_back(monitor);
		}

		XRRFreeMonitors(info);
	}

	XCloseDisplay(display);

	return monitors;
}

void moveWindow(osgViewer::Viewer& viewer, int x, int y, int width, int height) {
	auto* camera = viewer.getCamera();

	if(!camera) return;

	auto* gw = dynamic_cast<osgViewer::GraphicsWindowX11*>(camera->getGraphicsContext());

	if(!gw) return;

	Display* display = gw->getEventDisplay();
	Window window = gw->getWindow();

	const osg::GraphicsContext::Traits* traits = gw->getTraits();
	int w = width > 0 ? width : traits->width;
	int h = height > 0 ? height : traits->height;

	XMoveResizeWindow(display, window, x, y, static_cast<unsigned int>(w), static_cast<unsigned int>(h));
	XFlush(display);

	gw->resized(x, y, w, h);
}

void bind(py::module_& m) {
	m.def(
		"alwaysOnTop",
		&alwaysOnTop,
		"viewer"_a,
		"enabled"_a=true,
		"Pin the viewer's native X11 window above other windows (EWMH _NET_WM_STATE_ABOVE)."
	);

	py::class_<Monitor>(m, "Monitor")
		.def_readonly("name", &Monitor::name)
		.def_readonly("x", &Monitor::x)
		.def_readonly("y", &Monitor::y)
		.def_readonly("width", &Monitor::width)
		.def_readonly("height", &Monitor::height)
		.def_readonly("primary", &Monitor::primary)
		.def("__repr__", [](const Monitor& self) {
			return
				"Monitor(name='"s + self.name + "', "
				"x="s + std::to_string(self.x) + ", "
				"y="s + std::to_string(self.y) + ", "
				"width="s + std::to_string(self.width) + ", "
				"height="s + std::to_string(self.height) + ", "
				"primary="s + (self.primary ? "True"s : "False"s) + ")"s
			;
		})
	;

	m.def(
		"listMonitors",
		&listMonitors,
		"Query the real XRandR monitor layout (position/size in root-window coordinates). Monitors "
		"are NOT assumed to be flush/adjacent -- use these rects directly for placement math."
	);

	m.def(
		"moveWindow",
		&moveWindow,
		"viewer"_a,
		"x"_a,
		"y"_a,
		"width"_a=-1,
		"height"_a=-1,
		"Reposition (and optionally resize) an already-realized X11 window, keeping OSG's own "
		"viewport bookkeeping in sync. Pass width/height <= 0 to keep the current size."
	);

	bind_GraphicsWindowEGL(m);
	bind_GraphicsWindowGBM(m);
}

}
