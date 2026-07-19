#include "GraphicsWindowEGL.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Notify>
#include <osg/State>
#include <osgViewer/GraphicsWindow>

PYOSG_ENABLE_WARNINGS

#include <EGL/egl.h>
#include <EGL/eglext.h>

#include <X11/Xlib.h>

#include <utility>

namespace pyosg_linux {

namespace detail {

// Adapted as-is from ~/dev/misc/osg/src/miscosg-graphics-window-egl.cpp: opens a bare X11
// window (no WM decoration/events beyond mapping) for EGL to drive via eglCreateWindowSurface().
std::pair<Display*, Window> createEGLDisplayWindow(unsigned int width, unsigned int height) {
	Display* display = XOpenDisplay(nullptr);

	if(!display) {
		osg::notify(osg::FATAL) << "EGL: XOpenDisplay failed" << std::endl;

		return {nullptr, 0};
	}

	Window root = DefaultRootWindow(display);
	Window win = XCreateSimpleWindow(display, root, 0, 0, width, height, 0, 0, 0);

	XMapWindow(display, win);
	XStoreName(display, win, "OSG EGL Window");

	return {display, win};
}

class GraphicsWindowEGL: public osgViewer::GraphicsWindow {
public:
	explicit GraphicsWindowEGL(osg::GraphicsContext::Traits* traits) {
		_traits = traits;

		init();
	}

	~GraphicsWindowEGL() override {
		close(true);
	}

	bool valid() const override { return _valid; }

	void init() {
		if(_initialized) return;

		if(!_traits) {
			osg::notify(osg::FATAL) << "EGL: no traits" << std::endl;

			return;
		}

		_traits->windowDecoration = false;
		_traits->pbuffer = false;

		auto [display, win] = createEGLDisplayWindow(
			static_cast<unsigned int>(_traits->width),
			static_cast<unsigned int>(_traits->height)
		);

		if(!display) return;

		_eglDisplay = eglGetDisplay(reinterpret_cast<EGLNativeDisplayType>(display));

		if(_eglDisplay == EGL_NO_DISPLAY) {
			osg::notify(osg::FATAL) << "EGL: eglGetDisplay failed" << std::endl;

			return;
		}

		if(!eglInitialize(_eglDisplay, &_eglMajor, &_eglMinor)) {
			osg::notify(osg::FATAL) << "EGL: eglInitialize failed" << std::endl;

			return;
		}

		if(!eglBindAPI(EGL_OPENGL_API)) {
			osg::notify(osg::FATAL) << "EGL: eglBindAPI(EGL_OPENGL_API) failed" << std::endl;

			return;
		}

		const EGLint configAttribs[] = {
			EGL_SURFACE_TYPE, EGL_WINDOW_BIT,
			EGL_RENDERABLE_TYPE, EGL_OPENGL_BIT,
			EGL_RED_SIZE, 8,
			EGL_GREEN_SIZE, 8,
			EGL_BLUE_SIZE, 8,
			EGL_ALPHA_SIZE, 8,
			EGL_DEPTH_SIZE, 24,
			EGL_NONE
		};

		EGLint numConfigs = 0;

		if(!eglChooseConfig(_eglDisplay, configAttribs, &_eglConfig, 1, &numConfigs) || numConfigs < 1) {
			osg::notify(osg::FATAL) << "EGL: eglChooseConfig failed" << std::endl;

			return;
		}

		_eglSurface = eglCreateWindowSurface(
			_eglDisplay,
			_eglConfig,
			reinterpret_cast<EGLNativeWindowType>(win),
			nullptr
		);

		if(_eglSurface == EGL_NO_SURFACE) {
			osg::notify(osg::FATAL) << "EGL: eglCreateWindowSurface failed" << std::endl;

			return;
		}

		_eglContext = eglCreateContext(_eglDisplay, _eglConfig, EGL_NO_CONTEXT, nullptr);

		if(_eglContext == EGL_NO_CONTEXT) {
			osg::notify(osg::FATAL) << "EGL: eglCreateContext failed" << std::endl;

			return;
		}

		if(!eglMakeCurrent(_eglDisplay, _eglSurface, _eglSurface, _eglContext)) {
			osg::notify(osg::FATAL) << "EGL: initial eglMakeCurrent failed" << std::endl;

			return;
		}

		osg::ref_ptr<osg::State> state = new osg::State();

		state->setGraphicsContext(this);
		state->setContextID(osg::GraphicsContext::createNewContextID());

		setState(state);

		_initialized = true;
		_realized = true;
		_valid = true;

		osg::notify(osg::NOTICE)
			<< "EGL initialized: " << _eglMajor << "." << _eglMinor
			<< " surface=" << _traits->width << "x" << _traits->height
			<< std::endl
		;
	}

	bool realizeImplementation() override {
		if(!_initialized) init();

		_realized = _valid;

		return _realized;
	}

	bool isRealizedImplementation() const override { return _realized; }

	bool makeCurrentImplementation() override {
		bool ok = eglMakeCurrent(_eglDisplay, _eglSurface, _eglSurface, _eglContext) == EGL_TRUE;

		if(!ok) osg::notify(osg::FATAL) << "EGL: eglMakeCurrent failed" << std::endl;

		return ok;
	}

	bool releaseContextImplementation() override {
		return eglMakeCurrent(_eglDisplay, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT) == EGL_TRUE;
	}

	void swapBuffersImplementation() override {
		eglSwapBuffers(_eglDisplay, _eglSurface);
	}

	void closeImplementation() override {
		if(_eglDisplay != EGL_NO_DISPLAY) {
			if(_eglContext != EGL_NO_CONTEXT) eglDestroyContext(_eglDisplay, _eglContext);
			if(_eglSurface != EGL_NO_SURFACE) eglDestroySurface(_eglDisplay, _eglSurface);

			eglTerminate(_eglDisplay);
		}

		_eglDisplay = EGL_NO_DISPLAY;
		_eglContext = EGL_NO_CONTEXT;
		_eglSurface = EGL_NO_SURFACE;
		_eglConfig = nullptr;

		_initialized = false;
		_realized = false;
		_valid = false;
	}

private:
	bool _valid = false;
	bool _initialized = false;
	bool _realized = false;

	EGLDisplay _eglDisplay = EGL_NO_DISPLAY;
	EGLContext _eglContext = EGL_NO_CONTEXT;
	EGLSurface _eglSurface = EGL_NO_SURFACE;
	EGLConfig _eglConfig = nullptr;

	EGLint _eglMajor = 0;
	EGLint _eglMinor = 0;
};

}

osg::ref_ptr<osgViewer::GraphicsWindow> createEGLWindow(osg::GraphicsContext::Traits* traits) {
	return new detail::GraphicsWindowEGL(traits);
}

void bind_GraphicsWindowEGL(py::module_& m) {
	m.def(
		"createEGLWindow",
		&createEGLWindow,
		"traits"_a,
		"Create an X11 window driven by EGL (instead of GLX). Skeleton/proof-of-concept: assign "
		"the result to `camera.graphicsContext`."
	);
}

}
