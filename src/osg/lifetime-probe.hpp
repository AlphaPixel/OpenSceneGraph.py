#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Object>
#include <osg/UserDataContainer>

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

							pyo(addr, type, name);
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

		static void attachTo(osg::Object* o) {
			o->getOrCreateUserDataContainer()->addUserObject(
				new LifetimeProbe(o, py::bool_(true))
			);
		}

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
}

}
