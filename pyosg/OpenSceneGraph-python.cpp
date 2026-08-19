#include "pyosg.hpp"
#include "pyosgAnimation.hpp"
#include "pyosgUtil.hpp"
#include "pyosgDB.hpp"
#include "pyosgGA.hpp"
#include "pyosgViewer.hpp"

#include "pybind11x.hpp"

#include <osg/Version>

#include <GL/gl.h>

#include <osgDB/Registry>

#include <algorithm>
#include <filesystem>
#include <limits>

#ifdef PYOSG_EMBEDDED
	extern "C" PYBIND11_EXPORT PyObject* PyInit_OpenSceneGraph();
#endif

PYOSG_CONSTRUCTOR(pyosg_preinit) {
	// OSG_INFO << "PYOSG_CONSTRUCTOR: You can do your static init here..." << std::endl;
}

#include <thread>
#include <chrono>

namespace pyx = pybind11x;

namespace {

void add_packaged_plugin_path(py::module_& module) {
	const auto module_file = py::str(module.attr("__file__")).cast<std::string>();
	const auto plugin_directory = std::filesystem::path(module_file).parent_path() / PYOSG_OSG_PLUGIN_DIR;
	std::error_code error;

	// Ordinary developer/system-OSG builds do not necessarily install private
	// plugins next to the extension. The wheel does; only register a real path.
	if(!std::filesystem::is_directory(plugin_directory, error)) return;

	const auto plugin_path = plugin_directory.string();
	auto& paths = osgDB::Registry::instance()->getLibraryFilePathList();

	if(std::find(paths.begin(), paths.end(), plugin_path) == paths.end()) {
		paths.push_back(plugin_path);
	}
}

} // namespace

std::string pyosg_async_task_example(
	size_t seconds,
	pyx::StopEvent* stop,
	py::object loop,
	py::object queue,
	size_t job_id
) {
	py::gil_scoped_release release;

	size_t steps = seconds * 10;

	for(size_t i = 0; i < steps; i++) {
		if(stop && stop->stop.load(std::memory_order_relaxed)) {
			// std::cerr << "C++: detected stop" << std::endl;

			pyx::put_nowait(loop, queue, "complete", job_id, "stopped");

			return "stopped";
		}

		std::this_thread::sleep_for(std::chrono::milliseconds(100));

		auto progress = static_cast<float>(i + 1) / static_cast<float>(steps);

		pyx::put_nowait(loop, queue, "progress", job_id, progress);
	}

	pyx::put_nowait(loop, queue, "complete", job_id, "result-from-cpp");

	return "result-from-cpp";
}

PYBIND11_MODULE(OpenSceneGraph, m) {
	// The wheel owns its deliberately supported osgDB plugins. Register their
	// private directory when the core module imports, so loading a packaged
	// format does not require an otherwise unrelated `import osgx`.
	add_packaged_plugin_path(m);

	auto osg = m.def_submodule("osg", "osg namespace");

	pyosg::bind(osg);

	auto osgAnimation = m.def_submodule("osgAnimation", "osgAnimation namespace");

	pyosgAnimation::bind(osgAnimation);

	auto osgUtil = m.def_submodule("osgUtil", "osgUtil namespace");

	pyosgUtil::bind(osgUtil);

	auto osgDB = m.def_submodule("osgDB", "osgDB namespace");

	pyosgDB::bind(osgDB);

	auto osgGA = m.def_submodule("osgGA", "osgGA namespace");

	pyosgGA::bind(osgGA);

	auto osgViewer = m.def_submodule("osgViewer", "osgViewer namespace");

	pyosgViewer::bind(osgViewer);

	// ============================================================================================
	// TODO: I add these as I need them! Later, we need to add... all. :(
	auto gl = m.def_submodule("GL");

	gl.attr("GL_POINTS") = GL_POINTS;
	gl.attr("GL_LINES") = GL_LINES;
	gl.attr("GL_LINE_LOOP") = GL_LINE_LOOP;
	gl.attr("GL_LINE_STRIP") = GL_LINE_STRIP;
	gl.attr("GL_TRIANGLES") = GL_TRIANGLES;
	gl.attr("GL_TRIANGLE_STRIP") = GL_TRIANGLE_STRIP;
	gl.attr("GL_TRIANGLE_FAN") = GL_TRIANGLE_FAN;

	gl.attr("GL_RED") = GL_RED;
	gl.attr("GL_RGB") = GL_RGB;
	gl.attr("GL_RGBA") = GL_RGBA;
	gl.attr("GL_RGBA8") = GL_RGBA8;
	gl.attr("GL_RGB16F") = GL_RGB16F;
	gl.attr("GL_RGB32F") = GL_RGB32F;
	gl.attr("GL_RGBA16F") = GL_RGBA16F;
	gl.attr("GL_RGBA32F") = GL_RGBA32F;
	gl.attr("GL_DEPTH_COMPONENT24") = GL_DEPTH_COMPONENT24;
	gl.attr("GL_DEPTH_COMPONENT") = GL_DEPTH_COMPONENT;
	gl.attr("GL_FLOAT") = GL_FLOAT;
	gl.attr("GL_HALF_FLOAT") = GL_HALF_FLOAT;
	gl.attr("GL_UNSIGNED_INT") = GL_UNSIGNED_INT;
	gl.attr("GL_UNSIGNED_BYTE") = GL_UNSIGNED_BYTE;
	gl.attr("GL_COLOR_BUFFER_BIT") = GL_COLOR_BUFFER_BIT;
	gl.attr("GL_DEPTH_BUFFER_BIT") = GL_DEPTH_BUFFER_BIT;
	gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
	gl.attr("GL_SCISSOR_TEST") = GL_SCISSOR_TEST;
	gl.attr("GL_CULL_FACE") = GL_CULL_FACE;

	gl.attr("GL_BLEND") = GL_BLEND;
	gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
	gl.attr("GL_VERTEX_PROGRAM_POINT_SIZE") = GL_VERTEX_PROGRAM_POINT_SIZE;
	gl.attr("GL_PROGRAM_POINT_SIZE") = GL_PROGRAM_POINT_SIZE;
	gl.attr("GL_SRC_ALPHA") = GL_SRC_ALPHA;
	gl.attr("GL_ONE_MINUS_SRC_ALPHA") = GL_ONE_MINUS_SRC_ALPHA;
	gl.attr("GL_ONE") = GL_ONE;

	// ============================================================================================
	py::dict info;

	info["osg"] = osgGetVersion();

	pyx::build_info(m, info);

	m.attr("F32_MIN") = std::numeric_limits<float>::min();
	m.attr("F32_MAX") = std::numeric_limits<float>::max();
	m.attr("F32_LOWEST") = std::numeric_limits<float>::lowest();

	m.attr("F64_MIN") = std::numeric_limits<double>::min();
	m.attr("F64_MAX") = std::numeric_limits<double>::max();
	m.attr("F64_LOWEST") = std::numeric_limits<double>::lowest();

	/* py::module_ atexit = py::module_::import("atexit");

	atexit.attr("register")( py::cpp_function([]() { })); */

	py::class_<pyx::StopEvent>(m, "StopEvent")
		.def(py::init<>())
		.def("stop", [](pyx::StopEvent& t) { t.stop.store(true); })
	;

	m.def("pyosg_async_task_example",
		&pyosg_async_task_example,
		"seconds"_a,
		"stop_event"_a,
		"loop"_a,
		"queue"_a,
		"job_id"_a
	);
}
