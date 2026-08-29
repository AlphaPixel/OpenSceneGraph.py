#pragma once

#include "pybind11x.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/Object>
#include <osg/UserDataContainer>
#include <osg/ref_ptr>

OSGX_ENABLE_WARNINGS

namespace pybind11x {

// The OSG form of kwargs_ctor(): allocate through ref_ptr so the returned object follows OSG's
// intrusive-reference ownership model.
template<typename T, typename... Args>
auto kwargs_ctor() {
	return [](Args... args, py::kwargs kwargs) {
		osg::ref_ptr<T> obj = new T(args...);

		kwargs_init(*obj, kwargs);

		return obj;
	};
}

// Attaches ProxyStorage directly to an osg::Object via UserDataContainer, giving OSG-created
// objects persistent Python-facing state regardless of where they originated.
template<typename T, typename... Proxies>
struct ProxyStorageOSG: public osg::Object, public ProxyStorage<T, Proxies...> {
	using base_type = ProxyStorage<T, Proxies...>;

	META_Object(pyosg, ProxyStorageOSG)

	ProxyStorageOSG(): osg::Object(), base_type() {
		setName("pyosg.ProxyStorage");
	}

	explicit ProxyStorageOSG(T* obj): osg::Object(), base_type(obj) {
		setName("pyosg.ProxyStorage");
	}

	ProxyStorageOSG(
		const ProxyStorageOSG& rhs,
		const osg::CopyOp& copyop=osg::CopyOp::SHALLOW_COPY
	):
	osg::Object(rhs, copyop),
	base_type() {
	}

	static ProxyStorageOSG* get(T& obj) {
		auto* udc = obj.getOrCreateUserDataContainer();

		for(unsigned int i = 0; i < udc->getNumUserObjects(); i++) {
			if(auto* s = dynamic_cast<ProxyStorageOSG*>(udc->getUserObject(i))) return s;
		}

		auto* s = new ProxyStorageOSG(&obj);

		udc->addUserObject(s);

		return s;
	}
};

template<typename Derived>
struct OwnerAccess<Derived, ProxyStorageOSG> {
	using owner_type = Derived&;

	static owner_type from_self(Derived& self) {
		return self;
	}
};

template<typename Derived, size_t N>
using PropertySlots = BasicPropertySlots<Derived, N, ProxyStorageOSG>;

}
