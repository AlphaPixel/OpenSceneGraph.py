#pragma once

#include "../pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Uniform>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	// ------------------------------------------------------------
	// CREATE (TYPE-DRIVEN)
	// ------------------------------------------------------------

	inline osg::Uniform* make_uniform_typed(
		const std::string& name,
		osg::Uniform::Type type,
		py::object value
	) {
		switch(type) {
			case osg::Uniform::BOOL:
				return new osg::Uniform(name.c_str(), value.cast<bool>());

			case osg::Uniform::INT:
				return new osg::Uniform(name.c_str(), value.cast<int>());

			case osg::Uniform::UNSIGNED_INT: {
				auto v = value.cast<long long>();

				if(v < 0) throw py::value_error("Cannot assign negative value to UNSIGNED_INT");

				return new osg::Uniform(name.c_str(), static_cast<unsigned int>(v));
			}

			case osg::Uniform::FLOAT:
				return new osg::Uniform(name.c_str(), value.cast<float>());

			case osg::Uniform::DOUBLE:
				return new osg::Uniform(name.c_str(), value.cast<double>());

			case osg::Uniform::FLOAT_VEC2:
				return new osg::Uniform(name.c_str(), value.cast<osg::Vec2>());

			case osg::Uniform::FLOAT_VEC3:
				return new osg::Uniform(name.c_str(), value.cast<osg::Vec3>());

			case osg::Uniform::FLOAT_MAT4:
				return new osg::Uniform(name.c_str(), value.cast<osg::Matrixf>());

			default:
				throw py::type_error("Unsupported Uniform type");
		}
	}

	// ------------------------------------------------------------
	// CREATE (PYTHON TYPE INFERENCE)
	// ------------------------------------------------------------

	inline osg::Uniform* make_uniform_infer(const std::string& name, py::handle h) {
		// IMPORTANT: `bool` must come before `int`; thanks Python! :)
		if(py::isinstance<py::bool_>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<bool>());
		}

		if(py::isinstance<py::int_>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<int>());
		}

		if(py::isinstance<py::float_>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<float>());
		}

		if(py::isinstance<osg::Vec2>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<osg::Vec2>());
		}

		if(py::isinstance<osg::Vec3>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<osg::Vec3>());
		}

		if(py::isinstance<osg::Matrixf>(h)) {
			return new osg::Uniform(name.c_str(), h.cast<osg::Matrixf>());
		}

		throw py::type_error("Cannot infer Uniform type from Python object");
	}

	// ------------------------------------------------------------
	// MAIN CREATE ENTRY
	// ------------------------------------------------------------

	inline osg::Uniform* make_uniform(const std::string& name, py::handle h) {
		// This supports a convenience layer where instead of implicitly inferring the type, it
		// can be explicitly inidcated in a tuple pairing: `(osg.Uniform.DOUBLE, 2.2)`. It is
		// mostly used by the `UniformsProxy` in `StateSet`.
		if(py::isinstance<py::tuple>(h)) {
			auto t = py::cast<py::tuple>(h);

			if(t.size() < 2 || t.size() > 3)
				throw py::type_error("Uniform tuple must be (type, value[, mode])");

			auto type = t[0].cast<osg::Uniform::Type>();
			auto value = t[1];

			return make_uniform_typed(name, type, value);
		}

		// Otherwise, we'll fall back to implicit detection.
		return make_uniform_infer(name, h);
	}

	// ------------------------------------------------------------
	// SET (TYPE-DRIVEN)
	// ------------------------------------------------------------

	template<typename T>
	void _uniform_set(
		osg::Uniform& self,
		unsigned int i,
		py::object obj,
		const char* name
	) {
		T v;

		try {
			v = obj.cast<T>();
		}

		catch(const py::cast_error&) {
			throw py::type_error(std::string("Invalid type for ") + name + " Uniform");
		}

		if(!self.setElement(i, v)) throw py::type_error("Uniform assignment failed");
	}

	inline void uniform_set(osg::Uniform& self, py::ssize_t index, py::object obj) {
		auto i = n_index<unsigned int>(self.getNumElements(), index);

		switch(self.getType()) {
			case osg::Uniform::INT:
				_uniform_set<int>(self, i, obj, "INT");
				return;

			case osg::Uniform::UNSIGNED_INT:
				_uniform_set<unsigned int>(self, i, obj, "UNSIGNED_INT");
				return;

			case osg::Uniform::FLOAT:
				_uniform_set<float>(self, i, obj, "FLOAT");
				return;

			case osg::Uniform::DOUBLE:
				_uniform_set<double>(self, i, obj, "DOUBLE");
				return;

			case osg::Uniform::BOOL:
				_uniform_set<bool>(self, i, obj, "BOOL");
				return;

			case osg::Uniform::FLOAT_VEC2:
				_uniform_set<osg::Vec2f>(self, i, obj, "FLOAT_VEC2");
				return;

			case osg::Uniform::FLOAT_VEC3:
				_uniform_set<osg::Vec3f>(self, i, obj, "FLOAT_VEC3");
				return;

			case osg::Uniform::FLOAT_MAT4:
				_uniform_set<osg::Matrixf>(self, i, obj, "FLOAT_MAT4");
				return;

			default:
				throw py::type_error("Unsupported Uniform type for assignment");
		}
	}

	// ------------------------------------------------------------
	// GET
	// ------------------------------------------------------------

	inline py::object uniform_get(osg::Uniform& self, py::ssize_t index) {
		auto i = n_index<unsigned int>(self.getNumElements(), index);

		switch(self.getType()) {
			case osg::Uniform::BOOL: {
				bool v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::INT: {
				int v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::UNSIGNED_INT: {
				unsigned int v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::FLOAT: {
				float v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::DOUBLE: {
				double v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::FLOAT_VEC2: {
				osg::Vec2 v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::FLOAT_VEC3: {
				osg::Vec3 v; self.getElement(i, v);

				return py::cast(v);
			}

			case osg::Uniform::FLOAT_MAT4: {
				osg::Matrixf v; self.getElement(i, v);

				return py::cast(v);
			}

			default:
				throw py::type_error("Unsupported underlying Uniform type");
		}
	}

	// ------------------------------------------------------------
	// ARRAY ACCESS (unchanged)
	// ------------------------------------------------------------

	inline py::object uniform_get_array(osg::Uniform& self) {
		if(auto* a = self.getFloatArray()) return py::cast(a);
		if(auto* a = self.getDoubleArray()) return py::cast(a);
		if(auto* a = self.getIntArray()) return py::cast(a);
		if(auto* a = self.getUIntArray()) return py::cast(a);
		if(auto* a = self.getInt64Array()) return py::cast(a);
		if(auto* a = self.getUInt64Array()) return py::cast(a);
		return py::none();
	}

	inline void uniform_set_array(osg::Uniform& self, py::object obj) {
		if(auto* a = obj.cast<osg::FloatArray*>()) { self.setArray(a); return; }
		if(auto* a = obj.cast<osg::DoubleArray*>()) { self.setArray(a); return; }
		if(auto* a = obj.cast<osg::IntArray*>()) { self.setArray(a); return; }
		if(auto* a = obj.cast<osg::UIntArray*>()) { self.setArray(a); return; }
		if(auto* a = obj.cast<osg::Int64Array*>()) { self.setArray(a); return; }
		if(auto* a = obj.cast<osg::UInt64Array*>()) { self.setArray(a); return; }

		throw py::type_error("Unsupported array type for Uniform.array");
	}

	// ------------------------------------------------------------
	// ITERATOR (unchanged)
	// ------------------------------------------------------------

	struct UniformIterator {
		osg::Uniform* u = nullptr;
		std::size_t index = 0;

		py::object next() {
			if(!u || index >= u->getNumElements())
				throw py::stop_iteration();

			return uniform_get(*u, static_cast<py::ssize_t>(index++));
		}
	};

} // namespace detail

void bind_Uniform(py::module_& m);

} // namespace pyosg
