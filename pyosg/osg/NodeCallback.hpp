#pragma once

#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
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

			if (auto r = call_override<bool>("__call__", this, node, nv)) {
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
