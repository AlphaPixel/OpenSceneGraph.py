//vimrun! ./embed

#include "pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Node>
#include <osgDB/ReadFile>
#include <osgViewer/Viewer>

PYOSG_ENABLE_WARNINGS

#include <algorithm>
#include <cstddef>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

// TODO: Move this into `pyosg::embed::dedent`!
inline std::string dedent(std::string_view text, std::string_view indent) {
	std::string out;

	// skip leading newline from R"(\n
	if(!text.empty() && text.front() == '\n') text.remove_prefix(1);

	// skip trailing newline before )"
	if(!text.empty() && text.back() == '\n') text.remove_suffix(1);

	while(!text.empty()) {
		if(text.starts_with(indent)) text.remove_prefix(indent.size());

		auto nl = text.find('\n');

		if(nl == std::string_view::npos) { out.append(text); break; }

		out.append(text.substr(0, nl + 1));
		text.remove_prefix(nl + 1);
	}

	return out;
}

constexpr auto SCRIPT = R"(
	from OpenSceneGraph import *

	import time

	v = osgViewer.Viewer()

	v.realize()
	v.sceneData = osgDB.readNodeFile("glsl_simple.osgt")

	for i in range(5):
		v.frame()

		print("Sleeping inside Python for 0.5s...")

		time.sleep(0.5)

	print("Returning 'v' to C++...")
	print(f"Address is: {hex(v.addr)}")
)";

int main(int argc, char** argv) {
	// TODO: Treat this line like osgEarth does with `GL3RealizeOperation`.
	pyosg::Interpreter::init();

	pyosg::Interpreter pi;

	// Bring an instance FROM Python INTO C++...
	pi.exec(R"(pyn = OpenSceneGraph.osg.Node(name="n0"))");

	auto pyn = pi.eval("pyn").cast<osg::ref_ptr<osg::Node>>();

	std::cout << "Node name: " << pyn->getName() << std::endl;

	// Export an instance FROM C++ INTO Python...
	auto* cppn = new osg::Node();

	cppn->setName("n1");

	pi.globals()["cppn"] = py::cast(cppn);

	pi.exec(R"(print(cppn))");
	pi.exec(R"(print(cppn.name))");
	pi.exec(dedent(SCRIPT, "\t"));

	auto viewer = pi.eval("v").cast<osg::ref_ptr<osgViewer::Viewer>>();

	if(viewer) {
		OSG_NOTICE << "C++ viewer address is: " << viewer.get() << std::endl;

		return viewer->run();
	}

	return 1;
}
