#include "callable.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/NodeVisitor>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	using NodeCallable = CallableCallback<
		osg::NodeCallback,
		void(osg::Node*, osg::NodeVisitor*),
		true
	>;

	/* // TODO: Use this in both places instead...
	template<auto Setter>
	auto setNodeCallback() {
		return detail::setCallback<Setter, osg::NodeCallback, NodeCallable>();
	} */

	template<>
	void kwargs_init(osg::Node& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Object&>(self), kwargs);

		if(kwargs.contains("nodeMask")) self.setNodeMask(
			kwargs["nodeMask"].cast<osg::Node::NodeMask>()
		);

		if(kwargs.contains("updateCallback")) {
			/* detail::setCallback<
				static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setUpdateCallback),
				osg::NodeCallback,
				NodeCallable
			>()(self, kwargs["updateCallback"]); */

			/* applyCallback<
				static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setUpdateCallback),
				osg::NodeCallback,
				NodeCallable
			>(self, kwargs["updateCallback"]); */

			std::cerr << "TODO: This doesn't work yet!" << std::endl;
		}
	}

	class TestCallback: public osg::NodeCallback {
		void operator()(osg::Node* node, osg::NodeVisitor* nv) {
			OSG_NOTICE << "In TestCallback CPP" << std::endl;
		}
	};
}

void bind_Node(py::module_& m) {
	auto node = py::class_<osg::Node, osg::Object, osg::ref_ptr<osg::Node>>(m, "Node")
		.def(py::init<>())
		.def(py::init([](py::kwargs kwargs) -> osg::Node* {
			// osg::ref_ptr<osg::Node> n = new osg::Node();
			auto* n = new osg::Node();

			detail::kwargs_init(*n, kwargs);

			return n;
		}))

		.def_property(
			"updateCallback",
			detail::getCallback(py::overload_cast<>(&osg::Node::getUpdateCallback)),
			detail::setCallback<
				static_cast<void(osg::Node::*)(osg::Callback*)>(&osg::Node::setUpdateCallback),
				osg::NodeCallback,
				detail::NodeCallable
			>()
		)

		// NOTE: We do NOT use py::keep_alive here, since the visitor will stay alive the entirety
		// of this call, even IF you do something like: node.accept(PythonVistor()).
		.def("accept", [](osg::Node& self, osg::NodeVisitor* nv) {
			self.accept(*nv);
		})

		.def_property("stateSet",
			py::cpp_function(
				[](osg::Node& self) { return self.getOrCreateStateSet(); },
				py::return_value_policy::reference
			),
			[](osg::Node& self, osg::StateSet* ss) { self.setStateSet(ss); }
		)

		.def_property("nodeMask", &osg::Node::getNodeMask, &osg::Node::setNodeMask)
	;

	/* node
		.def_static("test_cpp", []() {
			auto* n = new osg::Node();

			n->setUpdateCallback(new detail::TestCallback());

			return n;
		})
	; */

	node.attr("NodeMask") = detail::builtin_int();
}

}
