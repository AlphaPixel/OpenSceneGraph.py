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

		/* .def("setUpdateCallback", [](osg::Node& self, osg::NodeCallback* cb) {
			// TODO: What happens when cb is nullptr?
			self.setUpdateCallback(cb);
		}, py::keep_alive<1, 2>())
		.def("getUpdateCallback", [](osg::Node& self) {
			return self.getUpdateCallback();
		}, py::return_value_policy::reference) */

		.def_property(
			"updateCallback",
			py::cpp_function([](osg::Node& self) -> osg::Callback* {
				return self.getUpdateCallback();
			// }, py::return_value_policy::reference),
			}, py::return_value_policy::reference_internal),
			py::cpp_function([](osg::Node& self, osg::NodeCallback* cb) {
				// py::cast(cb).inc_ref();

				self.setUpdateCallback(cb);
			}, py::keep_alive<1, 2>())
			// })
		)

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
		.def_property("stateSet",
			[](osg::Node& self) { return self.getOrCreateStateSet(); },
			[](osg::Node& self, osg::StateSet* ss) { self.setStateSet(ss); },
			py::return_value_policy::reference
		)
		.def_property("nodeMask",
			[](osg::Node& self) { return self.getNodeMask(); },
			[](osg::Node& self, osg::Node::NodeMask mask) { self.setNodeMask(mask); }
		)
	;

	node.attr("NodeMask") = detail::builtin_int();
}

}
