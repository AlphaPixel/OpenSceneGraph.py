#include "pyosgGA.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/GUIEventHandler>
#include <osgGA/EventQueue>
#include <osgGA/TrackballManipulator>

PYOSG_ENABLE_WARNINGS

namespace pyosgGA {

class GUIEventHandler: public osgGA::GUIEventHandler {
public:
	using osgGA::GUIEventHandler::GUIEventHandler;

	bool handle(
		const osgGA::GUIEventAdapter& ea,
		osgGA::GUIActionAdapter& aa,
		osg::Object* obj,
		osg::NodeVisitor* nv
	) override {
		auto r = pyosg::detail::call_override<bool>("handle", this, &ea, &aa);

		// If a Python override exists and gave us a bool, check it.
		if(r.has_value()) {
			// If the event WAS HANDLED (returned True), we're done.
			if(*r) return true;
		}

		// Python does not override OR returned None, so we should keep going.
		return osgGA::GUIEventHandler::handle(ea, aa, obj, nv);
	}
};

void bind(py::module_& m) {
	py::class_<osgGA::GUIActionAdapter>(m, "GUIActionAdapter");

	auto gea = py::class_<
		osgGA::GUIEventAdapter,
		osg::Object,
		osg::ref_ptr<osgGA::GUIEventAdapter>
	>(m, "GUIEventAdapter")
		// TODO: Continue converting these down below!
		.def_property_readonly("x", &osgGA::GUIEventAdapter::getX)
		.def_property_readonly("y", &osgGA::GUIEventAdapter::getY)
		.def_property_readonly("buttonMask", &osgGA::GUIEventAdapter::getButtonMask)
		.def_property_readonly("mask", &osgGA::GUIEventAdapter::getButtonMask)
		.def_property_readonly("button", &osgGA::GUIEventAdapter::getButton)
		.def_property_readonly("scrollingMotion", &osgGA::GUIEventAdapter::getScrollingMotion)
		.def_property_readonly("modKeyMask", &osgGA::GUIEventAdapter::getModKeyMask)
		.def_property_readonly("key", &osgGA::GUIEventAdapter::getKey)
	;

	py::enum_<osgGA::GUIEventAdapter::EventType>(gea, "EventType")
		.value("NONE", osgGA::GUIEventAdapter::NONE)
		.value("PUSH", osgGA::GUIEventAdapter::PUSH)
		.value("RELEASE", osgGA::GUIEventAdapter::RELEASE)
		.value("DOUBLECLICK", osgGA::GUIEventAdapter::DOUBLECLICK)
		.value("DRAG", osgGA::GUIEventAdapter::DRAG)
		.value("MOVE", osgGA::GUIEventAdapter::MOVE)
		.value("KEYDOWN", osgGA::GUIEventAdapter::KEYDOWN)
		.value("KEYUP", osgGA::GUIEventAdapter::KEYUP)
		.value("FRAME", osgGA::GUIEventAdapter::FRAME)
		.value("RESIZE", osgGA::GUIEventAdapter::RESIZE)
		.value("SCROLL", osgGA::GUIEventAdapter::SCROLL)
		.value("PEN_PRESSURE", osgGA::GUIEventAdapter::PEN_PRESSURE)
		.value("PEN_ORIENTATION", osgGA::GUIEventAdapter::PEN_ORIENTATION)
		.value("PEN_PROXIMITY_ENTER", osgGA::GUIEventAdapter::PEN_PROXIMITY_ENTER)
		.value("PEN_PROXIMITY_LEAVE", osgGA::GUIEventAdapter::PEN_PROXIMITY_LEAVE)
		.value("CLOSE_WINDOW", osgGA::GUIEventAdapter::CLOSE_WINDOW)
		.value("QUIT_APPLICATION", osgGA::GUIEventAdapter::QUIT_APPLICATION)
		.value("USER", osgGA::GUIEventAdapter::USER)
	;

	py::enum_<osgGA::GUIEventAdapter::MouseYOrientation>(gea, "MouseYOrientation")
		.value("Y_INCREASING_UPWARDS", osgGA::GUIEventAdapter::Y_INCREASING_UPWARDS)
		.value("Y_INCREASING_DOWNWARDS", osgGA::GUIEventAdapter::Y_INCREASING_DOWNWARDS)
	;

	py::enum_<osgGA::GUIEventAdapter::ScrollingMotion>(gea, "ScrollingMotion")
		.value("SCROLL_NONE", osgGA::GUIEventAdapter::SCROLL_NONE)
		.value("SCROLL_LEFT", osgGA::GUIEventAdapter::SCROLL_LEFT)
		.value("SCROLL_RIGHT", osgGA::GUIEventAdapter::SCROLL_RIGHT)
		.value("SCROLL_UP", osgGA::GUIEventAdapter::SCROLL_UP)
		.value("SCROLL_DOWN", osgGA::GUIEventAdapter::SCROLL_DOWN)
		.value("SCROLL_2D", osgGA::GUIEventAdapter::SCROLL_2D)
	;

	gea
		// TODO: Should this ACTUALLy be `eventType` instead?
		.def_property(
			"type",
			&osgGA::GUIEventAdapter::getEventType,
			&osgGA::GUIEventAdapter::setEventType
		)
		.def_property(
			"mouseYOrientation",
			&osgGA::GUIEventAdapter::getMouseYOrientation,
			&osgGA::GUIEventAdapter::setMouseYOrientation
		)
	;

	py::class_<
		osgGA::GUIEventHandler,
		GUIEventHandler,
		osg::Object,
		osg::ref_ptr<osgGA::GUIEventHandler>
	>(m, "GUIEventHandler")
		.def(py::init_alias<>())
		.def("handle", [](
			osgGA::GUIEventHandler& self,
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa
		) {
			return self.handle(ea, aa, nullptr, nullptr);
		})
	;

	py::class_<
		osgGA::EventQueue,
		osg::Referenced,
		osg::ref_ptr<osgGA::EventQueue>
	>(m, "EventQueue")
		.def("getCurrentEventState", py::overload_cast<>(&osgGA::EventQueue::getCurrentEventState))

		.def("windowResize", py::overload_cast<
			int, int, int, int
		>(&osgGA::EventQueue::windowResize))
		.def("windowResize", py::overload_cast<
			int, int, int, int, double
		>(&osgGA::EventQueue::windowResize))

		.def("mouseButtonPress", py::overload_cast<
			float, float, unsigned int
		>(&osgGA::EventQueue::mouseButtonPress))
		.def("mouseButtonPress", py::overload_cast<
			float, float, unsigned int, double
		>(&osgGA::EventQueue::mouseButtonPress))

		.def("mouseButtonRelease", py::overload_cast<
			float, float, unsigned int
		>(&osgGA::EventQueue::mouseButtonRelease))
		.def("mouseButtonRelease", py::overload_cast<
			float, float, unsigned int, double
		>(&osgGA::EventQueue::mouseButtonRelease))

		.def("mouseMotion", py::overload_cast<
			float, float
		>(&osgGA::EventQueue::mouseMotion))
		.def("mouseMotion", py::overload_cast<
			float, float, double
		>(&osgGA::EventQueue::mouseMotion))

		.def("mouseScroll", py::overload_cast<
			osgGA::GUIEventAdapter::ScrollingMotion
		>(&osgGA::EventQueue::mouseScroll))
		.def("mouseScroll", py::overload_cast<
			osgGA::GUIEventAdapter::ScrollingMotion, double
		>(&osgGA::EventQueue::mouseScroll))
	;

	// TODO: This WILL NEED a trampoline class in the `detail` namespace!
	py::class_<
		osgGA::CameraManipulator,
		osgGA::GUIEventHandler,
		osg::ref_ptr<osgGA::CameraManipulator>
	>(m, "CameraManipulator")
		// coordianteFrame
		// sideVector
		// frontVector
		// upVector
	;

	auto sm = py::class_<
		osgGA::StandardManipulator,
		osgGA::CameraManipulator,
		osg::ref_ptr<osgGA::StandardManipulator>
	>(m, "StandardManipulator");

	py::enum_<osgGA::StandardManipulator::UserInteractionFlags>(sm, "UserInteractionFlags")
		.value("UPDATE_MODEL_SIZE", osgGA::StandardManipulator::UPDATE_MODEL_SIZE)
		.value("COMPUTE_HOME_USING_BBOX", osgGA::StandardManipulator::COMPUTE_HOME_USING_BBOX)
		.value("PROCESS_MOUSE_WHEEL", osgGA::StandardManipulator::PROCESS_MOUSE_WHEEL)
		.value(
			"SET_CENTER_ON_WHEEL_FORWARD_MOVEMENT",
			osgGA::StandardManipulator::SET_CENTER_ON_WHEEL_FORWARD_MOVEMENT
		)
		.value("DEFAULT_SETTINGS", osgGA::StandardManipulator::DEFAULT_SETTINGS)
	;

	py::class_<
		osgGA::OrbitManipulator,
		osgGA::StandardManipulator,
		osg::ref_ptr<osgGA::OrbitManipulator>
	>(m, "OrbitManipulator");

	py::class_<
		osgGA::TrackballManipulator,
		osgGA::CameraManipulator,
		osg::ref_ptr<osgGA::TrackballManipulator>
	>(m, "TrackballManipulator")
		.def(py::init<int>(), "flags"_a=osgGA::StandardManipulator::DEFAULT_SETTINGS)
	;
}

}
