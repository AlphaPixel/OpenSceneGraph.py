#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/View>

OSGX_ENABLE_WARNINGS

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	constexpr size_t CameraSlot = 0;

	using ViewSlots = pyx::PropertySlots<osg::View, 1>;
	using ViewStorage = pyx::ProxyStorageOSG<osg::View, ViewSlots>;
}

void bind_View(py::module_& m) {
	py::class_<osg::View, osg::Object, osg::ref_ptr<osg::View>>(
		m,
		"View",
		"Base class pairing a scene (via a Camera) with a FrameStamp, the common ancestor of "
		"osgViewer.View/Viewer."
	)
		.def(py::init<>(), "Construct a View with no camera and no scene data yet assigned.")
		.def_property(
			"camera",
			detail::ViewSlots::getter<detail::CameraSlot>(
				py::overload_cast<>(&osg::View::getCamera)
			),
			detail::ViewSlots::setter<detail::CameraSlot, osg::Camera*>(&osg::View::setCamera),
			"This View's master Camera, holding the view/projection matrices and render target "
			"its scene is drawn through."
		)
		.def_property_readonly("frameStamp",
			py::overload_cast<>(&osg::View::getFrameStamp, py::const_),
			py::return_value_policy::reference,
			"The FrameStamp (frame number, reference/simulation time) this View was last updated with."
		)
	;
}

}
