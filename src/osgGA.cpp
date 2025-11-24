#include "OpenSceneGraph-python.hpp"
#include "osg.hpp"
#include "osgGA.hpp"

PYOSG_DISABLE_WARNINGS

#include <osgGA/GUIEventHandler>

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

	auto gea = py::class_<osgGA::GUIEventAdapter, osg::Object, osg::ref_ptr<osgGA::GUIEventAdapter>>(m, "GUIEventAdapter")
		.def_property_readonly("eventType", &osgGA::GUIEventAdapter::getEventType)
		.def_property_readonly("type", &osgGA::GUIEventAdapter::getEventType)
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

	py::class_<osgGA::GUIEventHandler, GUIEventHandler, osg::Object, osg::ref_ptr<osgGA::GUIEventHandler>>(m, "GUIEventHandler")
		.def(py::init_alias<>())
		// .def("handle", py::overload_cast<const osgGA::GUIEventAdapter&, osgGA::GUIActionAdapter&>(&osgGA::GUIEventHandler::handle))
		.def("handle", [](osgGA::GUIEventHandler* self, const osgGA::GUIEventAdapter& ea, osgGA::GUIActionAdapter& aa) {
			return self->handle(ea, aa, nullptr, nullptr);
		})
	;
}

}
