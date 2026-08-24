#!/usr/bin/env bash
# Assemble and repair a Windows wheel from an already-configured MSVC-on-Wine
# CMake tree.  This deliberately does not run scikit-build-core: the host
# Python would tag a cross-built wheel as Linux.  `wheel pack` gives us a real
# win_amd64 wheel while preserving the CMake install layout used by CI.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$(cd -- "${script_dir}/../.." && pwd)"

build_dir="${BUILD_DIR:-${source_dir}/BUILD-msvc-release}"
output_dir="${OUTPUT_DIR:-${source_dir}/wheelhouse-msvc-wine}"
vcpkg_bin="${VCPKG_BIN_DIR:-${source_dir}/../vcpkg/installed/x64-windows-msvc-wine/bin}"
msvc_redist_bin="${MSVC_REDIST_BIN:-}"
repair=1

usage() {
    cat <<'EOF'
Usage: msvc-wine-wheel.sh [options]

Create a Windows cp312-win_amd64 wheel from an existing MSVC-on-Wine build,
then repair it with delvewheel.

Options:
  -B, --build-dir DIR   CMake build directory (default: BUILD-msvc-release)
  -o, --output-dir DIR  Output directory (default: wheelhouse-msvc-wine)
      --vcpkg-bin DIR   Directory containing vcpkg runtime DLLs
      --msvc-redist-bin DIR
                         Directory containing the MSVC x64 runtime DLLs
      --no-repair       Assemble only; do not invoke delvewheel
  -h, --help            Show this help

The build must already contain a Ninja build.ninja file. Repair mode requires
the host command `python3 -m delvewheel` to be available.
EOF
}

while (($#)); do
    case "$1" in
        -B|--build-dir) build_dir="$2"; shift 2 ;;
        -o|--output-dir) output_dir="$2"; shift 2 ;;
        --vcpkg-bin) vcpkg_bin="$2"; shift 2 ;;
        --msvc-redist-bin) msvc_redist_bin="$2"; shift 2 ;;
        --no-repair) repair=0; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ ! -f "${build_dir}/build.ninja" ]]; then
    echo "No configured Ninja build found at: ${build_dir}" >&2
    exit 2
fi

stage_dir="$(mktemp -d "${TMPDIR:-/tmp}/pyosg-msvc-wheel.XXXXXX")"
trap 'rm -rf -- "$stage_dir"' EXIT
mkdir -p "$output_dir"

project_name="$(sed -nE 's/^name = "([^"]+)"$/\1/p' "${source_dir}/pyproject.toml" | head -n 1)"
project_version="$(sed -nE 's/^version = "([^"]+)"$/\1/p' "${source_dir}/pyproject.toml" | head -n 1)"
if [[ -z "$project_name" || -z "$project_version" ]]; then
    echo "Could not read project name/version from pyproject.toml" >&2
    exit 2
fi
distribution="$(tr '[:upper:]' '[:lower:]' <<<"$project_name" | tr '_' '-')"
dist_info="${distribution}-${project_version}.dist-info"

echo "Installing MSVC build: ${build_dir}"
cmake --install "$build_dir" --prefix "$stage_dir"

# delvewheel's Windows-wheel code normalizes the top-level package directory
# from the distribution name.  On Linux that otherwise disagrees with our
# CamelCase package spelling; Windows itself is case-insensitive.  Keep this
# normalization local to the smoke-wheel harness, never to the CMake install
# rules used by CI.
package_dir="$stage_dir/OpenSceneGraph"
if [[ "$(uname -s)" != "MINGW"* && "$(uname -s)" != "MSYS"* ]]; then
    mv -- "$package_dir" "$stage_dir/openscenegraph"
    package_dir="$stage_dir/openscenegraph"
    while IFS= read -r -d '' path; do
        lower_path="$(dirname -- "$path")/$(basename -- "$path" | tr '[:upper:]' '[:lower:]')"
        [[ "$path" == "$lower_path" ]] || mv -- "$path" "$lower_path"
    done < <(find "$package_dir" -depth -print0)
fi

# The local CMake probe uses the Linux host's extension suffix even though the
# files are PE DLLs.  Generic .pyd is importable by the target Windows CPython.
for extension in "$package_dir"/_openscenegraph*.so "$package_dir"/osgx*.so; do
    [[ -e "$extension" ]] || continue
    mv -- "$extension" "${extension%.so}.pyd"
done

mkdir -p "$stage_dir/$dist_info"
printf 'Metadata-Version: 2.1\nName: %s\nVersion: %s\nSummary: Modern Python bindings for OpenSceneGraph\nRequires-Python: >=3.9\n' \
    "$project_name" "$project_version" > "$stage_dir/$dist_info/METADATA"
printf 'Wheel-Version: 1.0\nGenerator: msvc-wine-wheel.sh\nRoot-Is-Purelib: false\nTag: cp312-cp312-win_amd64\n' \
    > "$stage_dir/$dist_info/WHEEL"

echo "Packing Windows wheel: ${output_dir}"
python3 -m wheel pack --dest-dir "$output_dir" "$stage_dir"
wheel_path="$output_dir/${distribution}-${project_version}-cp312-cp312-win_amd64.whl"
if [[ ! -f "$wheel_path" ]]; then
    wheel_path="$(find "$output_dir" -maxdepth 1 -type f -name '*-win_amd64.whl' -print -quit)"
fi
if [[ -z "$wheel_path" || ! -f "$wheel_path" ]]; then
    echo "wheel pack did not create a Windows wheel" >&2
    exit 1
fi

if (( ! repair )); then
    echo "Assembled wheel: $wheel_path"
    exit 0
fi

if ! python3 -c 'import delvewheel' 2>/dev/null; then
    echo "delvewheel is not installed for python3." >&2
    echo "Make python3 -m delvewheel available, then rerun this script." >&2
    exit 2
fi
if [[ ! -d "$vcpkg_bin" ]]; then
    echo "vcpkg runtime DLL directory does not exist: $vcpkg_bin" >&2
    exit 2
fi

if [[ -z "$msvc_redist_bin" ]]; then
    msvc_redist_bin="$(find "${source_dir}/../msvc-wine/.toolchains/msvc/VC/Redist/MSVC" \
        -type d -path '*/x64/Microsoft.VC*.CRT' -print -quit 2>/dev/null || true)"
fi

repair_paths="$vcpkg_bin"
if [[ -n "$msvc_redist_bin" && -d "$msvc_redist_bin" ]]; then
    repair_paths+=":$msvc_redist_bin"
else
    echo "Warning: MSVC runtime DLL directory was not found; set MSVC_REDIST_BIN if needed." >&2
fi

repaired_dir="$output_dir/repaired"
mkdir -p "$repaired_dir"
echo "Repairing wheel with delvewheel"
python3 -m delvewheel repair --ignore-existing --analyze-existing --add-path "$repair_paths" -w "$repaired_dir" "$wheel_path"
echo "Repaired wheel: $(find "$repaired_dir" -maxdepth 1 -type f -name '*.whl' -print -quit)"
