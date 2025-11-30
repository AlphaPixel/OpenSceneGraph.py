#include "osg.hpp"

int main(int argc, char** argv) {
	pyosg::Interpreter::init();

	pyosg::Interpreter py;

	auto osg = py.osg();
	auto node = osg.attr("Node")();

	if(node) std::cout << "YES" << std::endl;

	return 0;
}
