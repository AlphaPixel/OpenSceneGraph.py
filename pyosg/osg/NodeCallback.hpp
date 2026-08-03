#pragma once

#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	// osg::Callback::run(Object*, Object*) is the modern, unified callback entry point --
	// osg::NodeCallback::run() below only exists to adapt IT to the "old style"
	// operator()(Node*, NodeVisitor*) method (real OSG's own doc comment on NodeCallback::run()
	// says exactly this). A Python subclass of plain Callback overriding run() needs this
	// trampoline for the same reason detail::NodeCallback needs one below: without it, a direct
	// Python call (`cb.run(obj, data)`) looks like it works via ordinary Python method lookup, but
	// a REAL C++-side virtual call (e.g. from Node::traverse()/accept()) would never reach the
	// override at all.
	class Callback: public osg::Callback {
	public:
		using osg::Callback::Callback;

		bool run(osg::Object* object, osg::Object* data) override {
			if(auto r = call_override<bool>("run", this, object, data)) return *r;

			return osg::Callback::run(object, data);
		}
	};

	class NodeCallback: public osg::NodeCallback {
	public:
		using osg::NodeCallback::NodeCallback;

		bool run(osg::Object* object, osg::Object* data) override {
			/* std::cout
				<< "[C++] run this=" << this
				<< " object=" << object
				<< " data=" << data
				<< std::endl; */

			// First, explicit Python `run` override...
			if(auto r = call_override<bool>("run", this, object, data)) {
				// std::cout << "[C++] run override found, returning " << *r << std::endl;

				return *r;
			}

			// std::cout << "[C++] no run override, delegating to osg::NodeCallback::run()" << std::endl;

			return osg::NodeCallback::run(object, data);
		}

		void operator()(osg::Node* node, osg::NodeVisitor* nv) override {
			/* std::cout
				<< "[C++] operator() this=" << this
				<< " node=" << node
				<< " name=" << (node ? node->getName() : std::string("<null>"))
				<< std::endl; */

			if(auto r = call_override<bool>("__call__", this, node, nv)) {
				// std::cout << "[C++] __call__ override found, value_or(true)="
				// << r.value_or(true) << std::endl;

				if(r.value_or(true)) {
					// std::cout << "[C++] delegating to osg::NodeCallback::operator() for traversal" << std::endl;

					osg::NodeCallback::operator()(node, nv);
				}

				return;
			}

			// std::cout << "[C++] no __call__ override, using osg::NodeCallback::operator()" << std::endl;

			osg::NodeCallback::operator()(node, nv);
		}
	};
}

void bind_NodeCallback(py::module_& m);

}
