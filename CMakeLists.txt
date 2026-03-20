cmake_minimum_required(VERSION 3.15)

project(OpenSceneGraph-python LANGUAGES C CXX)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
# find_package(pybind11 REQUIRED)
add_subdirectory("etc/pybind11")

# # Step A — generate C++ from Cython
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
# # Step B — build Cython-generated module
# add_library(cython_part MODULE ${CYTHON_CPP})
# target_include_directories(cython_part PRIVATE ${Python3_INCLUDE_DIRS})
# set_target_properties(cython_part PROPERTIES
# 	PREFIX ""  # no 'lib' prefix
# 	CXX_VISIBILITY_PRESET default
# 	VISIBILITY_INLINES_HIDDEN OFF
# )

# Step C — build pybind11 module
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

find_package(OpenSceneGraph REQUIRED
	osg
	osgDB
	osgGA
	osgViewer
	# osgUtil
	# osgText
)

option(PYOSG_EMBEDDED "Build OpenSceneGraph bindings for embedding" OFF)

set(PYOSG_SOURCES
	"src/pyosg.cpp"
	"src/osg/ArgumentParser.cpp"
	"src/osg/Notify.cpp"
	"src/osg/Vec.cpp"
	"src/osg/Matrix.cpp"
	"src/osg/Bound.cpp"
	"src/osg/Buffer.cpp"
	"src/osg/Array.cpp"
	"src/osg/Object.cpp"
	"src/osg/Node.cpp"
	"src/osg/NodeCallback.cpp"
	"src/osg/NodeVisitor.cpp"
	"src/osg/Drawable.cpp"
	"src/osg/Geometry.cpp"
	"src/osg/Group.cpp"
	"src/osg/Transform.cpp"
	"src/osg/Geode.cpp"
	"src/osg/Shape.cpp"
	"src/osg/View.cpp"
	"src/osg/Camera.cpp"
	"src/osg/State.cpp"
	"src/osg/StateAttributes.cpp"
	"src/osg/Uniform.cpp"
	"src/osg/Shader.cpp"
	"src/osg/Program.cpp"
	"src/osg/Texture.cpp"
	"src/osg/GraphicsContext.cpp"
	"src/pyosgDB.cpp"
	"src/pyosgGA.cpp"
	"src/pyosgViewer.cpp"
)

add_library(OpenSceneGraph_python STATIC ${PYOSG_SOURCES})

target_link_libraries(OpenSceneGraph_python PRIVATE
	Python3::Python
	pybind11::module
	${OPENSCENEGRAPH_LIBRARIES}
)
target_compile_features(OpenSceneGraph_python PUBLIC cxx_std_20)
target_compile_options(OpenSceneGraph_python PRIVATE ${PYOSG_COMPILE_OPTIONS})
target_include_directories(OpenSceneGraph_python PUBLIC ${OPENSCENEGRAPH_INCLUDE_DIRS})
# TODO: PCH didn't help much, but the "unity" build made the project go from
# taking 3 full minutes to 30s or less. That's pretty incredible.
# target_precompile_headers(OpenSceneGraph_python PRIVATE "src/pyosg_pch.hpp")
# set_target_properties(OpenSceneGraph_python PROPERTIES
# 	UNITY_BUILD ON
# 	UNITY_BUILD_BATCH_SIZE 1000
# )
set_property(TARGET OpenSceneGraph_python PROPERTY POSITION_INDEPENDENT_CODE ON)
# set_property(GLOBAL PROPERTY RULE_LAUNCH_COMPILE ccache)

if(NOT PYOSG_EMBEDDED)
	pybind11_add_module(OpenSceneGraph "src/OpenSceneGraph-python.cpp")

	target_link_libraries(OpenSceneGraph PRIVATE OpenSceneGraph_python)

else()
	add_executable(embed
		"src/OpenSceneGraph-python.cpp"
		"etc/embed.cpp"
	)

	target_compile_definitions(embed PRIVATE PYOSG_EMBEDDED=1)
	target_link_libraries(embed PRIVATE pybind11::embed OpenSceneGraph_python)
	target_include_directories(embed PRIVATE "${CMAKE_SOURCE_DIR}/src")
endif()

# pybind11_add_module(osgEarth
# 	"src/osgEarth-python.cpp"
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
