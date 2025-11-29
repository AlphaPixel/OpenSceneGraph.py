#include "../osg.hpp"

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
}

void bind_NodeCallback(py::module_& m) {
	py::class_<osg::NodeCallback, detail::NodeCallback, osg::Object, osg::ref_ptr<osg::NodeCallback>>(m, "NodeCallback")
		.def(py::init<>())
		.def("__call__", [](osg::NodeCallback& self, osg::Node* node, osg::NodeVisitor* nv) {
			// Manual forwarding; ensures Python sees correct signature.
			return;
		})
	;
}

}
