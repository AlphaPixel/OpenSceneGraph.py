#pragma once

#include "lifetime-probe.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/ValueObject>
#include <osgDB/Registry>

OSGX_ENABLE_WARNINGS

#include <limits>

#include "pybind11x-osg.hpp"

namespace pyx = pybind11x;

namespace pyosg {

namespace detail {
	// This class exists to permit Python code like: `o = osg.Object`.
	class Object: public osg::Object {
	public:
		OSGX_DISABLE_WARNINGS

		// It's weird not using `pyosg` here, but doing so would break serialization.
		META_Object(osg, Object)

		OSGX_ENABLE_WARNINGS

		using osg::Object::Object;

		explicit Object(): osg::Object() {}
		// ~Object() override {}

		// TODO: These are used often, and Python subclasses MIGHT need to override them!
		// void resizeGLObjectBuffers(unsigned int) override
		// void releaseGLObjects(osg::State* = 0) const override
	};

	class UserDataContainer: public osg::UserDataContainer {
	public:
		using osg::UserDataContainer::UserDataContainer;

		// void setUserData(Referenced* obj) = 0;
		// Referenced* getUserData() = 0;
		// const Referenced* getUserData() const  = 0;
		// unsigned int addUserObject(Object* obj)  = 0;
		// void setUserObject(unsigned int i, Object* obj)  = 0;
		// void removeUserObject(unsigned int i)  = 0;
		// unsigned int getUserObjectIndex(const osg::Object* obj, unsigned int startPos=0) const = 0;
		// unsigned int getUserObjectIndex(const std::string& name, unsigned int startPos=0) const = 0;
		// void setDescriptions(const DescriptionList& descriptions) = 0;
		// DescriptionList& getDescriptions() = 0;
		// const DescriptionList& getDescriptions() const = 0;
		// unsigned int getNumDescriptions() const = 0;
		// void addDescription(const std::string& desc) = 0;

		unsigned int getNumUserObjects() const override {
			PYBIND11_OVERRIDE_PURE(
				unsigned int,
				osg::UserDataContainer,
				getNumUserObjects
			);
		}

		// const Object* getUserObject(unsigned int i) const  = 0;
		osg::Object* getUserObject(unsigned int i) override {
			PYBIND11_OVERRIDE_PURE(
				osg::Object*,
				osg::UserDataContainer,
				getUserObject
				i
			);
		}
	};

	template<typename T>
	std::uintptr_t objectAddress(const T& self) {
		OSGX_DISABLE_WARNINGS

			const void* ptr = dynamic_cast<const void*>(&self);

		OSGX_ENABLE_WARNINGS

		return reinterpret_cast<std::uintptr_t>(ptr);
	}

	struct UserValuesTag;

	// Python int -> a C++ integer type, raising ValueError (not pybind11's generic cast_error)
	// when the value does not fit.
	template<typename V>
	V narrowInt(py::handle h) {
		auto i = h.cast<long long>();

		if(
			i < static_cast<long long>(std::numeric_limits<V>::min()) ||
			i > static_cast<long long>(std::numeric_limits<V>::max())
		) throw py::value_error("integer " + std::to_string(i) + " out of range");

		return static_cast<V>(i);
	}

	// Converts a stored osg::ValueObject to its Python value. Types with no Python binding (the
	// integer Vec variants) leave `result` null.
	class PYOSG_INTERNAL UserValueGetter: public osg::ValueObject::GetValueVisitor {
	public:
		using osg::ValueObject::GetValueVisitor::apply;

		py::object result;

		void apply(bool v) override { result = py::bool_(v); }
		void apply(char v) override { result = py::int_(v); }
		void apply(unsigned char v) override { result = py::int_(v); }
		void apply(short v) override { result = py::int_(v); }
		void apply(unsigned short v) override { result = py::int_(v); }
		void apply(int v) override { result = py::int_(v); }
		void apply(unsigned int v) override { result = py::int_(v); }
		void apply(float v) override { result = py::float_(v); }
		void apply(double v) override { result = py::float_(v); }
		void apply(const std::string& v) override { result = py::str(v); }
		void apply(const osg::Vec2f& v) override { result = py::cast(v); }
		void apply(const osg::Vec3f& v) override { result = py::cast(v); }
		void apply(const osg::Vec4f& v) override { result = py::cast(v); }
		void apply(const osg::Vec2d& v) override { result = py::cast(v); }
		void apply(const osg::Vec3d& v) override { result = py::cast(v); }
		void apply(const osg::Vec4d& v) override { result = py::cast(v); }
		void apply(const osg::Quat& v) override { result = py::cast(v); }
		void apply(const osg::Plane& v) override { result = py::cast(v); }
		void apply(const osg::Matrixf& v) override { result = py::cast(v); }
		void apply(const osg::Matrixd& v) override { result = py::cast(v); }
		void apply(const osg::BoundingBoxf& v) override { result = py::cast(v); }
		void apply(const osg::BoundingBoxd& v) override { result = py::cast(v); }
		void apply(const osg::BoundingSpheref& v) override { result = py::cast(v); }
		void apply(const osg::BoundingSphered& v) override { result = py::cast(v); }
	};

	// Writes a Python value into an existing osg::ValueObject, converting to the type already
	// stored (C++ getUserValue<T>() requires an exact typeid match, so the stored type must not
	// change underneath it). `handled` stays false for types with no Python binding.
	class PYOSG_INTERNAL UserValueSetter: public osg::ValueObject::SetValueVisitor {
	public:
		using osg::ValueObject::SetValueVisitor::apply;

		explicit UserValueSetter(py::handle h): value(h) {}

		py::handle value;
		bool handled = false;

		void apply(bool& v) override { assign(v); }
		void apply(char& v) override { assignInt(v); }
		void apply(unsigned char& v) override { assignInt(v); }
		void apply(short& v) override { assignInt(v); }
		void apply(unsigned short& v) override { assignInt(v); }
		void apply(int& v) override { assignInt(v); }
		void apply(unsigned int& v) override { assignInt(v); }
		void apply(float& v) override { assign(v); }
		void apply(double& v) override { assign(v); }
		void apply(std::string& v) override { assign(v); }
		void apply(osg::Vec2f& v) override { assign(v); }
		void apply(osg::Vec3f& v) override { assign(v); }
		void apply(osg::Vec4f& v) override { assign(v); }
		void apply(osg::Vec2d& v) override { assign(v); }
		void apply(osg::Vec3d& v) override { assign(v); }
		void apply(osg::Vec4d& v) override { assign(v); }
		void apply(osg::Quat& v) override { assign(v); }
		void apply(osg::Plane& v) override { assign(v); }
		void apply(osg::Matrixf& v) override { assign(v); }
		void apply(osg::Matrixd& v) override { assign(v); }
		void apply(osg::BoundingBoxf& v) override { assign(v); }
		void apply(osg::BoundingBoxd& v) override { assign(v); }
		void apply(osg::BoundingSpheref& v) override { assign(v); }
		void apply(osg::BoundingSphered& v) override { assign(v); }

	private:
		template<typename V>
		void assign(V& v) {
			v = value.cast<V>();
			handled = true;
		}

		template<typename V>
		void assignInt(V& v) {
			v = narrowInt<V>(value);
			handled = true;
		}
	};
}

void bind_Object(py::module_& m);

}

// Object.userValues - the TemplateValueObject<T> entries getUserValue()/setUserValue() manage,
// keyed by name. Non-ValueObject user objects sharing the container (ProxyStorage, lifetime
// probes, arbitrary addUserObject() payloads) are invisible here. Reads never create a
// UserDataContainer; only assigning a new key does (via setUserValue()). Duplicate names resolve
// to the first match, same as getUserValue().
template<>
struct pyx::ValueMappingTraits<osg::Object, pyosg::detail::UserValuesTag> {
	using key_type = std::string;
	using value_type = py::object;

	static value_type from_python(py::handle h) {
		return py::reinterpret_borrow<py::object>(h);
	}

	static osg::UserDataContainer* container(osg::Object* obj) {
		if(auto* udc = obj->asUserDataContainer()) return udc;

		return obj->getUserDataContainer();
	}

	static osg::ValueObject* find(osg::Object* obj, const key_type& key) {
		auto* udc = container(obj);

		if(!udc) return nullptr;

		auto* o = udc->getUserObject(key);

		return o ? o->asValueObject() : nullptr;
	}

	static std::vector<key_type> keys(osg::Object* obj) {
		std::vector<key_type> out;

		auto* udc = container(obj);

		if(!udc) return out;

		for(unsigned int i = 0; i < udc->getNumUserObjects(); i++) {
			auto* o = udc->getUserObject(i);

			if(!o || !o->asValueObject()) continue;

			if(std::find(out.begin(), out.end(), o->getName()) == out.end()) {
				out.push_back(o->getName());
			}
		}

		return out;
	}

	static size_t size(osg::Object* obj) {
		return keys(obj).size();
	}

	static bool contains(osg::Object* obj, key_type key) {
		return find(obj, key) != nullptr;
	}

	static value_type get(osg::Object* obj, key_type key) {
		auto* vo = find(obj, key);

		if(!vo) throw py::key_error(key);

		pyosg::detail::UserValueGetter gvv;

		vo->get(gvv);

		if(!gvv.result) throw py::type_error(
			"user value '" + key + "' (" + vo->className() + ") has no Python type"
		);

		return gvv.result;
	}

	static void set(osg::Object* obj, key_type key, value_type value) {
		if(auto* vo = find(obj, key)) {
			pyosg::detail::UserValueSetter svv(value);

			try {
				vo->set(svv);
			}

			catch(const py::cast_error&) {
				throw py::type_error(
					"user value '" + key + "' (" + vo->className() + ") cannot be assigned a '" +
					py::str(py::type::handle_of(value).attr("__name__")).cast<std::string>() + "'; `del` it "
					"first to change its type"
				);
			}

			if(!svv.handled) throw py::type_error(
				"user value '" + key + "' (" + vo->className() + ") has no Python type"
			);

			return;
		}

		// setUserValue() replaces ANY user object with a matching name; refuse rather than
		// silently discard a non-value object (ProxyStorage, a probe, a user payload).
		if(auto* udc = container(obj); udc && udc->getUserObject(key)) throw py::value_error(
			"'" + key + "' names a user object that is not a value"
		);

		if(py::isinstance<py::bool_>(value)) obj->setUserValue(key, value.cast<bool>());
		else if(py::isinstance<py::int_>(value)) obj->setUserValue(
			key,
			pyosg::detail::narrowInt<int>(value)
		);
		else if(py::isinstance<py::float_>(value)) obj->setUserValue(key, value.cast<double>());
		else if(py::isinstance<py::str>(value)) obj->setUserValue(key, value.cast<std::string>());
		else if(!setTyped<
			osg::Vec2f, osg::Vec3f, osg::Vec4f,
			osg::Vec2d, osg::Vec3d, osg::Vec4d,
			osg::Quat, osg::Plane,
			osg::Matrixf, osg::Matrixd,
			osg::BoundingBoxf, osg::BoundingBoxd,
			osg::BoundingSpheref, osg::BoundingSphered
		>(obj, key, value)) throw py::type_error(
			"cannot store a '" + py::str(py::type::handle_of(value).attr("__name__")).cast<std::string>() +
			"' as a user value"
		);
	}

	static void del(osg::Object* obj, key_type key) {
		auto* udc = container(obj);

		if(!find(obj, key)) throw py::key_error(key);

		udc->removeUserObject(udc->getUserObjectIndex(key));
	}

private:
	template<typename... Vs>
	static bool setTyped(osg::Object* obj, const key_type& key, py::handle value) {
		return ((
			py::isinstance<Vs>(value) && (obj->setUserValue(key, value.cast<Vs>()), true)
		) || ...);
	}
};

namespace pyosg::detail {
	using UserValuesProxy = pyx::ValueMappingProxy<osg::Object, UserValuesTag>;
}
