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

# Keep this mapping explicit: the add-on wheel may install only files it owns
# below the base package's examples directory. In particular, it must never
# install OpenSceneGraph/__init__.py, OpenSceneGraph/examples/__init__.py, or
# OpenSceneGraph/examples/__main__.py.
install(FILES "pyosg-khronos-viewer.py"
	DESTINATION "OpenSceneGraph/examples"
	RENAME "khronos_viewer.py"
)

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
