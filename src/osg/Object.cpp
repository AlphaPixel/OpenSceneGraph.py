#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Object>
#include <osgDB/Registry>

PYOSG_ENABLE_WARNINGS

#include <sstream>

namespace pyosg {

namespace detail {
	class PYOSG_INTERNAL LifetimeProbe: public osg::Object {
	public:
		PYOSG_DISABLE_WARNINGS

		META_Object(pyosg, LifetimeProbe)

		PYOSG_ENABLE_WARNINGS

		LifetimeProbe() = default;

		explicit LifetimeProbe(osg::Object* o, py::object cb=py::none()):
		addr(reinterpret_cast<uintptr_t>(o)),
		name(o ? o->getName() : ""),
		type(o ? o->className() : ""),
		pyo(std::move(cb)) {
			// std::cout << "py::bool_(pyo) = " << py::bool_(pyo) << std::endl;
			// std::cout << "PyCallable_Check(pyo.ptr()) = " << PyCallable_Check(pyo.ptr()) << std::endl;

			if(py::bool_(pyo) && !PyCallable_Check(pyo.ptr())) _notify("Observing");
		}

		~LifetimeProbe() {
			if(py::bool_(pyo)) {
				if(!PyCallable_Check(pyo.ptr())) _notify("Destroying");

				else {
					try {
						if(Py_IsInitialized()) {
							// TODO: Remove me!
							_notify("Destroying (Py_IsInitialized())");

							py::gil_scoped_acquire gil;

							pyo(addr, name, type);
						}

						// TODO: Remove me!
						else _notify("Destroying (!Py_IsInitialized())");
					}

					catch(const py::error_already_set& e) {
						std::cerr
							<< "Python exception in destructor callback:"
							<< e.what() << std::endl
						;
					}

					catch(...) {
						// TODO: Remove me!
						_notify("Destroying (EXCEPTION)");
					}
				}
			}
		}

		LifetimeProbe(
			const LifetimeProbe& rhs,
			const osg::CopyOp& copyop=osg::CopyOp::SHALLOW_COPY
		):
		osg::Object() {}

	protected:
		void _notify(const std::string& action) {
			std::cerr
				<< action << " " << std::hex << addr << std::dec
				<< " [" << type << "]"
				<< " (" << name << ")" << std::endl
			;
		}

		uintptr_t addr = 0;

		std::string name;
		std::string type;

		py::object pyo;
	};

	template<>
	void kwargs_init(osg::Object& self, const py::kwargs& kwargs) {
		if(kwargs.contains("name")) self.setName(kwargs["name"].cast<std::string>());

		if(kwargs.contains("dataVariance")) self.setDataVariance(
			kwargs["dataVariance"].cast<osg::Object::DataVariance>()
		);

		if(kwargs.contains("debug")) {
			auto dbg = kwargs["debug"];

			if(py::bool_(dbg)) self.getOrCreateUserDataContainer()->addUserObject(
				new LifetimeProbe(&self, dbg)
			);
		}
	}

	// This class exists to permit Python code like: `o = osg.Object`.
	class Object: public osg::Object {
	public:
		PYOSG_DISABLE_WARNINGS

		// It's weird not using `pyosg` here, but doing so would break serialization.
		META_Object(osg, Object)

		PYOSG_ENABLE_WARNINGS

		using osg::Object::Object;

		explicit Object(): osg::Object() {}
		// ~Object() override {}

		// TODO: These are used often, and Python subclasses MIGHT need to override them!
		// void resizeGLObjectBuffers(unsigned int) override
		// void releaseGLObjects(osg::State* = 0) const override
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
			)
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

	// TODO: This is a temporary debugging method; REMOVE IT (eventually).
	obj.def("dumps", [](osg::Object& self, const std::string& ext) {
		auto* rw = osgDB::Registry::instance()->getReaderWriterForExtension(ext);

		if(!rw) throw std::runtime_error("No ReaderWriter for extension: " + ext);

		std::ostringstream oss;

		auto r = rw->writeObject(self, oss, nullptr);

		if(!r.success()) throw std::runtime_error(r.message());

		return py::bytes(oss.str());
	}, "ext"_a="osg");
}

}
