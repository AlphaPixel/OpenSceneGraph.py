cmake_minimum_required(VERSION 3.17)

project(
    ${SKBUILD_PROJECT_NAME}
    VERSION ${SKBUILD_PROJECT_VERSION}
    LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -pthread")
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)

# Generate compile_commands.json to make tree-sitter happy.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON CACHE INTERNAL "")
if(CMAKE_EXPORT_COMPILE_COMMANDS)
  set(CMAKE_CXX_STANDARD_INCLUDE_DIRECTORIES
      ${CMAKE_CXX_IMPLICIT_INCLUDE_DIRECTORIES})
endif()

# By default build the release version with O3
if (NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "-O3")

message(STATUS "Using compiler ${CMAKE_CXX_COMPILER_ID} ...")

include(CMakeDependentOption)           # This is a really useful scripts that creates options that depends on other options. It can even be used with generator expressions !
include(GNUInstallDirs)                 # This will define the default values for installation directories (all platforms even if named GNU)
include(InstallRequiredSystemLibraries) # Tell CMake that the `install` target needs to install required system libraries (eg: Windows SDK)
include(CMakePackageConfigHelpers)      # Helper to create relocatable packages

# +----------------------------------------+
# | Options                                |
# +----------------------------------------+

option(PYOSG_ENABLE_TEST "Should ${PROJECT_NAME} build the unit tests" ON)
option(PYOSG_EMBEDDED "Build OpenSceneGraph bindings for embedding" OFF)

# +----------------------------------------+
# | Dependencies                           |
# +----------------------------------------+

if(PYOSG_ENABLE_TEST)
    include(GoogleTest)
    find_package(GTest REQUIRED)
    enable_testing()
endif()

find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)
find_package(spdlog REQUIRED)
find_package(OpenSceneGraph REQUIRED
    osg
	osgUtil
	osgDB
	osgGA
	osgViewer
)

#############################################################
# Targets                                                   #
#############################################################
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

set(PYOSG_SOURCES
	"src/pyosg.cpp"
	"src/osg/ArgumentParser.cpp"
	"src/osg/Notify.cpp"
	"src/osg/Vec.cpp"
	"src/osg/Quat.cpp"
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
	"src/pyosgUtil.cpp"
	"src/pyosgDB.cpp"
	"src/pyosgGA.cpp"
	"src/pyosgViewer.cpp"
)
add_library(OpenSceneGraph_python STATIC ${PYOSG_SOURCES})

target_link_libraries(OpenSceneGraph_python PRIVATE
	Python3::Python
	pybind11::headers
	${OPENSCENEGRAPH_LIBRARIES}
)
target_compile_features(OpenSceneGraph_python PUBLIC cxx_std_20)
target_compile_options(OpenSceneGraph_python PRIVATE ${PYOSG_COMPILE_OPTIONS})
target_include_directories(OpenSceneGraph_python PUBLIC
	"${CMAKE_SOURCE_DIR}/etc"
	${OPENSCENEGRAPH_INCLUDE_DIRS}
)

if(NOT PYOSG_EMBEDDED)
	pybind11_add_module(${SKBUILD_PROJECT_NAME} "src/OpenSceneGraph-python.cpp")
	target_link_libraries(${SKBUILD_PROJECT_NAME} PRIVATE OpenSceneGraph_python)

    install(TARGETS ${SKBUILD_PROJECT_NAME} LIBRARY DESTINATION "${CMAKE_INSTALL_PREFIX}")
else()
	add_executable(embed
		"src/OpenSceneGraph-python.cpp"
		"etc/embed.cpp"
	)

	target_compile_definitions(embed PRIVATE PYOSG_EMBEDDED=1)
	target_link_libraries(embed PRIVATE pybind11::embed OpenSceneGraph_python)
	target_include_directories(embed PRIVATE "${CMAKE_SOURCE_DIR}/src")
endif()
