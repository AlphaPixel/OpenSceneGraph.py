#include "pyosg.hpp"
#include "pyosgDB.hpp"
#include "pyosgGA.hpp"
#include "pyosgUtil.hpp"
#include "pyosgViewer.hpp"

#include "pybind11x.hpp"

#include <osg/Version>

#ifdef PYOSG_EMBEDDED
extern "C" PYBIND11_EXPORT PyObject *PyInit_pyosg();
#endif

PYOSG_CONSTRUCTOR(pyosg_preinit) {
  // OSG_INFO << "PYOSG_CONSTRUCTOR: You can do your static init here..." <<
  // std::endl;
}

#include <atomic>
#include <chrono>
#include <thread>

namespace pyx = pybind11x;

struct StopEvent {
  std::atomic<bool> stop{false};
};

/* struct LoopQueueScope {
public:
        LoopQueueScope(py::object loop, py::object queue): _loop(loop),
_queue(queue) {}

        template<typename... Args>
        void put_nowait(Args&&... args) {
                py::gil_scoped_acquire gil;

                _loop.attr("call_soon_threadsafe")(
                        _queue.attr("put_nowait"),
                        py::make_tuple(std::forward<Args>(args)...)
                );
        }

private:
        py::object _loop;
        py::object _queue;
} */

template <typename... Args>
void put_nowait(const py::object &loop, const py::object &queue,
                Args &&...args) {
  py::gil_scoped_acquire gil;

  // static py::object call_soon = loop.attr("call_soon_threadsafe");
  // static py::object put = queue.attr("put_nowait");

  loop.attr("call_soon_threadsafe")(
      queue.attr("put_nowait"), py::make_tuple(std::forward<Args>(args)...));
}

std::string pyosg_async_task_example(size_t seconds, StopEvent *stop,
                                     py::object loop, py::object queue,
                                     size_t job_id) {
  py::gil_scoped_release release;

  size_t steps = seconds * 10;

  for (size_t i = 0; i < steps; i++) {
    if (stop && stop->stop.load(std::memory_order_relaxed)) {
      std::cerr << "C++: detected stop" << std::endl;

      put_nowait(loop, queue, "complete", job_id, "stopped");

      return "stopped";
    }

    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    auto progress = static_cast<float>(i + 1) / static_cast<float>(steps);

    put_nowait(loop, queue, "progress", job_id, progress);
  }

  put_nowait(loop, queue, "complete", job_id, "result-from-cpp");

  return "result-from-cpp";
}

PYBIND11_MODULE(pyosg, m) {
  auto osg = m.def_submodule("osg", "osg namespace");

  pyosg::bind(osg);

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

  gl.attr("GL_RGBA") = GL_RGBA;
  gl.attr("GL_DEPTH_COMPONENT24") = GL_DEPTH_COMPONENT24;
  gl.attr("GL_DEPTH_COMPONENT") = GL_DEPTH_COMPONENT;
  gl.attr("GL_FLOAT") = GL_FLOAT;
  gl.attr("GL_UNSIGNED_INT") = GL_UNSIGNED_INT;
  gl.attr("GL_COLOR_BUFFER_BIT") = GL_COLOR_BUFFER_BIT;
  gl.attr("GL_DEPTH_BUFFER_BIT") = GL_DEPTH_BUFFER_BIT;
  gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
  gl.attr("GL_SCISSOR_TEST") = GL_SCISSOR_TEST;

  gl.attr("GL_BLEND") = GL_BLEND;
  gl.attr("GL_DEPTH_TEST") = GL_DEPTH_TEST;
  gl.attr("GL_VERTEX_PROGRAM_POINT_SIZE") = GL_VERTEX_PROGRAM_POINT_SIZE;
  gl.attr("GL_PROGRAM_POINT_SIZE") = GL_PROGRAM_POINT_SIZE;
  //  gl.attr("GL_POINT_SPRITE") = GL_POINT_SPRITE;
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

  py::class_<StopEvent>(m, "StopEvent")
      .def(py::init<>())
      .def("stop", [](StopEvent &t) { t.stop.store(true); });

  m.def("pyosg_async_task_example", &pyosg_async_task_example, "seconds"_a,
        "stop_event"_a, "loop"_a, "queue"_a, "job_id"_a);
}
