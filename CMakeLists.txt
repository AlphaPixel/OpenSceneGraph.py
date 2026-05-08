cmake_minimum_required(VERSION 3.15)

project(
  ${SKBUILD_PROJECT_NAME}
  VERSION ${SKBUILD_PROJECT_VERSION}
  LANGUAGES C CXX)

option(PYOSG_EMBEDDED "Build OpenSceneGraph bindings for embedding" OFF)

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)
find_package(pybind11 CONFIG REQUIRED)
find_package(
  OpenSceneGraph
  REQUIRED
  osg
  osgUtil
  osgDB
  osgGA
  osgViewer
  # osgUtil osgText
)

if(WIN32)
  set(PYOSG_COMPILE_OPTIONS
      "/W4" "/WX" "/wd4100" "/analyze"
      # "/wd4225" "/wd4244" "/wd4668" "/wd4146" "/wd4267" "/wd4996" "/wd4334"
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
        "-Wno-unused-parameter")
  else(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    set(PYOSG_COMPILE_OPTIONS
        "-W"
        "-Wall"
        "-Wshadow"
        "-Wsign-conversion"
        "-Wpedantic"
        "-Werror"
        "-Wno-unused-parameter")
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
    "src/pyosgViewer.cpp")

add_library(OpenSceneGraph_python STATIC ${PYOSG_SOURCES})

target_link_libraries(
  OpenSceneGraph_python PUBLIC Python3::Python pybind11::module
                               ${OPENSCENEGRAPH_LIBRARIES})
target_compile_features(OpenSceneGraph_python PUBLIC cxx_std_20)
target_compile_options(OpenSceneGraph_python PRIVATE ${PYOSG_COMPILE_OPTIONS})
set_property(TARGET OpenSceneGraph_python PROPERTY POSITION_INDEPENDENT_CODE ON)

if(NOT PYOSG_EMBEDDED)
  python3_add_library(openscenegraph WITH_SOABI MODULE
                      "src/OpenSceneGraph-python.cpp")

  target_link_libraries(openscenegraph PUBLIC OpenSceneGraph_python)
else()
  add_executable(embed "src/OpenSceneGraph-python.cpp" "etc/embed.cpp")

  target_compile_definitions(embed PRIVATE PYOSG_EMBEDDED=1)
  target_link_libraries(embed PRIVATE OpenSceneGraph_python)
  target_include_directories(embed PRIVATE "${CMAKE_SOURCE_DIR}/src")
endif()

install(TARGETS openscenegraph LIBRARY DESTINATION ${SKBUILD_PROJECT_NAME})
