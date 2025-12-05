#include "../osg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Array>

PYOSG_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	template<typename T>
	auto bind_Array(py::module_& m, const char* name) {
		return py::class_<T, osg::Array, osg::ref_ptr<T>>(m, name, py::buffer_protocol())
			.def(py::init<>())
			.def(py::init<size_t>(), py::arg("size"))

			// .def("append", [](T& self, const osg::Vec3& v) { self.push_back(v); })

			// https://pybind11.readthedocs.io/en/stable/advanced/pycpp/numpy.html
			.def_buffer([](T& self) -> py::buffer_info {
				auto n = static_cast<py::ssize_t>(self.size());

				// Number of components for each value of `n` above; for example, 1 if it's a "flat"
				// array of floats, 2 for Vec2, 3 for Vec3, etc.
				auto comps = static_cast<py::ssize_t>(self.getDataSize());

				py::ssize_t itemsize = 0;
				std::string fmt;

				// GL_FLOAT, GL_DOUBLE, GL_INT...
				switch(self.getDataType()) {
					case GL_FLOAT:
						itemsize = sizeof(float);
						fmt = py::format_descriptor<float>::format();
						break;

					case GL_DOUBLE:
						itemsize = sizeof(double);
						fmt = py::format_descriptor<double>::format();
						break;

					case GL_INT:
						itemsize = sizeof(int);
						fmt = py::format_descriptor<int>::format();
						break;

					case GL_UNSIGNED_INT:
						itemsize = sizeof(unsigned);
						fmt = py::format_descriptor<unsigned>::format();
						break;

					default:
						throw std::runtime_error("Unsupported osg::Array data type");
				}

				if(comps == 1) return py::buffer_info(
					const_cast<void*>(self.getDataPointer()),
					itemsize,
					fmt,
					1,
					{ n },
					{ itemsize }
				);

				return py::buffer_info(
					const_cast<void*>(self.getDataPointer()),
					itemsize,
					fmt,
					2,
					{ n, comps },
					{ itemsize * comps, itemsize }
				);
			})

			.def("__len__", [](const T& self) { return self.size(); })

			.def("__getitem__", [](const T& self, py::ssize_t index) {
				if(index < 0 || static_cast<size_t>(index) >= self.size()) index_error(self.size());

				return self[static_cast<unsigned int>(index)];
			})

			.def("__setitem__", [](T& self, py::ssize_t index, const osg::Vec3& value) {
				if(index < 0 || static_cast<size_t>(index) >= self.size()) index_error(self.size());

				self[static_cast<unsigned int>(index)] = value;
			})

			.def("__repr__", [name](const T& self) {
				return py::str("{}(size={})").format(name, self.size());
			})
		;
	}
}

void bind_Array(py::module_& m) {
	py::class_<
		osg::Array,
		osg::BufferData,
		osg::ref_ptr<osg::Array>
	>(m, "Array")
		// .def(py::init_alias<>())
		// .def(py::init<const osg::BufferData&>())

		// .def_propert("bufferObject"
		// .def_propert("bufferIndex"
	;

	detail::bind_Array<osg::Vec3Array>(m, "Vec3Array")
		// .def_static("test", [](size_t size) -> osg::ref_ptr<osg::Vec3Array> {
		.def_static("test", [](size_t size) {
			return new osg::Vec3Array(size);
		})
	;
}

}
