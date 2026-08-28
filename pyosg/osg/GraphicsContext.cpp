#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/ArgumentParser>
#include <osg/GraphicsContext>

OSGX_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

void bind_GraphicsContext(py::module_& m) {
	py::class_<
		osg::DisplaySettings,
		osg::Referenced,
		osg::ref_ptr<osg::DisplaySettings>
	>(
		m,
		"DisplaySettings",
		"Process-wide rendering configuration (multisampling, stereo, compression, etc.) "
		"shared by every GraphicsContext."
	)
		.def(py::init<>(), "Construct with OSG's built-in default settings.")
		.def(py::init<osg::ArgumentParser&>(),
			"Construct then apply OSG_* environment variables and any recognized "
			"--display-settings-style command-line options via the given ArgumentParser."
		)
		// I know the syntax here LOOKS WEIRD, but there's a lot of "magic" happening; see:
		// https://pybind11.readthedocs.io/en/latest/advanced/classes.html?utm_source=chatgpt.com#static-properties
		.def_property_readonly_static(
			"instance",
			[](py::object cls) { return osg::DisplaySettings::instance(); },
			"The process-wide singleton DisplaySettings that GraphicsContexts consult when "
			"none is explicitly assigned to their Traits."
		)
		.def_property(
			"numMultiSamples",
			&osg::DisplaySettings::getNumMultiSamples,
			&osg::DisplaySettings::setNumMultiSamples,
			"Requested MSAA sample count; 0 disables multisampling."
		)
		// The REQUESTED GL context (from OSG_GL_VERSION/OSG_GL_CONTEXT_VERSION and
		// OSG_GL_CONTEXT_PROFILE_MASK, read automatically into these fields the moment this
		// singleton is first constructed) -- compare against the ACTUALLY negotiated context
		// via State.glExtensions.glVersion to confirm a request was honored, not just made.
		.def_property(
			"glContextVersion",
			&osg::DisplaySettings::getGLContextVersion,
			&osg::DisplaySettings::setGLContextVersion,
			"Requested \"major.minor\" GL context version string, e.g. \"4.3\"."
		)
		.def_property(
			"glContextProfileMask",
			&osg::DisplaySettings::getGLContextProfileMask,
			&osg::DisplaySettings::setGLContextProfileMask,
			"Requested GL_CONTEXT_PROFILE_MASK bits (core/compatibility)."
		)
		.def_property(
			"glContextFlags",
			&osg::DisplaySettings::getGLContextFlags,
			&osg::DisplaySettings::setGLContextFlags,
			"Requested GL_CONTEXT_FLAGS bits (e.g. forward-compatible, debug)."
		)
	;

	auto gc = py::class_<
		osg::GraphicsContext,
		osg::Object,
		osg::ref_ptr<osg::GraphicsContext>
	>(
		m,
		"GraphicsContext",
		"An OpenGL context and its associated drawing surface (window, pbuffer, or FBO target)."
	)
		.def("resized", &osg::GraphicsContext::resized,
			"Notify the context that its window/surface was resized to (x, y, width, height)."
		)
		.def("runOperations", &osg::GraphicsContext::runOperations,
			"Make this context current and run every Operation queued on it, in order."
		)
		.def("valid", &osg::GraphicsContext::valid,
			"Return whether the underlying GL context/window still exists."
		)
		// Needed for embedding under a widget toolkit (Qt's QOpenGLWidget, etc.) that owns its
		// own non-zero "default" FBO: RenderStage rebinds framebuffer 0 by default after every
		// FBO-camera pass (RenderStage.cpp reads getDefaultFboId(), which starts at 0), so a
		// final pass with no renderTargetImplementation silently ends up drawing into the REAL
		// GL default framebuffer -- invisible to a compositor that only reads its own FBO --
		// unless this is set to match e.g. QOpenGLWidget.defaultFramebufferObject().
		.def_property("defaultFboId",
			&osg::GraphicsContext::getDefaultFboId,
			&osg::GraphicsContext::setDefaultFboId,
			"GL FBO id RenderStage rebinds as \"the default framebuffer\" after every FBO-camera "
			"pass; set to a host toolkit's real FBO (e.g. QOpenGLWidget.defaultFramebufferObject()) "
			"when embedding, or the final pass silently draws into GL's true default FBO."
		)
		// State (and thus .state.contextID) is only valid once the context has been realized --
		// this is how a BufferObject/Texture's compiled GL object id can be reached from plain
		// script code, outside of a draw callback's RenderInfo.
		.def_property_readonly(
			"state",
			static_cast<osg::State*(osg::GraphicsContext::*)()>(&osg::GraphicsContext::getState),
			py::return_value_policy::reference,
			"This context's osg::State; only valid (non-crashing to use for GL work) once the "
			"context has been realized."
		)
		// The Traits this context was actually realized with -- e.g. traits.glContextVersion
		// to confirm what a DisplaySettings request (see DisplaySettings.glContextVersion
		// above) resolved to on THIS context specifically, independent of what
		// State.glExtensions.glVersion later reports the driver actually granted.
		.def_property_readonly("traits", &osg::GraphicsContext::getTraits,
			"The Traits this context was actually realized with."
		)
	;

	py::class_<osg::GraphicsContext::ScreenIdentifier>(gc, "ScreenIdentifier",
		"Identifies an X11/Windows display+screen pair (hostname, display number, screen "
		"number) that a GraphicsContext should be realized on."
	)
		.def(py::init<>(), "Identify the default display/screen.")
		.def(py::init<int>(), "Identify a screen number on the default display.")
		.def(py::init<const std::string&, int, int>(),
			"Identify (hostName, displayNum, screenNum) explicitly."
		)
		.def_property_readonly("displayName", &osg::GraphicsContext::ScreenIdentifier::displayName,
			"The \"hostName:displayNum.screenNum\" string form of this identifier."
		)
	;

	// struct OSG_EXPORT Traits : public osg::Referenced, public ScreenIdentifier
	//
	// Traits IS-A osg::Referenced, and GraphicsContext keeps its own ref_ptr<Traits> internally
	// (_traits), so this MUST use the ref_ptr holder -- otherwise pybind11 defaults to
	// unique_ptr<Traits>, giving the object two independent owners (Python's unique_ptr and OSG's
	// internal ref_ptr) that both unconditionally delete it, causing a double-free.
	py::class_<
		osg::GraphicsContext::Traits,
		osg::ref_ptr<osg::GraphicsContext::Traits>
	>(gc, "Traits",
		"The requested configuration (position, size, pixel format, GL version/profile, etc.) "
		"a GraphicsContext is realized from; assign to GraphicsContext.traits before realize()."
	)
		.def(py::init<>(), "Construct with OSG's built-in defaults.")
		.def(py::init<osg::DisplaySettings*>(), "ds"_a=nullptr,
			"Construct, seeding GL version/profile/flags from a DisplaySettings (or the "
			"process-wide singleton if ds is None)."
		)
		.def_readwrite("x", &osg::GraphicsContext::Traits::x, "Window/surface X position in pixels.")
		.def_readwrite("y", &osg::GraphicsContext::Traits::y, "Window/surface Y position in pixels.")
		.def_readwrite("width", &osg::GraphicsContext::Traits::width, "Surface width in pixels.")
		.def_readwrite("height", &osg::GraphicsContext::Traits::height, "Surface height in pixels.")
		.def_readwrite("glContextVersion", &osg::GraphicsContext::Traits::glContextVersion,
			"Requested \"major.minor\" GL context version string."
		)
		.def_readwrite("glContextProfileMask", &osg::GraphicsContext::Traits::glContextProfileMask,
			"Requested GL_CONTEXT_PROFILE_MASK bits (core/compatibility)."
		)
		.def_readwrite("glContextFlags", &osg::GraphicsContext::Traits::glContextFlags,
			"Requested GL_CONTEXT_FLAGS bits (e.g. forward-compatible, debug)."
		)
	;

	// struct ScreenSettings {
	// struct WindowingSystemInterface : public osg::Referenced
}

}
