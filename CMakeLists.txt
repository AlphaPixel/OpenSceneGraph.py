cmake_minimum_required(VERSION 3.15)

project(OpenSceneGraph-python LANGUAGES C CXX)

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
# find_package(pybind11 REQUIRED)
add_subdirectory("etc/pybind11")

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

find_package(OpenSceneGraph REQUIRED
	osg
	osgUtil
	osgDB
	osgGA
	osgViewer
	# osgUtil
	# osgText
)

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
	"pyosg/pyosgUtil.cpp"
	"pyosg/pyosgDB.cpp"
	"pyosg/pyosgGA.cpp"
	"pyosg/pyosgViewer.cpp"
)

add_library(OpenSceneGraph_python STATIC ${PYOSG_SOURCES})

target_link_libraries(OpenSceneGraph_python PRIVATE
	Python3::Python
	pybind11::module
	${OPENSCENEGRAPH_LIBRARIES}
)

target_compile_features(OpenSceneGraph_python PUBLIC cxx_std_20)
target_compile_options(OpenSceneGraph_python PRIVATE ${PYOSG_COMPILE_OPTIONS})
target_include_directories(OpenSceneGraph_python PUBLIC
	# TODO: This is currently a hack to ensure `pybind11x.hpp` is found! In the
	# future, it will come in as another submodule!
	"${CMAKE_SOURCE_DIR}/etc"
	${OPENSCENEGRAPH_INCLUDE_DIRS}
)
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

else()
	add_executable(embed
		"pyosg/OpenSceneGraph-python.cpp"
		"etc/embed.cpp"
	)

	target_compile_definitions(embed PRIVATE PYOSG_EMBEDDED=1)
	target_link_libraries(embed PRIVATE pybind11::embed OpenSceneGraph_python)
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
