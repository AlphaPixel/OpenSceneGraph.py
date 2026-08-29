#include "pyosgDB.hpp"

OSGX_DISABLE_WARNINGS

#include <osgDB/ReadFile>
#include <osgDB/WriteFile>

OSGX_ENABLE_WARNINGS

namespace pyosgDB {

void bind(py::module_& m) {
	py::class_<osgDB::Registry, osg::Referenced, osg::ref_ptr<osgDB::Registry>>(
		m,
		"Registry",
		"The process-wide singleton owning every loaded ReaderWriter plugin, reached via "
		"Registry.instance()."
	)
		.def_static(
			"instance",
			&osgDB::Registry::instance,
			"erase"_a=false,
			"Return the process-wide ReaderWriter registry singleton."
		)
		.def("getReaderWriterForExtension", &osgDB::Registry::getReaderWriterForExtension,
			"Return the plugin registered for a filename extension."
		)
		.def("getReaderWriterForMimeType", &osgDB::Registry::getReaderWriterForMimeType,
			"Return the plugin registered for a MIME type."
		)
	;

	auto opts = py::class_<osgDB::Options, osg::Object, osg::ref_ptr<osgDB::Options>>(
		m,
		"Options",
		"Per-call settings (caching, precision, plugin-specific strings) passed to a "
		"ReaderWriter or the readXFile()/writeXFile() helpers."
	);

	py::enum_<osgDB::Options::CacheHintOptions>(opts, "CacheHintOptions", py::arithmetic(),
		"Control which resource types a ReaderWriter may cache."
	)
		.value("CACHE_NONE", osgDB::Options::CACHE_NONE)
		.value("CACHE_NODES", osgDB::Options::CACHE_NODES)
		.value("CACHE_IMAGES", osgDB::Options::CACHE_IMAGES)
		.value("CACHE_HEIGHTFIELDS", osgDB::Options::CACHE_HEIGHTFIELDS)
		.value("CACHE_ARCHIVES", osgDB::Options::CACHE_ARCHIVES)
		.value("CACHE_OBJECTS", osgDB::Options::CACHE_OBJECTS)
		.value("CACHE_SHADERS", osgDB::Options::CACHE_SHADERS)
		.value("CACHE_ALL", osgDB::Options::CACHE_ALL)
		.export_values()
	;

	py::enum_<osgDB::Options::PrecisionHint>(opts, "PrecisionHint", py::arithmetic(),
		"Request double precision for selected data written by a ReaderWriter."
	)
		.value("FLOAT_PRECISION_ALL", osgDB::Options::FLOAT_PRECISION_ALL)
		.value("DOUBLE_PRECISION_VERTEX", osgDB::Options::DOUBLE_PRECISION_VERTEX)
		.value("DOUBLE_PRECISION_NORMAL", osgDB::Options::DOUBLE_PRECISION_NORMAL)
		.value("DOUBLE_PRECISION_COLOR", osgDB::Options::DOUBLE_PRECISION_COLOR)
		.value("DOUBLE_PRECISION_SECONDARY_COLOR", osgDB::Options::DOUBLE_PRECISION_SECONDARY_COLOR)
		.value("DOUBLE_PRECISION_FOG_COORD", osgDB::Options::DOUBLE_PRECISION_FOG_COORD)
		.value("DOUBLE_PRECISION_TEX_COORD", osgDB::Options::DOUBLE_PRECISION_TEX_COORD)
		.value("DOUBLE_PRECISION_VERTEX_ATTRIB", osgDB::Options::DOUBLE_PRECISION_VERTEX_ATTRIB)
		.value("DOUBLE_PRECISION_ALL", osgDB::Options::DOUBLE_PRECISION_ALL)
		.export_values()
	;

	py::enum_<osgDB::Options::BuildKdTreesHint>(opts, "BuildKdTreesHint",
		"Control whether a ReaderWriter builds acceleration kd-trees."
	)
		.value("NO_PREFERENCE", osgDB::Options::NO_PREFERENCE)
		.value("DO_NOT_BUILD_KDTREES", osgDB::Options::DO_NOT_BUILD_KDTREES)
		.value("BUILD_KDTREES", osgDB::Options::BUILD_KDTREES)
		.export_values()
	;

	opts
		.def(py::init<>(), "Create options with OSG's default settings.")
		.def_property(
			"optionString",
			&osgDB::Options::getOptionString,
			&osgDB::Options::setOptionString,
			"Plugin-specific option string passed to a ReaderWriter."
		)
		// TODO: *PluginStringData as `MappingProxy`
	;

	auto rw = py::class_<
		osgDB::ReaderWriter,
		osg::Object,
		osg::ref_ptr<osgDB::ReaderWriter>
	>(
		m,
		"ReaderWriter",
		"Base class for a file-format plugin (registered with Registry) that reads/writes "
		"Objects, Nodes, and Images for a given extension."
	)
		.def(py::init<>(), "Create a ReaderWriter base instance.")
		.def(
			"writeObject",
			py::overload_cast<
				const osg::Object&,
				const std::string&,
				const osgDB::Options*
			>(&osgDB::ReaderWriter::writeObject, py::const_),
			"object"_a,
			"path"_a,
			"options"_a=nullptr,
			"Write object to path and return the WriteResult."
		)
		.def("writeObject", [](
			osgDB::ReaderWriter& self,
			const osg::Object& obj,
			const osgDB::Options* opts_
		) {
			std::ostringstream oss;

			auto r = self.writeObject(obj, oss, opts_);

			return py::make_tuple(r, oss.str());
		},
			"object"_a,
			"options"_a=nullptr,
			"Write object to a string and return its WriteResult and text."
		)
	;

	auto rr = py::class_<osgDB::ReaderWriter::ReadResult>(rw, "ReadResult",
		"Result returned by a ReaderWriter read operation."
	);

	py::enum_<osgDB::ReaderWriter::ReadResult::ReadStatus>(rr, "ReadStatus",
		"Describe the outcome of a ReaderWriter read operation."
	)
		.value("NOT_IMPLEMENTED", osgDB::ReaderWriter::ReadResult::NOT_IMPLEMENTED)
		.value("FILE_NOT_HANDLED", osgDB::ReaderWriter::ReadResult::FILE_NOT_HANDLED)
		.value("FILE_NOT_FOUND", osgDB::ReaderWriter::ReadResult::FILE_NOT_FOUND)
		.value("ERROR_IN_READING_FILE", osgDB::ReaderWriter::ReadResult::ERROR_IN_READING_FILE)
		.value("FILE_LOADED", osgDB::ReaderWriter::ReadResult::FILE_LOADED)
		.value("FILE_LOADED_FROM_CACHE", osgDB::ReaderWriter::ReadResult::FILE_LOADED_FROM_CACHE)
		.value("FILE_REQUESTED", osgDB::ReaderWriter::ReadResult::FILE_REQUESTED)
		.value(
			"INSUFFICIENT_MEMORY_TO_LOAD",
			osgDB::ReaderWriter::ReadResult::INSUFFICIENT_MEMORY_TO_LOAD
		)
		.export_values()
	;

	rr
		.def_property_readonly(
			"message",
			py::overload_cast<>(&osgDB::ReaderWriter::ReadResult::message, py::const_),
			"Diagnostic message supplied by the ReaderWriter."
		)
	;

	auto wr = py::class_<osgDB::ReaderWriter::WriteResult>(rw, "WriteResult",
		"Result returned by a ReaderWriter write operation."
	);

	py::enum_<osgDB::ReaderWriter::WriteResult::WriteStatus>(wr, "WriteStatus",
		"Describe the outcome of a ReaderWriter write operation."
	)
		.value("NOT_IMPLEMENTED", osgDB::ReaderWriter::WriteResult::NOT_IMPLEMENTED)
		.value("FILE_NOT_HANDLED", osgDB::ReaderWriter::WriteResult::FILE_NOT_HANDLED)
		.value("ERROR_IN_WRITING_FILE", osgDB::ReaderWriter::WriteResult::ERROR_IN_WRITING_FILE)
		.value("FILE_SAVED", osgDB::ReaderWriter::WriteResult::FILE_SAVED)
		.export_values()
	;

	wr
		.def_property_readonly("status", &osgDB::ReaderWriter::WriteResult::status,
			"Status code returned by the ReaderWriter."
		)
		.def_property_readonly(
			"message",
			py::overload_cast<>(&osgDB::ReaderWriter::WriteResult::message, py::const_),
			"Diagnostic message supplied by the ReaderWriter."
		)
	;

	m.def(
		"readObjectFile", [](const std::string& filename) {
			osg::Object* obj = osgDB::readObjectFile(filename);

			if(!obj) pyosg::detail::file_not_found(filename);

			return obj;
		},
		"filename"_a,
		"Read an OSG object from a file; pybind11 downcasts to the concrete type (e.g. osg.TextureCubeMap)"
	);

	m.def(
		"readNodeFile", [](const std::string& filename) {
			auto* node = osgDB::readNodeFile(filename);

			if(!node) pyosg::detail::file_not_found(filename);

			return node;
		},
		"filename"_a,
		"Read an OSG node from a file and return it as an osg.Node"
	);

	m.def(
		"readImageFile", [](const std::string& filename) {
			auto* img = osgDB::readImageFile(filename);

			if(!img) pyosg::detail::file_not_found(filename);

			return img;
		},
		"filename"_a,
		"Read an OSG image from a file and return it as an osg.Image"
	);

	m.def(
		"writeImageFile", [](const osg::Image& img, const std::string& filename) {
			return osgDB::writeImageFile(img, filename);
		},
		"img"_a,
		"filename"_a,
		"Write an OSG image from an osg.Image to the specified filename"
	);

	m.def(
		"writeObjectFile", [](const osg::Object& obj, const std::string& filename) {
			return osgDB::writeObjectFile(obj, filename);
		},
		"obj"_a,
		"filename"_a,
		"Write an OSG object (e.g. osg.TextureCubeMap) to the specified filename"
	);

	// m.def("readNodeFile", py::overload_cast<const std::string&>(&osgDB::readNodeFile));

	/* m.def(
		"readNodeFile",
		py::overload_cast<const std::string&, const osgDB::Options*>(&osgDB::readNodeFile),
		"filename"_a,
		"options"_a
	); */
}

}
