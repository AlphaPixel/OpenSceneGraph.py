#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	class NodeCallback: public osg::NodeCallback {
	public:
		using osg::NodeCallback::NodeCallback;

		void operator()(osg::Node* node, osg::NodeVisitor* nv) override {
			auto r = call_override<bool>("__call__", this, node, nv);

			if(r.value_or(true)) osg::NodeCallback::operator()(node, nv);
		}
	};

	/* // TODO: Test this!
	class PYOSG_INTERNAL CallableNodeCallback: public osg::NodeCallback {
	public:
		explicit CallableNodeCallback(py::object fn): _fn(std::move(fn)) {}

		void operator()(osg::Node* node, osg::NodeVisitor* nv) override {
			py::gil_scoped_acquire gil;

			py::object result = _fn(node, nv);

			bool traverse = true;

			if(!result.is_none()) traverse = result.cast<bool>();

			if(traverse) osg::NodeCallback::operator()(node, nv);
		}

	private:
		py::object _fn;
	}; */
}

void bind_NodeCallback(py::module_& m) {
	py::class_<
		osg::NodeCallback,
		detail::NodeCallback,
		osg::Object,
		osg::ref_ptr<osg::NodeCallback>
	>(m, "NodeCallback")
		.def(py::init<>())
		.def("__call__", [](osg::NodeCallback& self, osg::Node* node, osg::NodeVisitor* nv) {
			// Manual forwarding; ensures Python sees correct signature.
			return;
		})
	;
}

}
