#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/observer_ptr>
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

		explicit LifetimeProbe(osg::Object* o, py::object pyo=py::none()):
		_addr(reinterpret_cast<uintptr_t>(o)),
		_name(o ? o->getName() : ""),
		_type(o ? o->className() : ""),
		_pyo(std::move(pyo)),
		_obj(o) {
			setName("pyosg.LifetimeProbe");

			if(py::bool_(_pyo) && !PyCallable_Check(_pyo.ptr())) _notify("Observing", false);
		}

		~LifetimeProbe() {
			if(py::bool_(_pyo)) {
				if(!PyCallable_Check(_pyo.ptr())) _notify("Destroying");

				else {
					try {
						if(Py_IsInitialized()) {
							// TODO: Remove me!
							_notify("Destroying (Py_IsInitialized())");

							py::gil_scoped_acquire gil;

							_pyo(_addr, _type, _name);
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

		static void attachTo(osg::Object* o, py::object pyo=py::bool_(true)) {
			o->getOrCreateUserDataContainer()->addUserObject(
				// new LifetimeProbe(o, py::bool_(true))
				new LifetimeProbe(o, pyo)
			);
		}

	protected:
		void _notify(const std::string& action, bool checkValid=true) {
			std::cerr
				<< action << " " << std::hex << _addr << std::dec
				<< " [" << _type << "]"
				<< " (" << _name << ")"
			;

			if(_obj.valid() && checkValid) std::cerr << " WARNING: Object still valid!";

			std::cerr << std::endl;
		}

		uintptr_t _addr = 0;

		std::string _name;
		std::string _type;

		py::object _pyo;

		osg::observer_ptr<osg::Object> _obj;
	};
}

}
