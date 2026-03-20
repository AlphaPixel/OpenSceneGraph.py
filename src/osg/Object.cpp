#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Object>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());

		if(kwargs.contains("dataVariance")) self.setDataVariance(
			kwargs["dataVariance"].cast<osg::Object::DataVariance>()
		);
	}

	class Object: public osg::Object {
	public:
		PYOSG_DISABLE_WARNINGS

		META_Object(pyosg::detail, Object)

		PYOSG_ENABLE_WARNINGS

		using osg::Object::Object;

		explicit Object(): osg::Object() {
			std::cout << "C++ CONSTRUCTION!" << std::endl;
		}

		~Object() override {
			if(debug_del) std::cout << "C++ destruction!" << std::endl;

			else std::cout << "C++ destruction (WITHOUT debug_del)!" << std::endl;
		}

		// TODO: These are used often, and Python subclasses MIGHT need to override them!
		// void resizeGLObjectBuffers(unsigned int /*maxSize*/) override
		// void releaseGLObjects(osg::State* = 0) const override

		bool debug_del = false;
	};
}

void bind_Object(py::module_& m) {
	py::object RefCounts = py::module_::import("collections").attr("namedtuple")(
		"RefCounts",
		py::make_tuple("cpp", "py")
	);

	m.attr("RefCounts") = RefCounts;

	py::class_<osg::Referenced, osg::ref_ptr<osg::Referenced>>(m, "Referenced")
		.def("ref", [](osg::Referenced& self) { return self.ref(); })
		.def("unref", [](osg::Referenced& self) { return self.unref(); })
		// .def_property_readonly("referenceCount", &osg::Referenced::referenceCount)
		// This returns both the `osg::Referenced` value AND the value reported by CPython. Remember
		// that the value returned by CPython is always +1 greater than you might expect!
		.def_property_readonly("referenceCount", [RefCounts](py::handle h) {
			auto& self = h.cast<osg::Referenced&>();

			return RefCounts(self.referenceCount(), h.ref_count());
		})
		.def_property_readonly(
			"addr",
			[](const osg::Referenced& self) { return reinterpret_cast<uintptr_t>(&self); }
		);
	;

	auto obj = py::class_<
		osg::Object,
		detail::Object,
		osg::Referenced,
		osg::ref_ptr<osg::Object>
	>(m, "Object");

	py::enum_<osg::Object::DataVariance>(obj, "DataVariance")
		.value("DYNAMIC", osg::Object::DYNAMIC)
		.value("STATIC", osg::Object::STATIC)
		.value("UNSPECIFIED", osg::Object::UNSPECIFIED)
		.export_values()
	;

	obj
		.def(py::init_alias<>())
		.def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Object> o = new detail::Object();

			detail::kwargs_init(*o, kwargs);

			return o;
		}))
		// .def_readwrite("debug_del", &detail::Object::debug_del)
		.def_property(
			"debug_del",
			[](detail::Object& self) { return self.debug_del; },
			[](detail::Object& self, bool dd) { self.debug_del = dd; }
		)
		.def_property(
			"name",
			&osg::Object::getName,
			py::overload_cast<const char*>(&osg::Object::setName)
		)
		.def_property(
			"dataVariance",
			&osg::Object::getDataVariance,
			&osg::Object::setDataVariance
		)
		.def_property(
			"userData",
			py::overload_cast<>(&osg::Object::getUserData),
			[](osg::Object& self, osg::Referenced* data) { self.setUserData(data); },
			py::return_value_policy::reference_internal
			/* py::cpp_function(
				py::overload_cast<>(&osg::Object::getUserData),
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				[](osg::Object& self, osg::Referenced* data) { self.setUserData(data); },
				py::keep_alive<1, 2>()
			) */
		)
		// TODO: This will be difficult to handle properly, and will likely end up using
		// `py::capsule`. However, it's only really useful for C++ interop, as Python itself already
		// HAS better mechanisms for this!
		//
		// The implementation should look like:
		//
		// n = osg.Node()
		// n.userValue(int, "val", 10)
		// i = n.userValue(int, "val")
		//
		// userValue
	;
}

}
