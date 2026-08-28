#include "Object.hpp"

namespace pybind11x {
	template<>
	void kwargs_init_own(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());

		if(kwargs.contains("dataVariance")) self.setDataVariance(
			kwargs["dataVariance"].cast<osg::Object::DataVariance>()
		);

		if(kwargs.contains("debug")) pyosg::detail::LifetimeProbe::attachTo(&self, kwargs["debug"]);
	}
}

namespace pyosg {

void bind_Object(py::module_& m) {
	py::object RefCounts = py::module_::import("collections").attr("namedtuple")(
		"RefCounts",
		py::make_tuple("cpp", "py")
	);

	m.attr("RefCounts") = RefCounts;

	py::class_<osg::Referenced, osg::ref_ptr<osg::Referenced>>(
		m,
		"Referenced",
		"Root of OSG's intrusive reference-counting hierarchy; nearly everything else in "
		"osg/osgGA/osgViewer inherits its ref()/unref() lifetime. Its owning Python wrapper "
		"is tracked via the object's own UserDataContainer rather than pybind11's keep_alive<>, "
		"so a replaced/discarded C++ instance can be freed instead of leaking for the life of "
		"the process."
	)
		.def("ref", [](osg::Referenced& self) { return self.ref(); },
			"Manually increment the intrusive C++ reference count (rarely needed from Python)."
		)
		.def("unref", [](osg::Referenced& self) { return self.unref(); },
			"Manually decrement the intrusive C++ reference count, deleting self if it reaches 0."
		)
		// .def_property_readonly("referenceCount", &osg::Referenced::referenceCount)
		// This returns both the `osg::Referenced` value AND the value reported by CPython. Remember
		// that the value returned by CPython is always +1 greater than you might expect!
		.def_property_readonly("referenceCount", [RefCounts](py::handle h) {
			auto& self = h.cast<osg::Referenced&>();

			return RefCounts(self.referenceCount(), h.ref_count());
		}, "A (cpp, py) named tuple of the C++ ref_ptr count and CPython's own refcount; "
			"the py value is always 1 higher than expected (the temporary handle held here)."
		)
		.def_property_readonly(
			"addr",
			// This only returns the "offset" of `osg::Referenced` in the vtable, NOT the address we
			// actually want; in order to get that, we need the second (uglier) approach.
			// [](const osg::Referenced& self) { return reinterpret_cast<uintptr_t>(&self); }
			[](const osg::Referenced& self) { return detail::objectAddress(self); },
			"The real memory address of the underlying C++ object, as an integer - useful for "
			"confirming two Python wrappers refer to the same instance."
		);
	;

	auto obj = py::class_<
		osg::Object,
		detail::Object,
		osg::Referenced,
		osg::ref_ptr<osg::Object>
	>(
		m,
		"Object",
		"Base class adding a name, DataVariance, and a UserDataContainer on top of Referenced; "
		"the common ancestor of Node, StateAttribute, Array, and most other OSG types. Most "
		"subclasses accept name=/dataVariance=/etc. as constructor keyword arguments in "
		"addition to their traditional setters."
	);

	py::enum_<osg::Object::DataVariance>(obj, "DataVariance",
		"Hint for whether an Object's data may change per-frame (DYNAMIC, disabling some "
		"threading/caching optimizations) or never (STATIC)."
	)
		.value("DYNAMIC", osg::Object::DYNAMIC)
		.value("STATIC", osg::Object::STATIC)
		.value("UNSPECIFIED", osg::Object::UNSPECIFIED)
		.export_values()
	;

	obj
		.def(py::init_alias<>(), "Construct a bare, unnamed Object.")
		.def(py::init([](py::kwargs kwargs) {
			osg::ref_ptr<osg::Object> o = new detail::Object();

			pyx::kwargs_init(*o, kwargs);

			return o;
		}), "Construct, applying name=/dataVariance=/debug= keyword arguments.")
		.def_property(
			"name",
			&osg::Object::getName,
			py::overload_cast<const char*>(&osg::Object::setName),
			"This Object's (not-necessarily-unique) identifying string."
		)
		.def_property(
			"dataVariance",
			&osg::Object::getDataVariance,
			&osg::Object::setDataVariance,
			"DYNAMIC/STATIC/UNSPECIFIED hint consulted by threading/caching optimizations."
		)
		.def_property(
			"userData",
			/* py::overload_cast<>(&osg::Object::getUserData),
			[](osg::Object& self, osg::Referenced* data) { self.setUserData(data); },
			py::return_value_policy::reference_internal */
			py::cpp_function(
				py::overload_cast<>(&osg::Object::getUserData),
				py::return_value_policy::reference_internal
			),
			py::cpp_function(
				[](osg::Object& self, osg::Referenced* data) { self.setUserData(data); }
				// , py::keep_alive<1, 2>()
			),
			"A single arbitrary Referenced payload attached to this Object; for multiple named "
			"payloads use userDataContainer instead."
		)
		.def_property_readonly(
			"userDataContainer",
			&osg::Object::getOrCreateUserDataContainer,
			py::return_value_policy::reference_internal,
			"This Object's UserDataContainer, creating a DefaultUserDataContainer on first access."
		)
		// TODO: Some way to do this..
		// .def_property("debug", ...)
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

	py::class_<
		osg::UserDataContainer,
		detail::UserDataContainer,
		osg::Object,
		osg::ref_ptr<osg::UserDataContainer>
	>(
		m,
		"UserDataContainer",
		"Holds an arbitrary collection of named/indexed user Objects attached to an Object "
		"via Object.userDataContainer."
	)
		.def_property_readonly("numUserObjects", &osg::UserDataContainer::getNumUserObjects,
			"Count of Objects currently attached via addUserObject()."
		)
		.def("getUserObject", py::overload_cast<unsigned int>(
			&osg::UserDataContainer::getUserObject
		), "Return the attached Object at index i, by insertion order.")
	;

	py::class_<
		osg::DefaultUserDataContainer,
		osg::UserDataContainer,
		osg::ref_ptr<osg::DefaultUserDataContainer>
	>(
		m,
		"DefaultUserDataContainer",
		"OSG's standard UserDataContainer implementation, created automatically by "
		"Object.getOrCreateUserDataContainer()."
	);

	// TODO: This is a temporary debugging method; REMOVE IT (eventually).
	obj.def("dumps", [](osg::Object& self, const std::string& ext) {
		auto* rw = osgDB::Registry::instance()->getReaderWriterForExtension(ext);

		if(!rw) throw std::runtime_error("No ReaderWriter for extension: " + ext);

		std::ostringstream oss;

		auto r = rw->writeObject(self, oss, nullptr);

		if(!r.success()) throw std::runtime_error(r.message());

		return py::bytes(oss.str());
	}, "ext"_a="osg",
		"Serialize this Object through osgDB's writer for the given plugin extension "
		"(native/.osgt-style by default) and return the result as bytes."
	);

	obj.def("udcDebug", [](osg::Object& self) {
		auto* udc = self.getOrCreateUserDataContainer();

		for(unsigned int i = 0; i < udc->getNumUserObjects(); i++) {
			// if(auto* s = dynamic_cast<ProxyStorageOSG*>(udc->getUserObject(i))) return s;
			auto* o = udc->getUserObject(i);

			std::cerr << i << ": " << o->getName() << " " << o->referenceCount() << std::endl;
		}
	}, "Print each attached user Object's index, name, and reference count to stderr.");
}

}
