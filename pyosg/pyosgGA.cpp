#include "pyosgGA.hpp"

namespace pyosgGA {

void bind(py::module_& m) {
	py::class_<osgGA::GUIActionAdapter, detail::GUIActionAdapter>(m, "GUIActionAdapter")
		.def(py::init_alias<>())
		.def("requestRedraw", &osgGA::GUIActionAdapter::requestRedraw)
		.def("requestContinuousUpdate", &osgGA::GUIActionAdapter::requestContinuousUpdate,
			"needed"_a=true)
		.def("requestWarpPointer", &osgGA::GUIActionAdapter::requestWarpPointer)
	;

	py::class_<osgGA::Event, osg::Object, osg::ref_ptr<osgGA::Event>>(m, "Event")
		.def_property("handled", &osgGA::Event::getHandled, &osgGA::Event::setHandled)
		.def_property("time", &osgGA::Event::getTime, &osgGA::Event::setTime)
	;

	auto gea = py::class_<
		osgGA::GUIEventAdapter,
		osgGA::Event,
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
		.def_property_readonly("handled", &osgGA::GUIEventAdapter::getHandled)
	;

	py::class_<
		osgGA::EventVisitor,
		osg::NodeVisitor,
		osg::ref_ptr<osgGA::EventVisitor>
	>(m, "EventVisitor")
		.def(py::init<>())
		.def_property(
			"actionAdapter",
			py::overload_cast<>(&osgGA::EventVisitor::getActionAdapter),
			&osgGA::EventVisitor::setActionAdapter,
			py::return_value_policy::reference
		)
		.def("addEvent", &osgGA::EventVisitor::addEvent)
		.def("removeEvent", &osgGA::EventVisitor::removeEvent)
		.def_property_readonly("eventHandled", &osgGA::EventVisitor::getEventHandled)
		.def("setEventHandled", &osgGA::EventVisitor::setEventHandled)
		.def_property_readonly("events", [](osgGA::EventVisitor& self) {
			py::list events;

			for(auto& event : self.getEvents()) events.append(event);

			return events;
		})
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
		.export_values()
	;

	py::enum_<osgGA::GUIEventAdapter::MouseYOrientation>(gea, "MouseYOrientation")
		.value("Y_INCREASING_UPWARDS", osgGA::GUIEventAdapter::Y_INCREASING_UPWARDS)
		.value("Y_INCREASING_DOWNWARDS", osgGA::GUIEventAdapter::Y_INCREASING_DOWNWARDS)
		.export_values()
	;

	py::enum_<osgGA::GUIEventAdapter::ScrollingMotion>(gea, "ScrollingMotion")
		.value("SCROLL_NONE", osgGA::GUIEventAdapter::SCROLL_NONE)
		.value("SCROLL_LEFT", osgGA::GUIEventAdapter::SCROLL_LEFT)
		.value("SCROLL_RIGHT", osgGA::GUIEventAdapter::SCROLL_RIGHT)
		.value("SCROLL_UP", osgGA::GUIEventAdapter::SCROLL_UP)
		.value("SCROLL_DOWN", osgGA::GUIEventAdapter::SCROLL_DOWN)
		.value("SCROLL_2D", osgGA::GUIEventAdapter::SCROLL_2D)
		.export_values()
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
		detail::GUIEventHandler,
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
		.def(py::init<>())
		.def("clear", &osgGA::EventQueue::clear)
		.def_property_readonly(
			"currentEventState",
			py::overload_cast<>(&osgGA::EventQueue::getCurrentEventState),
			py::return_value_policy::reference_internal
		)

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

		.def("keyPress", [](
			osgGA::EventQueue& self,
			int key,
			double time=0.0,
			int unmodifiedKey=0
		) {
			return self.keyPress(key, time, unmodifiedKey);
		}, "key"_a, "time"_a=0.0, "unmodifiedKey"_a=0)
		.def("keyRelease", [](
			osgGA::EventQueue& self,
			int key,
			double time=0.0,
			int unmodifiedKey=0
		) {
			return self.keyRelease(key, time, unmodifiedKey);
		}, "key"_a, "time"_a=0.0, "unmodifiedKey"_a=0)
		.def("frame", &osgGA::EventQueue::frame, "time"_a=0.0)
		.def("takeEvents", [](osgGA::EventQueue& self) {
			osgGA::EventQueue::Events source;
			py::list events;

			self.takeEvents(source);

			for(auto& event : source) events.append(event);

			return events;
		})
	;

	py::class_<
		osgGA::CameraManipulator,
		detail::CameraManipulator,
		osgGA::GUIEventHandler,
		osg::ref_ptr<osgGA::CameraManipulator>
	>(m, "CameraManipulator")
		.def(py::init_alias<>())
		.def("home", py::overload_cast<
			const osgGA::GUIEventAdapter&,
			osgGA::GUIActionAdapter&
		>(&osgGA::CameraManipulator::home))
		.def("home", py::overload_cast<double>(&osgGA::CameraManipulator::home))
		// Bound as a plain method (not just made overridable in the trampoline) for the same
		// reason updateCamera() is: lets test code (and real callers) invoke it through a
		// genuine C++ virtual call, which is the only way to actually prove a trampoline
		// override fires -- a direct Python-side call on a Python subclass instance always
		// finds the subclass's own method via ordinary attribute lookup regardless of whether
		// the trampoline works at all (see test/osgGA_CameraManipulator.py's
		// test_direct_python_call_is_not_proof_of_real_dispatch).
		.def("computeHomePosition", &osgGA::CameraManipulator::computeHomePosition,
			"camera"_a=nullptr,
			"useBoundingBox"_a=false
		)
		.def_property(
			"node",
			detail::CameraManipulatorSlots::getter<detail::NodeSlot>(
				static_cast<osg::Node*(osgGA::CameraManipulator::*)()>(
					&osgGA::CameraManipulator::getNode
				)
			),
			detail::CameraManipulatorSlots::setter<detail::NodeSlot, osg::Node*>(
				&osgGA::CameraManipulator::setNode
			),
			py::doc("Scene node used for bounds, home-position, and model-size calculations.")
		)
		.def_property(
			"homePosition",
			py::cpp_function([](osgGA::CameraManipulator& self) {
				osg::Vec3d eye, center, up;

				self.getHomePosition(eye, center, up);

				return py::make_tuple(eye, center, up);
			}),
			py::cpp_function([](osgGA::CameraManipulator& self, py::object obj) {
				auto vals = pyx::try_unpack_sequence<osg::Vec3d, osg::Vec3d, osg::Vec3d>(obj);

				if(!vals) throw py::type_error(
					"Expected Vec3d sequence of length 3 (eye, center, up)"
				);

				auto& [eye, center, up] = *vals;

				self.setHomePosition(eye, center, up);
			})
		)
		.def_property(
			"autoComputeHomePosition",
			&osgGA::CameraManipulator::getAutoComputeHomePosition,
			&osgGA::CameraManipulator::setAutoComputeHomePosition
		)
		.def_property(
			"inverseMatrix",
			&osgGA::CameraManipulator::getInverseMatrix,
			&osgGA::CameraManipulator::setByInverseMatrix
		)
		.def_property(
			"matrix",
			&osgGA::CameraManipulator::getMatrix,
			&osgGA::CameraManipulator::setByMatrix
		)
		// Bound as a plain method (not just made overridable in the trampoline above) so a
		// Python decorator manipulator can delegate to an INNER manipulator's own updateCamera()
		// before composing anything on top of it -- e.g. self.inner.updateCamera(camera) -- see
		// aipython/06-camera-effects.md.
		.def("updateCamera", &osgGA::CameraManipulator::updateCamera)
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
		.export_values()
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
