#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Notify>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	struct NotifyHandler: public osg::NotifyHandler {
		using osg::NotifyHandler::NotifyHandler;

		void notify(osg::NotifySeverity severity, const char* message) override {
			// TODO: How necessary is this?
			py::gil_scoped_acquire gil;

			PYBIND11_OVERRIDE_PURE(
				void,
				osg::NotifyHandler,
				notify,
				severity,
				message
			);
		}
	};

	static osg::ref_ptr<osg::NotifyHandler> notifyHandler = nullptr;
}

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

	py::class_<
		osg::NotifyHandler,
		detail::NotifyHandler,
		osg::ref_ptr<osg::NotifyHandler>
	>(m, "NotifyHandler")
		.def(py::init<>())
		.def("notify", &osg::NotifyHandler::notify)
	;

	m
		.def("isNotifyEnabled", &osg::isNotifyEnabled)
		.def("setNotifyHandler",
			[](osg::NotifyHandler* handler) {
				detail::notifyHandler = handler;

				osg::setNotifyHandler(handler);
			},
			py::arg("handler")
		)
		.def("setNotifyLevel", [](osg::NotifySeverity level) {
			osg::setNotifyLevel(level);
		}, py::arg("severity"))
		.def("getNotifyLevel", &osg::getNotifyLevel)
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
