// This is just a simple embedded interpreter for help generating Valgrind/ASAN/LSAN suppressions.

#include <Python.h>

#include <iostream>

int main(int argc, char** argv) {
	Py_Initialize();

	if(!Py_IsInitialized()) {
		std::cerr << "Failed to initialize Python" << std::endl;

		return 1;
	}

	// Run any Python code here that you want to subject to Valgrind/ASAN sanity checks!
	// PyRun_SimpleString("print('HelloWorld')");

	// per CPython docs: nonzero if finalize fails
	if(Py_FinalizeEx() < 0) return 2;

	return 0;
}
