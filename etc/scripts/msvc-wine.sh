#!/usr/bin/env bash
# Build OpenSceneGraph.py with the local msvc-wine toolchain.
#
# This intentionally defaults to one job: Wine-hosted cl.exe is much more
# reliable in this project when compilation is serialized.

set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../.." && pwd)

msvc_wine_root=${MSVC_WINE_ROOT:-"$HOME/dev/msvc-wine"}
build_dir=${BUILD_DIR:-"$repo_root/BUILD-msvc"}
target=_OpenSceneGraph
jobs=1
log_file=

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Builds the local BUILD-msvc tree with Wine-hosted MSVC and native LLD.

Options:
  -j, --jobs N       Number of simultaneous compiler jobs (default: 1).
  -t, --target NAME  CMake target (default: _OpenSceneGraph).
  -l, --log FILE     Write the complete build log to FILE.
  -h, --help         Show this help.

Environment overrides:
  MSVC_WINE_ROOT     Toolchain location (default: ~/dev/msvc-wine).
  BUILD_DIR          CMake build directory (default: BUILD-msvc).
EOF
}

while (($#)); do
    case $1 in
        -j|--jobs)
            jobs=$2
            shift 2
            ;;
        -t|--target)
            target=$2
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

if [[ ! -f "$build_dir/build.ninja" ]]; then
    echo "No configured Ninja build found at: $build_dir" >&2
    echo "Configure BUILD-msvc first, then rerun this script." >&2
    exit 1
fi

if [[ ! -f "$msvc_wine_root/use-msvc-x64.sh" || ! -f "$msvc_wine_root/msvcenv-native.sh" ]]; then
    echo "msvc-wine toolchain not found at: $msvc_wine_root" >&2
    echo "Set MSVC_WINE_ROOT if it lives elsewhere." >&2
    exit 1
fi

if [[ -z "$log_file" ]]; then
    log_file="$build_dir/msvc-wine-$(date +%Y%m%d-%H%M%S).log"
fi

mkdir -p "$(dirname "$log_file")"

# These scripts set Wine/MSVC executable paths plus INCLUDE and LIB.
source "$msvc_wine_root/use-msvc-x64.sh"
BIN="$msvc_wine_root/.toolchains/msvc/bin/x64" \
    . "$msvc_wine_root/msvcenv-native.sh"

echo "Building target: $target"
echo "Build directory: $build_dir"
echo "Jobs: $jobs"
echo "Log: $log_file"

cmake --build "$build_dir" --target "$target" --parallel "$jobs" 2>&1 | tee "$log_file"
