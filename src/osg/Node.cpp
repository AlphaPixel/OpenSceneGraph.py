#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Node& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Object&>(self), kwargs);
	}
}

void bind_Node(py::module_& m) {
	auto node = py::class_<osg::Node, osg::Object, osg::ref_ptr<osg::Node>>(m, "Node")
		.def(py::init<>())
		.def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Node> n = new osg::Node();

			detail::kwargs_init(*n, kwargs);

			return n;
		}))
		.def("setUpdateCallback", [](osg::Node& self, osg::NodeCallback* cb) {
			// TODO: What happens when cb is nullptr?
			self.setUpdateCallback(cb);
		}, py::keep_alive<1, 2>())
		// NOTE: We do NOT use py::keep_alive here, since the visitor will stay alive the entirety
		// of this call, even IF you do something like: node.accept(PythonVistor()).
		.def("accept", [](osg::Node& self, osg::NodeVisitor* nv) {
			self.accept(*nv);
		// }, py::keep_alive<2, 1>())
		})
		/* .def("traverse", [](osg::Node& self, osg::NodeVisitor* nv) {
			self.traverse(*nv);
		// }, py::keep_alive<2, 1>())
		}) */
		.def_property("nodeMask", &osg::Node::getNodeMask, &osg::Node::setNodeMask)
	;

	node.attr("NodeMask") = py::int_();
}

}
