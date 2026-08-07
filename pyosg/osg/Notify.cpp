#include "Notify.hpp"

namespace pyosg {

void bind_Notify(py::module_& m) {
	py::enum_<osg::NotifySeverity>(m, "NotifySeverity")
		.value("ALWAYS", osg::NotifySeverity::ALWAYS)
		.value("FATAL", osg::NotifySeverity::FATAL)
		.value("WARN", osg::NotifySeverity::WARN)
		.value("NOTICE", osg::NotifySeverity::NOTICE)
		.value("INFO", osg::NotifySeverity::INFO)
		.value("DEBUG_INFO", osg::NotifySeverity::DEBUG_INFO)
		.value("DEBUG_FP", osg::NotifySeverity::DEBUG_FP)
	;

	/* py::class_<
		osg::NotifyHandler,
		detail::NotifyHandler,
		osg::ref_ptr<osg::NotifyHandler>
	>(m, "NotifyHandler")
		.def(py::init<>())
		.def("notify", &osg::NotifyHandler::notify)
	; */

	m
		/* .def("setNotifyHandler",
			[](osg::NotifyHandler* handler) {
				detail::notifyHandler = handler;

				osg::setNotifyHandler(handler);
			},
			"handler"_a
		) */
		.def("getNotifyHandler", []() -> py::object {
			if(!detail::notifyHandler.valid()) return py::none();

			return detail::notifyHandler->getCallback();
		})
		.def("setNotifyHandler", [](py::object cb) {
			// Clear handler with the `None` argument.
			if(cb.is_none()) {
				osg::setNotifyHandler(nullptr);

				detail::notifyHandler = nullptr;

				return;
			}

			// Whatever is passed-in MUST be a callable object!
			if(!PyCallable_Check(cb.ptr())) throw py::type_error("Expected a callable or None");

			detail::notifyHandler = new detail::NotifyHandler(cb);

			osg::setNotifyHandler(detail::notifyHandler.get());
		})
		.def("getNotifyLevel", &osg::getNotifyLevel)
		.def("setNotifyLevel", [](osg::NotifySeverity severity) {
			osg::setNotifyLevel(severity);
		}, "severity"_a)
		.def("isNotifyEnabled", &osg::isNotifyEnabled)
		.def("always", [](const char* msg) { OSG_ALWAYS << msg << std::endl; })
		.def("fatal", [](const char* msg) { OSG_FATAL << msg << std::endl; })
		.def("warn", [](const char* msg) { OSG_WARN << msg << std::endl; })
		.def("notice", [](const char* msg) { OSG_NOTICE << msg << std::endl; })
		.def("info", [](const char* msg) { OSG_INFO << msg << std::endl; })
		.def("debug", [](const char* msg) { OSG_DEBUG << msg << std::endl; })
		.def("debug_fp", [](const char* msg) { OSG_DEBUG_FP << msg << std::endl; })
	;

	m.add_object("_notify_teardown", py::capsule([]() {
		// Make absolutely sure OSG stops using it; I've seen crashes...
		osg::setNotifyHandler(nullptr);

		detail::notifyHandler = nullptr;
	}));
}

}
