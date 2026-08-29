#include "Notify.hpp"

namespace pyosg {

void bind_Notify(py::module_& m) {
	py::enum_<osg::NotifySeverity>(m, "NotifySeverity",
		"Severity levels for OSG's global notify/logging stream, from ALWAYS (never filtered) "
		"down to DEBUG_FP; compare against getNotifyLevel()/setNotifyLevel()."
	)
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
		}, "Return the current Python notify callback, or None if OSG's default handler is active.")
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
		}, "Install a callable(severity, message) as OSG's global notify handler; pass None to "
			"restore OSG's default (stderr/stdout) handler."
		)
		.def("getNotifyLevel", &osg::getNotifyLevel,
			"Return the current global NotifySeverity threshold."
		)
		.def("setNotifyLevel", [](osg::NotifySeverity severity) {
			osg::setNotifyLevel(severity);
		}, "severity"_a, "Set the global NotifySeverity threshold; messages above it are dropped.")
		.def("isNotifyEnabled", &osg::isNotifyEnabled,
			"Return whether messages at the given NotifySeverity would currently be emitted."
		)
		.def("always", [](const char* msg) { OSG_ALWAYS << msg << std::endl; },
			"Write msg to OSG's notify stream at ALWAYS severity (never filtered)."
		)
		.def("fatal", [](const char* msg) { OSG_FATAL << msg << std::endl; },
			"Write msg to OSG's notify stream at FATAL severity."
		)
		.def("warn", [](const char* msg) { OSG_WARN << msg << std::endl; },
			"Write msg to OSG's notify stream at WARN severity."
		)
		.def("notice", [](const char* msg) { OSG_NOTICE << msg << std::endl; },
			"Write msg to OSG's notify stream at NOTICE severity."
		)
		.def("info", [](const char* msg) { OSG_INFO << msg << std::endl; },
			"Write msg to OSG's notify stream at INFO severity."
		)
		.def("debug", [](const char* msg) { OSG_DEBUG << msg << std::endl; },
			"Write msg to OSG's notify stream at DEBUG_INFO severity."
		)
		.def("debug_fp", [](const char* msg) { OSG_DEBUG_FP << msg << std::endl; },
			"Write msg to OSG's notify stream at DEBUG_FP (most verbose) severity."
		)
	;

	m.add_object("_notify_teardown", py::capsule([]() {
		// Make absolutely sure OSG stops using it; I've seen crashes...
		osg::setNotifyHandler(nullptr);

		detail::notifyHandler = nullptr;
	}));
}

}
