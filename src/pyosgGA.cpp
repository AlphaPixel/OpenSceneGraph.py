#include "pyosgGA.hpp"
#include "osg/callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/GUIEventHandler>
#include <osgGA/EventQueue>
#include <osgGA/TrackballManipulator>

PYOSG_ENABLE_WARNINGS

namespace pyosgGA {

namespace detail {
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

	class CameraManipulator: public osgGA::CameraManipulator {
	public:
		using osgGA::CameraManipulator::CameraManipulator;

		~CameraManipulator() override {}

		void home(const osgGA::GUIEventAdapter& ea, osgGA::GUIActionAdapter& aa) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, home, ea, aa);
		}

		void home(double t) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, home, t);
		}

		void setAutoComputeHomePosition(bool flag) override {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, setAutoComputeHomePosition, flag);
		}

		void getHomePosition(osg::Vec3d& eye, osg::Vec3d& center, osg::Vec3d& up) const override {
			PYBIND11_OVERRIDE(
				void,
				osgGA::CameraManipulator,
				getHomePosition,
				eye,
				center,
				up
			);
		}

		void setHomePosition(
			const osg::Vec3d& eye,
			const osg::Vec3d& center,
			const osg::Vec3d& up,
			bool autoComputeHomePosition=false
		) {
			PYBIND11_OVERRIDE(
				void,
				osgGA::CameraManipulator,
				setHomePosition,
				eye,
				center,
				up,
				autoComputeHomePosition
			);
		}

		osg::Matrixd getMatrix() const override {
			std::cerr << "detail::CameraManipulator::getMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getMatrix
			);
		}

		osg::Matrixd getInverseMatrix() const override {
			std::cerr << "detail::CameraManipulator::getInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				osg::Matrixd,
				osgGA::CameraManipulator,
				getInverseMatrix
			);
		}

		void setByMatrix(const osg::Matrixd& mat) override {
			std::cerr << "detail::CameraManipulator::setByMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByMatrix,
				mat
			);
		}

		void setByInverseMatrix(const osg::Matrixd& mat) override {
			std::cerr << "detail::CameraManipulator::setByInverseMatrix" << std::endl;

			PYBIND11_OVERRIDE_PURE(
				void,
				osgGA::CameraManipulator,
				setByInverseMatrix,
				mat
			);
		}

		/* void computeHomePosition(const osg::Camera* camera=nullptr, bool useBoundingBox=false) {
			PYBIND11_OVERRIDE(void, osgGA::CameraManipulator, setAutoComputeHomePosition, flag);
		} */
	};
}

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
	;

	// TODO: This WILL NEED a trampoline class in the `detail` namespace!
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
		.def_property(
			"homePosition",
			py::cpp_function([](osgGA::CameraManipulator& self) {
				osg::Vec3d eye, center, up;

				self.getHomePosition(eye, center, up);

				return py::make_tuple(eye, center, up);
			}),
			py::cpp_function([](osgGA::CameraManipulator& self, py::object obj) {
				if(!py::isinstance<py::sequence>(obj)) throw py::type_error(
					"Expected (eye, center, up) Vec3d sequence"
				);

				auto seq = obj.cast<py::sequence>();

				if(seq.size() != 3) throw py::type_error(
					"Expected Vec3d sequence of length 3 (eye, center, up)"
				);

				self.setHomePosition(
					seq[0].cast<osg::Vec3d>(),
					seq[1].cast<osg::Vec3d>(),
					seq[2].cast<osg::Vec3d>()
				);
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
