cmake_minimum_required(VERSION 3.18)

# This is a separate, pure-Python/data wheel build for the optional
# `openscenegraph-examples` distribution. The root project owns native bindings
# and remains the single source of version information.
project(OpenSceneGraph-examples LANGUAGES NONE)

# Prepared third-party payload is intentionally supplied from outside the
# source tree. `build-local-wheel.sh` writes it under its scratch directory;
# CI will prepare the same layout from a pinned asset manifest. An empty path
# still permits a lightweight code-only wheel for package-layout testing.
set(PYOSG_EXAMPLES_ASSET_DIR ""
	CACHE PATH "Prepared examples asset directory to include in the wheel"
)

# PYOSG_OFFICIAL_EXAMPLES is defined once in manifest.cmake (this directory)
# and shared with the root CMakeLists.txt's dev-tree overlay; see that file for the
# curated list itself.
include("${CMAKE_CURRENT_SOURCE_DIR}/manifest.cmake")

# Keep this mapping explicit: the add-on wheel may install only files it owns
# below the base package's examples directory. In particular, it must never
# install OpenSceneGraph/__init__.py, OpenSceneGraph/examples/__init__.py, or
# OpenSceneGraph/examples/__main__.py.
foreach(PYOSG_EXAMPLE_ENTRY IN LISTS PYOSG_OFFICIAL_EXAMPLES)
	string(REPLACE "=" ";" PYOSG_EXAMPLE_ENTRY "${PYOSG_EXAMPLE_ENTRY}")
	list(GET PYOSG_EXAMPLE_ENTRY 0 PYOSG_EXAMPLE_SRC)
	list(GET PYOSG_EXAMPLE_ENTRY 1 PYOSG_EXAMPLE_DST)

	# A dst containing "/" (e.g. "lighting/lambert.py") places it in a subpackage --
	# RENAME only accepts a bare filename, so the subdirectory (if any) goes on
	# DESTINATION instead.
	get_filename_component(PYOSG_EXAMPLE_DST_DIR "${PYOSG_EXAMPLE_DST}" DIRECTORY)
	get_filename_component(PYOSG_EXAMPLE_DST_NAME "${PYOSG_EXAMPLE_DST}" NAME)

	install(FILES "${PYOSG_EXAMPLE_SRC}"
		DESTINATION "OpenSceneGraph/examples/${PYOSG_EXAMPLE_DST_DIR}"
		RENAME "${PYOSG_EXAMPLE_DST_NAME}"
	)
endforeach()

if(NOT PYOSG_EXAMPLES_ASSET_DIR STREQUAL "")
	if(NOT IS_DIRECTORY "${PYOSG_EXAMPLES_ASSET_DIR}")
		message(FATAL_ERROR
			"PYOSG_EXAMPLES_ASSET_DIR is not a directory: "
			"${PYOSG_EXAMPLES_ASSET_DIR}"
		)
	endif()

	# The generated glTF manifests reference their KTX2 payload by sibling
	# relative URI, so preserve the prepared directory hierarchy verbatim.
	install(DIRECTORY "${PYOSG_EXAMPLES_ASSET_DIR}/"
		DESTINATION "OpenSceneGraph/examples/assets"
	)
endif()

# Do not glob the source examples tree: most scripts are development-only, and
# third-party payload must remain selected/auditable.
