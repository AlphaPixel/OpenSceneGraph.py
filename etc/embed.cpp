#include "pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Node>

PYOSG_ENABLE_WARNINGS

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

	return 0;
}
