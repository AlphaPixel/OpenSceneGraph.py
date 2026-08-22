#pragma once

#include "callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/NodeVisitor>

OSGX_ENABLE_WARNINGS

#include "pybind11x.hpp"

namespace pyx = pybind11x;

namespace pyosg::detail {
	struct NestedCallbacksTag;
}

// osg::Callback::nestedCallback is a SINGLY-LINKED chain (Callback -> Callback -> ... ->
// nullptr), not an array -- this traits specialization flattens it into a Python list-like
// view (`callback.nestedCallbacks`) instead of forcing manual getNestedCallback()/
// setNestedCallback() walks from Python. get()/size() walk the chain; set()/del() splice
// around the target node (clearing its own nestedCallback so a removed/replaced node doesn't
// silently keep pointing into the middle of a chain it's no longer part of); append()/insert()
// reuse the same splice shape, with append() landing at the true end of the chain via
// addNestedCallback() rather than assuming `this` has no nested callback yet.
template<>
struct pyx::SequenceTraits<osg::Callback, pyosg::detail::NestedCallbacksTag> {
	using element_type = osg::Callback;
	using value_type = element_type*;

	static value_type from_python(py::handle h) {
		return h.cast<value_type>();
	}

	static size_t size(const osg::Callback* c) {
		size_t n = 0;

		for(const osg::Callback* cur = c->getNestedCallback(); cur; cur = cur->getNestedCallback()) n++;

		return n;
	}

	static element_type* get(osg::Callback* c, size_t i) {
		osg::Callback* cur = c->getNestedCallback();

		for(size_t k = 0; k < i && cur; k++) cur = cur->getNestedCallback();

		return cur;
	}

	static void set(osg::Callback* c, size_t i, value_type n) {
		osg::Callback* prev = c;

		for(size_t k = 0; k < i; k++) prev = prev->getNestedCallback();

		osg::Callback* old = prev->getNestedCallback();
		osg::Callback* tail = old ? old->getNestedCallback() : nullptr;

		if(old) old->setNestedCallback(nullptr);

		n->setNestedCallback(tail);
		prev->setNestedCallback(n);
	}

	static void del(osg::Callback* c, size_t i) {
		osg::Callback* prev = c;

		for(size_t k = 0; k < i; k++) prev = prev->getNestedCallback();

		osg::Callback* old = prev->getNestedCallback();
		osg::Callback* tail = old ? old->getNestedCallback() : nullptr;

		if(old) old->setNestedCallback(nullptr);

		prev->setNestedCallback(tail);
	}

	static void append(osg::Callback* c, value_type n) {
		c->addNestedCallback(n);
	}

	static void insert(osg::Callback* c, size_t i, value_type n) {
		osg::Callback* prev = c;

		for(size_t k = 0; k < i; k++) prev = prev->getNestedCallback();

		n->setNestedCallback(prev->getNestedCallback());
		prev->setNestedCallback(n);
	}
};

namespace pyosg {

namespace detail {
	using NestedCallbacksProxy = pyx::SequenceProxy<osg::Callback, NestedCallbacksTag>;
	using CallbackStorage = pyx::ProxyStorageOSG<osg::Callback, NestedCallbacksProxy>;

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
