#!/usr/bin/env bash
# Configure OpenSceneGraph.py for a local Wine-hosted MSVC build.
#
# Run this once for a new BUILD-msvc tree, or pass --clean for a from-scratch,
# CI-like configuration.  Use msvc-wine.sh afterwards to perform the build.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)

msvc_wine_root=${MSVC_WINE_ROOT:-"$HOME/dev/msvc-wine"}
vcpkg_root=${VCPKG_ROOT:-"$HOME/dev/vcpkg"}
build_dir=${BUILD_DIR:-"$repo_root/BUILD-msvc"}
osgx_source=${PYOSG_OSGX_SOURCE_DIR:-"$repo_root/../osgx"}
overlay_triplets=${VCPKG_OVERLAY_TRIPLETS:-/tmp/msvc-wine-vcpkg-triplets}
python_executable=${PYTHON3_EXECUTABLE:-/usr/bin/python3}
build_type=${PYOSG_MSVC_BUILD_TYPE:-Debug}
clean=false
log_file=

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Configures a Ninja build using Wine-hosted MSVC, native LLD, local vcpkg, and
the sibling osgx developer checkout.  It does not compile; run msvc-wine.sh
afterwards.

Options:
  --clean                 Remove the generated build directory first.
  -B, --build-dir DIR     Build directory (default: BUILD-msvc).
  --build-type TYPE       CMake build type (default: Debug).
  --osgx-source DIR       osgx source checkout (default: ../osgx).
  -l, --log FILE          Save configure output to FILE as well as the terminal.
  -h, --help              Show this help.

Environment overrides:
  MSVC_WINE_ROOT          Toolchain location (default: ~/dev/msvc-wine).
  VCPKG_ROOT              vcpkg checkout (default: ~/dev/vcpkg).
  BUILD_DIR               Build directory (default: BUILD-msvc).
  PYOSG_MSVC_BUILD_TYPE   CMake build type (default: Debug).
  PYOSG_OSGX_SOURCE_DIR   osgx checkout (default: ../osgx).
  VCPKG_OVERLAY_TRIPLETS  vcpkg triplet overlay (default: /tmp/msvc-wine-vcpkg-triplets).
  PYTHON3_EXECUTABLE      Host Python used by CMake (default: /usr/bin/python3).
EOF
}

while (($#)); do
    case $1 in
        --clean)
            clean=true
            shift
            ;;
        -B|--build-dir)
            build_dir=$2
            shift 2
            ;;
        --build-type)
            build_type=$2
            shift 2
            ;;
        --osgx-source)
            osgx_source=$2
            shift 2
            ;;
        -l|--log)
            log_file=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case $build_type in
    Debug|Release|RelWithDebInfo|MinSizeRel) ;;
    *)
        echo "Unsupported CMake build type: $build_type" >&2
        exit 2
        ;;
esac

for required_file in \
    "$msvc_wine_root/use-msvc-x64.sh" \
    "$msvc_wine_root/msvcenv-native.sh" \
    "$msvc_wine_root/msvc-wine-x64.cmake" \
    "$vcpkg_root/scripts/buildsystems/vcpkg.cmake" \
    "$osgx_source/CMakeLists.txt"; do
    if [[ ! -f "$required_file" ]]; then
        echo "Required file not found: $required_file" >&2
        exit 1
    fi
done

if [[ ! -d "$overlay_triplets" ]]; then
    echo "vcpkg triplet overlay not found: $overlay_triplets" >&2
    exit 1
fi

if $clean; then
    # Only remove an explicit generated subdirectory, never the source tree.
    build_dir_abs=$(realpath -m "$build_dir")
    repo_root_abs=$(realpath "$repo_root")
    if [[ "$build_dir_abs" == / || "$build_dir_abs" == "$repo_root_abs" ]]; then
        echo "Refusing to remove unsafe build directory: $build_dir_abs" >&2
        exit 1
    fi
    echo "Removing generated build directory: $build_dir_abs"
    rm -rf -- "$build_dir_abs"
fi

if [[ -n "$log_file" ]]; then
    mkdir -p "$(dirname "$log_file")"
fi

source "$msvc_wine_root/use-msvc-x64.sh"
BIN="$msvc_wine_root/.toolchains/msvc/bin/x64" \
    . "$msvc_wine_root/msvcenv-native.sh"
unset CC CXX RC

cmake_args=(
    -S "$repo_root"
    -B "$build_dir"
    -G Ninja
    "-DCMAKE_BUILD_TYPE=$build_type"
    "-DCMAKE_TOOLCHAIN_FILE=$vcpkg_root/scripts/buildsystems/vcpkg.cmake"
    -DVCPKG_TARGET_TRIPLET=x64-windows-msvc-wine
    "-DVCPKG_OVERLAY_TRIPLETS=$overlay_triplets"
    "-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE=$msvc_wine_root/msvc-wine-x64.cmake"
    "-DVCPKG_INSTALLED_DIR=$vcpkg_root/installed"
    -DVCPKG_APPLOCAL_DEPS=OFF
    -DPYOSG_FETCH_OSG=ON
    -DPYOSG_BUILD_OSGX=ON
    "-DPYOSG_OSGX_SOURCE_DIR=$osgx_source"
    # OpenThreads checks that the Win32 Interlocked operations can be run.
    # In a cross build CMake can compile, but cannot execute, the PE probe.
    # The native MSVC/Wine build already established that this test succeeds.
    -D_OPENTHREADS_ATOMIC_USE_WIN32_INTERLOCKED_EXITCODE:STRING=0
    "-DPython3_EXECUTABLE=$python_executable"
    "-DPython3_INCLUDE_DIR=$msvc_wine_root/.toolchains/python312/include"
    "-DPython3_LIBRARY=$msvc_wine_root/.toolchains/python312/libs/python312.lib"
)

echo "Configuring MSVC-on-Wine build"
echo "Source: $repo_root"
echo "Build directory: $build_dir"
echo "Build type: $build_type"
echo "osgx source: $osgx_source"

if [[ -n "$log_file" ]]; then
    echo "Log: $log_file"
    cmake "${cmake_args[@]}" 2>&1 | tee "$log_file"
else
    cmake "${cmake_args[@]}"
fi
