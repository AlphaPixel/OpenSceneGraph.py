#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/ArgumentParser>
#include <osg/GraphicsContext>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

// namespace detail {}

void bind_GraphicsContext(py::module_& m) {
	py::class_<
		osg::DisplaySettings,
		osg::Referenced,
		osg::ref_ptr<osg::DisplaySettings>
	>(m, "DisplaySettings")
		.def(py::init<>())
		.def(py::init<osg::ArgumentParser&>())
	;

	auto gc = py::class_<
		osg::GraphicsContext,
		osg::Object,
		osg::ref_ptr<osg::GraphicsContext>
	>(m, "GraphicsContext")
		.def("resized", &osg::GraphicsContext::resized)
		.def("runOperations", &osg::GraphicsContext::runOperations)
	;

	py::class_<osg::GraphicsContext::ScreenIdentifier>(gc, "ScreenIdentifier")
		.def(py::init<>())
		.def(py::init<int>())
		.def(py::init<const std::string&, int, int>())
		.def_property_readonly("displayName", &osg::GraphicsContext::ScreenIdentifier::displayName)
	;

	// struct OSG_EXPORT Traits : public osg::Referenced, public ScreenIdentifier
	py::class_<osg::GraphicsContext::Traits>(gc, "Traits")
		.def(py::init<>())
		.def(py::init<osg::DisplaySettings*>(), "ds"_a=nullptr)
		.def_readwrite("x", &osg::GraphicsContext::Traits::x)
		.def_readwrite("y", &osg::GraphicsContext::Traits::y)
		.def_readwrite("width", &osg::GraphicsContext::Traits::width)
		.def_readwrite("height", &osg::GraphicsContext::Traits::height)
	;

	// struct ScreenSettings {
	// struct WindowingSystemInterface : public osg::Referenced
}

}
