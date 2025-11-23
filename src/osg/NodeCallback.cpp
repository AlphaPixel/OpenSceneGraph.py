#include "../OpenSceneGraph-python.hpp"
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
			/* if(auto r = call_override<bool>("handle", this, node, nv); *r) osg::NodeCallback::operator()(node, nv);

			osg::NodeCallback::operator()(node, nv); */

        // call_override<bool>:
        //   - optional(true)  → Python returned True
        //   - optional(false) → Python returned False
        //   - empty optional  → Python returned None OR no override
        auto r = call_override<bool>("handle", this, node, nv);

        // default behavior = call base callback
        bool call_base = r.value_or(true);

        if (call_base)
            osg::NodeCallback::operator()(node, nv);

		}
	};
}

void bind_NodeCallback(py::module_& m) {
	py::class_<osg::NodeCallback, detail::NodeCallback, osg::Object, osg::ref_ptr<osg::NodeCallback>>(m, "NodeCallback")
		.def(py::init<>())
		.def("handle", [](osg::NodeCallback* self, osg::Node* node, osg::NodeVisitor* nv) {
			// Manual forwarding; ensures Python sees correct signature.
			return;
		})
	;
}

}
