#pragma once

#include "../pyosg.hpp"

OSGX_DISABLE_WARNINGS

#include <osg/ArgumentParser>

OSGX_ENABLE_WARNINGS

namespace pyosg {

namespace detail {
	struct ArgumentParser {
		// This "owns" all the data that is NORMALLY hosted by the OS and passed into your
		// executable via argc/argv.
		std::vector<std::string> storage;

		// These are the ACTUAL values passed into the actual OSG object.
		int argc;
		std::vector<char*> argv;

		osg::ArgumentParser parser;

		// Helper that fills storage/argv and returns a fully constructed osg::ArgumentParser.
		static osg::ArgumentParser create(
			std::vector<std::string>& storage,
			int& argc,
			std::vector<char*>& argv,
			const std::string& name,
			const py::sequence& args
		) {
			storage.clear();
			argv.clear();

			storage.reserve(args.size() + 1);
			argv.reserve(args.size() + 1);

			// First, add the standard `argv[0]` argument name.
			storage.push_back(name);
			argv.push_back(storage.back().data());

			// Now, iterate over everything passed-in via the sequence and add them to our storage,
			// as well as the `char*` vector corresponding to `argv`.
			for(py::handle h : args) {
				storage.emplace_back(py::str(h));
				argv.push_back(storage.back().data());
			}

			argc = static_cast<int>(argv.size());

			return osg::ArgumentParser(&argc, argv.data());
		}

		ArgumentParser(const std::string& name, const py::sequence& args):
		storage(),
		argc(0),
		argv(),
		parser(create(storage, argc, argv, name, args)) {}

		static constexpr const char* DOCSTRING = R"(
			A thin adapter for OSG's legacy argc/argv-style ArgumentParser.

			This exists *only* to support integration with OSG APIs that expect
			an `osg::ArgumentParser` (e.g., plugin loaders, `osgViewer` command-line
			utilities, `DisplaySettings::readCommandLine`, and various osgDB helpers).

			It is **not** intended to be a full-featured argument-parsing solution
			for Python. Use Python's standard libraries (`argparse`, etc.) for real
			parsing, PLEASE.

			Python users generally should not need to construct this manually unless
			explicitly calling into an OSG API that requires it.

			Internally this wrapper owns the backing storage needed for a valid
			argc and C-style argv array, ensuring that OSG receives stable,
			lifetime-correct pointers as expected.
		)";
	};
}

void bind_ArgumentParser(py::module_& m);

}
