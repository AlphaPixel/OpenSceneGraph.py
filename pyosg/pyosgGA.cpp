#include "pyosgGA.hpp"

namespace pyosgGA {

void bind(py::module_& m) {
	py::class_<osgGA::GUIActionAdapter, detail::GUIActionAdapter>(
		m,
		"GUIActionAdapter",
		"Interface an event handler uses to request a redraw, continuous updates, or a "
		"pointer warp from the windowing system, without depending on it directly."
	)
		.def(py::init_alias<>(), "Create a GUI action adapter.")
		.def("requestRedraw", &osgGA::GUIActionAdapter::requestRedraw,
			"Request that the view redraw at the next opportunity."
		)
		.def("requestContinuousUpdate", &osgGA::GUIActionAdapter::requestContinuousUpdate,
			"needed"_a=true,
			"Enable or disable continuous updates."
		)
		.def("requestWarpPointer", &osgGA::GUIActionAdapter::requestWarpPointer,
			"Request that the window system move the pointer."
		)
	;

	py::class_<osgGA::Event, osg::Object, osg::ref_ptr<osgGA::Event>>(
		m,
		"Event",
		"Base class for a single GUI event (see GUIEventAdapter) with a timestamp and a "
		"handled flag."
	)
		.def_property("handled", &osgGA::Event::getHandled, &osgGA::Event::setHandled,
			"Whether an event handler has consumed this event."
		)
		.def_property("time", &osgGA::Event::getTime, &osgGA::Event::setTime,
			"Event timestamp in seconds."
		)
	;

	auto gea = py::class_<
		osgGA::GUIEventAdapter,
		osgGA::Event,
		osg::ref_ptr<osgGA::GUIEventAdapter>
	>(
		m,
		"GUIEventAdapter",
		"A concrete Event carrying mouse/keyboard/window state (position, buttons, key, "
		"scroll) for a single input or window event."
	)
		// TODO: Continue converting these down below!
		.def_property_readonly("x", &osgGA::GUIEventAdapter::getX, "Pointer x coordinate.")
		.def_property_readonly("y", &osgGA::GUIEventAdapter::getY, "Pointer y coordinate.")
		.def_property_readonly("buttonMask", &osgGA::GUIEventAdapter::getButtonMask,
			"Bit mask of currently pressed mouse buttons."
		)
		.def_property_readonly("mask", &osgGA::GUIEventAdapter::getButtonMask,
			"Alias for buttonMask."
		)
		.def_property_readonly("button", &osgGA::GUIEventAdapter::getButton,
			"Mouse button associated with this event."
		)
		.def_property_readonly("scrollingMotion", &osgGA::GUIEventAdapter::getScrollingMotion,
			"Scroll direction associated with this event."
		)
		.def_property_readonly("modKeyMask", &osgGA::GUIEventAdapter::getModKeyMask,
			"Bit mask of active modifier keys."
		)
		.def_property_readonly("key", &osgGA::GUIEventAdapter::getKey,
			"Key code associated with this event."
		)
		.def_property_readonly("handled", &osgGA::GUIEventAdapter::getHandled,
			"Whether an event handler has consumed this event."
		)
	;

	py::class_<
		osgGA::EventVisitor,
		osg::NodeVisitor,
		osg::ref_ptr<osgGA::EventVisitor>
	>(
		m,
		"EventVisitor",
		"A NodeVisitor that dispatches queued GUIEventAdapter events to each Node's "
		"eventCallback during the event traversal."
	)
		.def(py::init<>(), "Create an event visitor.")
		.def_property(
			"actionAdapter",
			py::overload_cast<>(&osgGA::EventVisitor::getActionAdapter),
			&osgGA::EventVisitor::setActionAdapter,
			py::return_value_policy::reference,
			"Action adapter used to service event-handler requests."
		)
		.def("addEvent", &osgGA::EventVisitor::addEvent, "Queue an event for dispatch.")
		.def("removeEvent", &osgGA::EventVisitor::removeEvent, "Remove an event from the queue.")
		.def_property_readonly("eventHandled", &osgGA::EventVisitor::getEventHandled,
			"Whether the current event was handled."
		)
		.def("setEventHandled", &osgGA::EventVisitor::setEventHandled,
			"Mark the current event as handled or unhandled."
		)
		.def_property_readonly("events", [](osgGA::EventVisitor& self) {
			py::list events;

			for(auto& event : self.getEvents()) events.append(event);

			return events;
		}, "The events queued for dispatch.")
	;

	py::enum_<osgGA::GUIEventAdapter::EventType>(gea, "EventType",
		"Classify the kind of GUI event."
	)
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

	py::enum_<osgGA::GUIEventAdapter::MouseYOrientation>(gea, "MouseYOrientation",
		"Describe which vertical direction increases pointer y."
	)
		.value("Y_INCREASING_UPWARDS", osgGA::GUIEventAdapter::Y_INCREASING_UPWARDS)
		.value("Y_INCREASING_DOWNWARDS", osgGA::GUIEventAdapter::Y_INCREASING_DOWNWARDS)
		.export_values()
	;

	py::enum_<osgGA::GUIEventAdapter::ScrollingMotion>(gea, "ScrollingMotion",
		"Describe the direction of a scroll event."
	)
		.value("SCROLL_NONE", osgGA::GUIEventAdapter::SCROLL_NONE)
		.value("SCROLL_LEFT", osgGA::GUIEventAdapter::SCROLL_LEFT)
		.value("SCROLL_RIGHT", osgGA::GUIEventAdapter::SCROLL_RIGHT)
		.value("SCROLL_UP", osgGA::GUIEventAdapter::SCROLL_UP)
		.value("SCROLL_DOWN", osgGA::GUIEventAdapter::SCROLL_DOWN)
		.value("SCROLL_2D", osgGA::GUIEventAdapter::SCROLL_2D)
		.export_values()
	;

	// Was entirely unbound -- ea.button/ea.buttonMask (both already bound above) returned a raw
	// int with no Python-side names to compare against, forcing callers to hardcode magic numbers
	// (LEFT=1, MIDDLE=2, RIGHT=4) to check which button an event carries.
	py::enum_<osgGA::GUIEventAdapter::MouseButtonMask>(gea, "MouseButtonMask",
		"Name mouse-button bit-mask values."
	)
		.value("LEFT_MOUSE_BUTTON", osgGA::GUIEventAdapter::LEFT_MOUSE_BUTTON)
		.value("MIDDLE_MOUSE_BUTTON", osgGA::GUIEventAdapter::MIDDLE_MOUSE_BUTTON)
		.value("RIGHT_MOUSE_BUTTON", osgGA::GUIEventAdapter::RIGHT_MOUSE_BUTTON)
		.export_values()
	;

	gea
		// TODO: Should this ACTUALLy be `eventType` instead?
		.def_property(
			"type",
			&osgGA::GUIEventAdapter::getEventType,
			&osgGA::GUIEventAdapter::setEventType,
			"The event's EventType."
		)
		.def_property(
			"mouseYOrientation",
			&osgGA::GUIEventAdapter::getMouseYOrientation,
			&osgGA::GUIEventAdapter::setMouseYOrientation,
			"Whether pointer y increases upward or downward."
		)
	;

	py::class_<
		osgGA::GUIEventHandler,
		detail::GUIEventHandler,
		osg::Object,
		osg::ref_ptr<osgGA::GUIEventHandler>
	>(
		m,
		"GUIEventHandler",
		"Base class for a per-view handler invoked with each event; override handle() to "
		"react to input (see View.eventHandlers)."
	)
		.def(py::init_alias<>(), "Create a GUI event handler.")
		.def("handle", [](
			osgGA::GUIEventHandler& self,
			const osgGA::GUIEventAdapter& ea,
			osgGA::GUIActionAdapter& aa
		) {
			return self.handle(ea, aa, nullptr, nullptr);
		}, "Handle an event; return true when it was consumed.")
	;

	py::class_<
		osgGA::EventQueue,
		osg::Referenced,
		osg::ref_ptr<osgGA::EventQueue>
	>(
		m,
		"EventQueue",
		"Accumulates synthesized input/window events (mouse, keyboard, resize) to be "
		"delivered on the next frame, e.g. from an embedded windowing toolkit."
	)
		.def(py::init<>(), "Create an empty event queue.")
		.def("clear", &osgGA::EventQueue::clear, "Discard all queued events.")
		.def_property_readonly(
			"currentEventState",
			py::overload_cast<>(&osgGA::EventQueue::getCurrentEventState),
			py::return_value_policy::reference_internal,
			"Current event state used when synthesizing events."
		)

		.def("windowResize", py::overload_cast<
			int, int, int, int
		>(&osgGA::EventQueue::windowResize), "Queue a window resize event.")
		.def("windowResize", py::overload_cast<
			int, int, int, int, double
		>(&osgGA::EventQueue::windowResize))

		.def("mouseButtonPress", py::overload_cast<
			float, float, unsigned int
		>(&osgGA::EventQueue::mouseButtonPress), "Queue a mouse-button press event.")
		.def("mouseButtonPress", py::overload_cast<
			float, float, unsigned int, double
		>(&osgGA::EventQueue::mouseButtonPress))

		.def("mouseButtonRelease", py::overload_cast<
			float, float, unsigned int
		>(&osgGA::EventQueue::mouseButtonRelease), "Queue a mouse-button release event.")
		.def("mouseButtonRelease", py::overload_cast<
			float, float, unsigned int, double
		>(&osgGA::EventQueue::mouseButtonRelease))

		.def("mouseMotion", py::overload_cast<
			float, float
		>(&osgGA::EventQueue::mouseMotion), "Queue a pointer-motion event.")
		.def("mouseMotion", py::overload_cast<
			float, float, double
		>(&osgGA::EventQueue::mouseMotion))

		.def("mouseScroll", py::overload_cast<
			osgGA::GUIEventAdapter::ScrollingMotion
		>(&osgGA::EventQueue::mouseScroll), "Queue a mouse-wheel scroll event.")
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
		}, "key"_a, "time"_a=0.0, "unmodifiedKey"_a=0, "Queue a key-press event.")
		.def("keyRelease", [](
			osgGA::EventQueue& self,
			int key,
			double time=0.0,
			int unmodifiedKey=0
		) {
			return self.keyRelease(key, time, unmodifiedKey);
		}, "key"_a, "time"_a=0.0, "unmodifiedKey"_a=0, "Queue a key-release event.")
		.def("frame", &osgGA::EventQueue::frame, "time"_a=0.0, "Queue a frame event at time.")
		.def("takeEvents", [](osgGA::EventQueue& self) {
			osgGA::EventQueue::Events source;
			py::list events;

			self.takeEvents(source);

			for(auto& event : source) events.append(event);

			return events;
		}, "Return and clear all queued events.")
	;

	py::class_<
		osgGA::CameraManipulator,
		detail::CameraManipulator,
		osgGA::GUIEventHandler,
		osg::ref_ptr<osgGA::CameraManipulator>
	>(
		m,
		"CameraManipulator",
		"Base class for interactive camera controllers (see TrackballManipulator) that turn "
		"input events into a view matrix. .node returns the same stable Python wrapper for "
		"the underlying scene node on every access, rather than a fresh one each call."
	)
		.def(py::init_alias<>(), "Create a camera manipulator.")
		.def("home", py::overload_cast<
			const osgGA::GUIEventAdapter&,
			osgGA::GUIActionAdapter&
		>(&osgGA::CameraManipulator::home), "Reset the camera to its home position.")
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
			"useBoundingBox"_a=false,
			"Compute a home position from the manipulator's scene node."
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
			}),
			"The (eye, center, up) tuple used by home()."
		)
		.def_property(
			"autoComputeHomePosition",
			&osgGA::CameraManipulator::getAutoComputeHomePosition,
			&osgGA::CameraManipulator::setAutoComputeHomePosition,
			"Whether home position is recomputed automatically."
		)
		.def_property(
			"inverseMatrix",
			&osgGA::CameraManipulator::getInverseMatrix,
			&osgGA::CameraManipulator::setByInverseMatrix,
			"The inverse camera transform matrix."
		)
		.def_property(
			"matrix",
			&osgGA::CameraManipulator::getMatrix,
			&osgGA::CameraManipulator::setByMatrix,
			"The camera transform matrix."
		)
		// Bound as a plain method (not just made overridable in the trampoline above) so a
		// Python decorator manipulator can delegate to an INNER manipulator's own updateCamera()
		// before composing anything on top of it -- e.g. self.inner.updateCamera(camera) -- see
		// aipython/06-camera-effects.md.
		.def("updateCamera", &osgGA::CameraManipulator::updateCamera,
			"Update camera from the manipulator's current state."
		)
		// coordianteFrame
		// sideVector
		// frontVector
		// upVector
	;

	auto sm = py::class_<
		osgGA::StandardManipulator,
		osgGA::CameraManipulator,
		osg::ref_ptr<osgGA::StandardManipulator>
	>(
		m,
		"StandardManipulator",
		"A CameraManipulator base adding common mouse-wheel/model-size/home-position "
		"behavior shared by OSG's built-in manipulators."
	);

	py::enum_<osgGA::StandardManipulator::UserInteractionFlags>(sm, "UserInteractionFlags",
		"Configure standard manipulator interaction behavior."
	)
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
	>(
		m,
		"OrbitManipulator",
		"A StandardManipulator that orbits the camera around a fixed center point."
	);

	py::class_<
		osgGA::TrackballManipulator,
		osgGA::CameraManipulator,
		osg::ref_ptr<osgGA::TrackballManipulator>
	>(
		m,
		"TrackballManipulator",
		"The default interactive camera manipulator: orbit/pan/zoom driven by mouse drag "
		"and scroll."
	)
		.def(py::init<int>(), "flags"_a=osgGA::StandardManipulator::DEFAULT_SETTINGS,
			"Create a trackball manipulator with interaction flags."
		)
	;
}

}
