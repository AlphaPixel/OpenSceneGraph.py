#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Notify>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	// XXX: I've left the implementation of osg::NotifyHandler here for educational purposes. It
	// does "work"--to some degree--but comes with many caveats due to how OSG uses a singleton
	// approach for supporting notification.

	/* struct NotifyHandler: public osg::NotifyHandler {
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
	}; */

	// Instead of the above, we setup our bindings to accept a generic, callable Python object to
	// use as the "handler" for all notifications. This could be a function, a lambda, or a class
	// with the `__call__` method defined.
	//
	// TODO: Since we'll likely use this technique in a few places, it makes sense to generalize at
	// some point (osg::ArgumentParser, osg::DisplaySettings, etc); ANYTHING that OSG stores as
	// static data and exposes via a singleton API.
	class NotifyHandler: public osg::NotifyHandler {
	public:
		explicit NotifyHandler(py::object cb):
		_cb(std::move(cb)) {}

		void notify(osg::NotifySeverity sev, const char* msg) override {
			py::gil_scoped_acquire gil;

			try {
				_cb(sev, msg);
			}

			catch(const py::error_already_set&) {
				PyErr_Print();
			}
		}

		py::object getCallback() {
			if(!_cb || _cb.is_none()) return py::none();

			return _cb;
		}

	protected:
		py::object _cb;
	};

	static osg::ref_ptr<NotifyHandler> notifyHandler = nullptr;
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
			py::arg("handler")
		) */
		.def("getNotifyHandler", []() -> py::object {
			if(!detail::notifyHandler.valid()) return py::none();

			/* if(
				!detail::notifyHandler->cb ||
				!detail::notifyHandler->cb.is_none()
			) return py::none();

			return detail::notifyHandler->cb; */

			return detail::notifyHandler->getCallback();
		})
		.def("setNotifyHandler", [](const py::object& cb) {
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
		.def("setNotifyLevel", [](osg::NotifySeverity level) {
			osg::setNotifyLevel(level);
		}, py::arg("severity"))
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
