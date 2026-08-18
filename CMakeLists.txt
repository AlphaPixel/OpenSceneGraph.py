cmake_minimum_required(VERSION 3.18)

project(OpenSceneGraph-python LANGUAGES C CXX)

# An extension module needs Python headers but must not link to libpython on
# Unix. manylinux deliberately omits that embedding library, so request the
# module-development component rather than the aggregate Development one.
find_package(Python3 COMPONENTS Interpreter Development.Module REQUIRED)
# find_package(pybind11 REQUIRED)
add_subdirectory("etc/pybind11")

# The packaged build must not inherit an arbitrary distro OSG ABI or feature
# set. Keep this opt-in while the wheel work is still being established, but
# make the source and revision used by this path explicit and reproducible.
option(PYOSG_FETCH_OSG
    "Fetch and build the project-pinned OpenSceneGraph dependency" OFF)


# Defaults to the project-pinned OSG path, but accepts any osgx source checkout
# so contributors can keep developing the two projects side by side.
option(PYOSG_BUILD_OSGX
    "Build osgx alongside a manually supplied OpenSceneGraph" OFF)
set(PYOSG_OSGX_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/etc/osgx"
    CACHE PATH "Path to the osgx source checkout")
set(PYOSG_OSG_GIT_TAG "a827840baf0786d72e11ac16d5338a4ee25779db"
    CACHE STRING "OpenSceneGraph revision (OpenSceneGraph-3.6.5)")
set(PYOSG_OSG_PLUGIN_DIR "osgPlugins-3.6.5"
    CACHE STRING "Private OSG plugin directory for the pinned OpenSceneGraph release")

if(PYOSG_FETCH_OSG)
    include(FetchContent)

    # Build only the libraries needed by the bindings. In particular, plugins
    # are intentionally excluded: the first distributable wheel must not imply
    # support for arbitrary osgDB file formats.
    set(BUILD_OSG_APPLICATIONS OFF CACHE BOOL "" FORCE)
    set(BUILD_OSG_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(BUILD_OSG_PLUGINS OFF CACHE BOOL "" FORCE)
    set(BUILD_DOCUMENTATION OFF CACHE BOOL "" FORCE)

    # This project requires a modern core-profile OSG build.  Set every
    # derived capability explicitly as well, so a reused CMake cache cannot
    # re-enable fixed-function support.
    set(OPENGL_PROFILE GLCORE CACHE STRING "" FORCE)
    set(OSG_GL1_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL2_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL3_AVAILABLE ON CACHE BOOL "" FORCE)
    set(OSG_GL_DISPLAYLISTS_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL_MATRICES_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL_VERTEX_FUNCS_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL_VERTEX_ARRAY_FUNCS_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL_FIXED_FUNCTION_AVAILABLE OFF CACHE BOOL "" FORCE)
    set(OSG_GL_CONTEXT_VERSION "4.3" CACHE STRING "" FORCE)

    FetchContent_Declare(OpenSceneGraph
        GIT_REPOSITORY https://github.com/openscenegraph/OpenSceneGraph.git
        GIT_TAG "${PYOSG_OSG_GIT_TAG}"
        GIT_SHALLOW TRUE
        GIT_PROGRESS TRUE
    )
    FetchContent_GetProperties(OpenSceneGraph)
    if(NOT openscenegraph_POPULATED)
        FetchContent_Populate(OpenSceneGraph)
    endif()

    # The parent owns the wheel layout. Exclude OSG's normal headers,
    # pkg-config files, and broad library installation from this install.
    add_subdirectory("${openscenegraph_SOURCE_DIR}" "${openscenegraph_BINARY_DIR}" EXCLUDE_FROM_ALL)

    set(PYOSG_OSG_LIBRARIES
        OpenThreads
        osg
        osgAnimation
        osgDB
        osgGA
        # osgViewer and osgAnimation depend on osgText at runtime. Keep this
        # explicit so the first wheel contains its complete OSG runtime.
        osgText
        osgUtil
        osgViewer
    )
else()
    find_package(OpenSceneGraph REQUIRED
        osg
        osgAnimation
        osgUtil

        osgDB
        osgGA
        osgViewer
    )

    set(PYOSG_OSG_LIBRARIES ${OPENSCENEGRAPH_LIBRARIES})
endif()

if(PYOSG_FETCH_OSG OR PYOSG_BUILD_OSGX)
    if(NOT EXISTS "${PYOSG_OSGX_SOURCE_DIR}/CMakeLists.txt")
        message(FATAL_ERROR
            "PYOSG_BUILD_OSGX is ON, but PYOSG_OSGX_SOURCE_DIR "
            "Initialize etc/osgx or pass -DPYOSG_OSGX_SOURCE_DIR=/path/to/osgx.")
    endif()

    # The wheel owns this complete dependency graph. Build osgx's Python
    # module and its deliberately supported osgDB plugins, but no examples or
    # standalone installation rules.
    set(OSGX_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
    set(OSGX_BUILD_UTILS OFF CACHE BOOL "" FORCE)
    set(OSGX_BUILD_PYTHON ON CACHE BOOL "" FORCE)
    set(OSGX_BUILD_KTX2 ON CACHE BOOL "" FORCE)
    set(OSGX_BUILD_GLTF ON CACHE BOOL "" FORCE)
    set(OSGX_OPENSCENEGRAPH_PY_DIR "${CMAKE_CURRENT_SOURCE_DIR}" CACHE PATH "" FORCE)
    set(OSGX_INSTALL OFF CACHE BOOL "" FORCE)
    add_subdirectory("${PYOSG_OSGX_SOURCE_DIR}" "${CMAKE_BINARY_DIR}/_deps/osgx-build" EXCLUDE_FROM_ALL)
endif()

# # Step A -> generate C++ from Cython
# set(CYTHON_SRC ${CMAKE_CURRENT_SOURCE_DIR}/cython_part.pyx)
# set(CYTHON_CPP ${CMAKE_CURRENT_BINARY_DIR}/cython_part.cpp)
#
# add_custom_command(
# 	OUTPUT ${CYTHON_CPP}
# 	COMMAND ${Python3_EXECUTABLE} -m cython --cplus -3 ${CYTHON_SRC} -o ${CYTHON_CPP}
# 	DEPENDS ${CYTHON_SRC}
# 	COMMENT "Running Cython"
# 	VERBATIM
# )
#
# # Step B -> build Cython-generated module
# add_library(cython_part MODULE ${CYTHON_CPP})
# target_include_directories(cython_part PRIVATE ${Python3_INCLUDE_DIRS})
# set_target_properties(cython_part PROPERTIES
# 	PREFIX "" # no 'lib' prefix
# 	CXX_VISIBILITY_PRESET default
# 	VISIBILITY_INLINES_HIDDEN OFF
# )

# Step C -> build pybind11 module
# pybind11_add_module(pybind_part pybind_part.cpp)
# target_link_libraries(pybind_part PRIVATE Python3::Python)
# target_compile_features(pybind_part PUBLIC cxx_std_20)
# add_dependencies(pybind_part cython_part)

if(WIN32)
	set(PYOSG_COMPILE_OPTIONS
		"/W4"
		"/WX"
		"/wd4100"
		"/analyze"
		# "/wd4225"
		# "/wd4244"
		# "/wd4668"
		# "/wd4146"
		# "/wd4267"
		# "/wd4996"
		# "/wd4334"
		# "/wd4311"
	)

else(WIN32)
	if(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
		set(PYOSG_COMPILE_OPTIONS
			"-W"
			"-Wall"
			"-Wshadow"
			"-Wconversion"
			"-Wpedantic"
			"-Werror"
			"-Wno-unused-parameter"
		)
	else(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
		set(PYOSG_COMPILE_OPTIONS
			"-W"
			"-Wall"
			"-Wshadow"
			"-Wsign-conversion"
			"-Wpedantic"
			"-Werror"
			"-Wno-unused-parameter"
		)
	endif()
endif()

option(PYOSG_EMBEDDED "Build OpenSceneGraph bindings for embedding" OFF)

set(PYOSG_SOURCES
	"pyosg/pyosg.cpp"
	"pyosg/osg/ArgumentParser.cpp"
	"pyosg/osg/Notify.cpp"
	"pyosg/osg/Vec.cpp"
	"pyosg/osg/Quat.cpp"
	"pyosg/osg/Matrix.cpp"
	"pyosg/osg/Bound.cpp"
	"pyosg/osg/Buffer.cpp"
	"pyosg/osg/Array.cpp"
	"pyosg/osg/Object.cpp"
	"pyosg/osg/Node.cpp"
	"pyosg/osg/NodeCallback.cpp"
	"pyosg/osg/NodeVisitor.cpp"
	"pyosg/osg/Drawable.cpp"
	"pyosg/osg/Geometry.cpp"
	"pyosg/osg/Group.cpp"
	"pyosg/osg/Transform.cpp"
	"pyosg/osg/Geode.cpp"
	"pyosg/osg/Shape.cpp"
	"pyosg/osg/View.cpp"
	"pyosg/osg/Camera.cpp"
	"pyosg/osg/State.cpp"
	"pyosg/osg/StateAttributes.cpp"
	"pyosg/osg/Uniform.cpp"
	"pyosg/osg/Shader.cpp"
	"pyosg/osg/Program.cpp"
	"pyosg/osg/Texture.cpp"
	"pyosg/osg/Image.cpp"
	"pyosg/osg/GraphicsContext.cpp"
	"pyosg/osg/Operation.cpp"
	"pyosg/pyosgAnimation.cpp"
	"pyosg/pyosgUtil.cpp"
	"pyosg/pyosgDB.cpp"
	"pyosg/pyosgGA.cpp"
	"pyosg/pyosgViewer.cpp"
)

add_library(OpenSceneGraph_python STATIC ${PYOSG_SOURCES})

target_link_libraries(OpenSceneGraph_python PRIVATE
	Python3::Module
	pybind11::module
	${PYOSG_OSG_LIBRARIES}
)


if(PYOSG_FETCH_OSG OR PYOSG_BUILD_OSGX)
	# osgx is EXCLUDE_FROM_ALL, so make all wheel runtime products dependencies
	# of the extension target.
	add_dependencies(OpenSceneGraph_python osgx osgx_python osgdb_gltf osgdb_ktx2)
endif()
target_compile_options(OpenSceneGraph_python PRIVATE ${PYOSG_COMPILE_OPTIONS})
	target_compile_features(OpenSceneGraph_python PUBLIC cxx_std_20)
target_include_directories(OpenSceneGraph_python PUBLIC
	# TODO: This is currently a hack to ensure `pybind11x.hpp` is found! In the
	# future, it will come in as another submodule!
	"${CMAKE_SOURCE_DIR}/etc"
)

if(PYOSG_FETCH_OSG)
	target_include_directories(OpenSceneGraph_python PUBLIC
		"${OpenSceneGraph_SOURCE_DIR}/include"
		"${OpenSceneGraph_BINARY_DIR}/include"
	)
else()
	target_include_directories(OpenSceneGraph_python PUBLIC
		${OPENSCENEGRAPH_INCLUDE_DIRS}
	)
endif()
# TODO: PCH didn't help much, but the "unity" build made the project go from
# taking 3 full minutes to 30s or less. That's pretty incredible.
# target_precompile_headers(OpenSceneGraph_python PRIVATE "pyosg/pyosg_pch.hpp")
# set_target_properties(OpenSceneGraph_python PROPERTIES
# 	UNITY_BUILD ON
# 	UNITY_BUILD_BATCH_SIZE 1000
# )
set_property(TARGET OpenSceneGraph_python PROPERTY POSITION_INDEPENDENT_CODE ON)
# set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE ccache)

if(NOT PYOSG_EMBEDDED)
	pybind11_add_module(OpenSceneGraph "pyosg/OpenSceneGraph-python.cpp")

	target_link_libraries(OpenSceneGraph PRIVATE OpenSceneGraph_python)

	# Keep the extension and project-built OSG libraries together in the wheel.
	# $ORIGIN makes the installed extension independent of the CMake build tree
	# and avoids relying on LD_LIBRARY_PATH at import time.
	if(PYOSG_FETCH_OSG)
		set_target_properties(OpenSceneGraph ${PYOSG_OSG_LIBRARIES} PROPERTIES
			BUILD_RPATH "$ORIGIN"
			INSTALL_RPATH "$ORIGIN"
		)
	endif()

	install(TARGETS OpenSceneGraph
		LIBRARY DESTINATION "."
		RUNTIME DESTINATION "."
		ARCHIVE DESTINATION "."
	)

	if(PYOSG_FETCH_OSG)
		set_target_properties(osgx osgx_python ktx PROPERTIES
			BUILD_RPATH "$ORIGIN"
			INSTALL_RPATH "$ORIGIN"
		)
		set_target_properties(osgdb_gltf osgdb_ktx2 PROPERTIES
			BUILD_RPATH "$ORIGIN/.."
			INSTALL_RPATH "$ORIGIN/.."
		)

		install(TARGETS ${PYOSG_OSG_LIBRARIES} osgx osgx_python ktx
			LIBRARY DESTINATION "."
			RUNTIME DESTINATION "."
			ARCHIVE DESTINATION "."
		)
		install(TARGETS osgdb_gltf osgdb_ktx2
			LIBRARY DESTINATION "${PYOSG_OSG_PLUGIN_DIR}"
			RUNTIME DESTINATION "${PYOSG_OSG_PLUGIN_DIR}"
		)
	endif()

else()
	# This optional executable embeds the interpreter, unlike the extension
	# module above, so it genuinely needs the embedding library.
	find_package(Python3 COMPONENTS Development.Embed REQUIRED)
	add_executable(embed
		"pyosg/OpenSceneGraph-python.cpp"
		"etc/embed.cpp"
	)

	target_compile_definitions(embed PRIVATE PYOSG_EMBEDDED=1)
	target_link_libraries(embed PRIVATE Python3::Python pybind11::embed OpenSceneGraph_python)
	target_include_directories(embed PRIVATE "${CMAKE_SOURCE_DIR}/pyosg")
endif()

# pybind11_add_module(osgEarth
# 	"pyosg/osgEarth-python.cpp"
# )
#
# target_link_libraries(osgEarth PRIVATE
# 	Python3::Python
# 	osgEarthd
# )
# target_compile_features(osgEarth PUBLIC cxx_std_20)
# # target_link_libraries(osgEarth PRIVATE ${OPENSCENEGRAPH_LIBRARIES} osgEarthd)
# target_include_directories(osgEarth PRIVATE ${OPENSCENEGRAPH_INCLUDE_DIRS})
# target_link_directories(osgEarth PRIVATE "${CMAKE_INSTALL_PREFIX}/lib")
