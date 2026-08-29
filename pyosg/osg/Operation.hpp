#pragma once

#include "callable.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/GraphicsContext>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	class Operation: public osg::Operation {
	public:
		// using osg::Operation::Operation;

		void release() override {
			PYBIND11_OVERRIDE(void, osg::Operation, release);
		}

		// TODO: Is there a better way for this?
		void operator()(osg::Object* obj) override {
			call_override<void>("__call__", this, obj);
		}
	};

	class GraphicsOperation: public osg::GraphicsOperation {
	public:
		using osg::GraphicsOperation::GraphicsOperation;

		// TODO: Is there a better way for this, too?
		void operator()(osg::GraphicsContext* gc) override {
			call_override<void>("__call__", this, gc);
		}

		// virtual void resizeGLObjectBuffers(unsigned int maxSize) {}
		// virtual void releaseGLObjects(osg::State* = 0) const {}
	};
}

void bind_Operation(py::module_& m);

}
