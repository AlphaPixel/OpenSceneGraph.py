#include "../OpenSceneGraph-python.hpp"
#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Group>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Group& self, const py::kwargs& kwargs) {
		kwargs_init(static_cast<osg::Node&>(self), kwargs);

		// if constexpr(!std::is_same_v<osg::Group, osg::Node>) kwargs_init(static_cast<osg::Node&>(group), kw);

		if(kwargs.contains("children")) {
			for(py::handle child : kwargs["children"]) {
				self.addChild(child.cast<osg::Node*>());
			}
		}

	}

	struct ChildrenProxy {
		osg::Group* g = nullptr;

		explicit ChildrenProxy(osg::Group* group): g(group) {}

		size_t size() const {
			return g->getNumChildren();
		}

		constexpr size_t _index(int index) const {
			auto n = static_cast<int>(g->getNumChildren());

			if(index < 0) index += n;
			if(index < 0 || index >= n) throw py::index_error();

			return static_cast<size_t>(index);
		}

		osg::Node* get(int index) const {
			return g->getChild(_index(index));
		}

		void set(int index, osg::Node* n) {
			g->replaceChild(g->getChild(_index(index)), n);
		}

		void del(int index) {
			g->removeChild(_index(index));
		}

		void append(osg::Node* n) {
			g->addChild(n);
		}

		void extend(py::object iterable) {
			for(py::handle item : iterable) {
				auto* n = item.cast<osg::Node*>();

				g->addChild(n);
			}
		}
	};
}

void bind_Group(py::module_& m) {
	auto group = py::class_<osg::Group, osg::Node, osg::ref_ptr<osg::Group>>(m, "Group");

	py::class_<detail::ChildrenProxy>(group, "_Children", py::module_local())
		.def("__len__", &detail::ChildrenProxy::size)
		.def("__getitem__", &detail::ChildrenProxy::get)
		.def("__setitem__", &detail::ChildrenProxy::set)
		.def("__delitem__", &detail::ChildrenProxy::del)
		.def("append", &detail::ChildrenProxy::append)
		.def("extend", &detail::ChildrenProxy::extend)
	;

	group
		.def(py::init<>())
		.def(py::init([](py::args args, py::kwargs kwargs) {
			osg::ref_ptr<osg::Group> g = new osg::Group();

			detail::kwargs_init(*g, kwargs);

			return g;
		}))
#if 0
		.def("addChild", [](osg::Group* self, osg::Node* child) {
			return self->addChild(child);
		}, py::arg("child"))
		.def("getNumChildren", &osg::Group::getNumChildren)
		.def("getChild", [](osg::Group* self, unsigned int index) {
			return self->getChild(index);
		}, py::arg("index"))
		// .def("getChild", static_cast<osg::Node*(osg::Group::*)(unsigned int)>(&osg::Group::getChild))
		/* .def("addChildren", [](osg::Group* self, py::object obj) {
			if(py::isinstance<py::iterable>(obj)) {
				for(auto item : obj) {
					// osg::Node* child = item.cast<osg::Node*>();
					auto* child = item.cast<osg::Node*>();

					self->addChild(child);
				}
			}

			else {
				// osg::Node* child = obj.cast<osg::Node*>();
				auto* child = obj.cast<osg::Node*>();

				self->addChild(child);
			}
		},
		py::arg("children")) */
		.def("addChildren", [](osg::Group* self, const py::args& args) {
			int count = 0;

			for(auto item : args) {
				auto* child = item.cast<osg::Node*>();

				if(self->addChild(child)) count++;
			}

			return count;
		},
		"Add one or more children. Returns number of children added.")
#endif
		.def_property_readonly("children", [](osg::Group* g) {
			return detail::ChildrenProxy(g);
		})
	;
}

}
