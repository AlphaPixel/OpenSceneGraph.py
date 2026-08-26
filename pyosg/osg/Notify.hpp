#pragma once

#include "../pyosg.hpp"
#include "pybind11x.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Notify>

OSGX_ENABLE_WARNINGS

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
	class PYOSG_INTERNAL NotifyHandler: public osg::NotifyHandler {
	public:
		explicit NotifyHandler(py::object cb):
		_cb(std::move(cb)) {}

		~NotifyHandler() override { pybind11x::release_with_gil(_cb); }

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

void bind_Notify(py::module_& m);

}
