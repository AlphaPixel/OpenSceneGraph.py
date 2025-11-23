// This is just a simple embedded interpreter for help generating Valgrind/ASAN/LSAN suppressions.

#include <Python.h>

#include <iostream>

int main(int argc, char** argv) {
	Py_Initialize();

	if(!Py_IsInitialized()) {
		std::cerr << "Failed to initialize Python\n";

		return 1;
	}

	// PyRun_SimpleString("print('HelloWorld')");

	// per CPython docs: nonzero if finalize fails
	if(Py_FinalizeEx() < 0) return 1;

	return 0;
}
