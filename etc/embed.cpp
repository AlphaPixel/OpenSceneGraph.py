#include "pyosg.hpp"

PYOSG_DISABLE_WARNINGS

#include <osg/Node>

PYOSG_ENABLE_WARNINGS

int main(int argc, char** argv) {
	pyosg::Interpreter::init();

	pyosg::Interpreter pi;

	// auto osg = pi.osg();
	// auto node = osg.attr("Node")();

	// if(node) {
		pi.exec(R"(n = OpenSceneGraph.osg.Node(name="n0"))");

		auto n = pi.eval("n").cast<osg::ref_ptr<osg::Node>>();

		std::cout << "Node name: " << n->getName() << std::endl;
	// }

	return 0;
}
