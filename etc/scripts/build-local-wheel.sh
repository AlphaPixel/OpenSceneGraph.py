#!/usr/bin/env bash
# Build the native HDR-preparation tool and one local base wheel without Docker
# or cibuildwheel. This is a developer/release-preparation path, not a
# substitute for the repaired manylinux wheels produced by CI.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

scratch="${PYOSG_SCRATCH:-/home/cubicool/tmp/pyosg}"
native_dir="$scratch/native"
wheelhouse="${PYOSG_WHEELHOUSE:-$scratch/wheelhouse}"
osgx_source="${PYOSG_OSGX_SOURCE_DIR:-$repo_root/etc/osgx}"
python_bin="${PYTHON:-python3}"
hdr_input="${PYOSG_HDR:-}"
asset_name="${PYOSG_ASSET_NAME:-}"
software_bake="${PYOSG_PBRIBL_SOFTWARE:-0}"
prepare_catalog_assets="${PYOSG_PREPARE_CATALOG_ASSETS:-0}"
catalog_asset_dir="${PYOSG_CATALOG_ASSET_DIR:-$scratch/catalog-assets}"
khronos_environments_dir="${PYOSG_KHRONOS_ENVIRONMENTS_DIR:-/home/cubicool/dev/OpenSceneGraph-Data/glTF-Sample-Environments}"
khronos_assets_dir="${PYOSG_KHRONOS_ASSETS_DIR:-/home/cubicool/dev/OpenSceneGraph-Data/glTF-Sample-Assets}"
pbribl_prefilter_size="${PYOSG_PBRIBL_PREFILTER_SIZE:-}"
pbribl_samples="${PYOSG_PBRIBL_SAMPLES:-}"
pbribl_diffuse_cube_size="${PYOSG_PBRIBL_DIFFUSE_CUBE_SIZE:-}"
pbribl_diffuse_samples="${PYOSG_PBRIBL_DIFFUSE_SAMPLES:-}"
build_base_wheel="${PYOSG_BUILD_BASE_WHEEL:-1}"
build_examples_wheel="${PYOSG_BUILD_EXAMPLES_WHEEL:-0}"
examples_asset_dir="${PYOSG_EXAMPLES_ASSET_DIR:-}"

if [[ ! -f "$osgx_source/CMakeLists.txt" ]]; then
	echo "osgx source directory is not configured: $osgx_source" >&2
	echo "Set PYOSG_OSGX_SOURCE_DIR to a valid osgx checkout." >&2
	exit 1
fi

if [[ "$software_bake" != "0" && "$software_bake" != "1" ]]; then
	echo "PYOSG_PBRIBL_SOFTWARE must be 0 or 1." >&2
	exit 1
fi

if [[ "$prepare_catalog_assets" != "0" && "$prepare_catalog_assets" != "1" ]]; then
	echo "PYOSG_PREPARE_CATALOG_ASSETS must be 0 or 1." >&2
	exit 1
fi

if [[ "$prepare_catalog_assets" == "1" && -n "$hdr_input" ]]; then
	echo "Use either PYOSG_PREPARE_CATALOG_ASSETS or PYOSG_HDR, not both." >&2
	exit 1
fi

mkdir -p "$native_dir" "$wheelhouse"

# This independent native build provides osgx-pbribl for preparing selected
# third-party assets. It is deliberately retained between invocations so CMake
# and the pinned OSG checkout can be reused.
cmake -S "$repo_root" -B "$native_dir" \
	-DPYOSG_FETCH_OSG=ON \
	-DPYOSG_OSGX_SOURCE_DIR="$osgx_source" \
	-DPYOSG_BUILD_OSGX_UTILS=ON \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_POLICY_VERSION_MINIMUM=3.5

cmake --build "$native_dir" \
	--target osgx-pbribl osgdb_hdr osgdb_ktx2 \
	--parallel "$(nproc)"

asset_tool="$native_dir/_deps/osgx-build/utils/osgx-pbribl"

shopt -s nullglob
osg_plugin_dirs=("$native_dir"/_deps/openscenegraph-build/lib/osgPlugins-*)
shopt -u nullglob

if [[ ${#osg_plugin_dirs[@]} -ne 1 ]]; then
	echo "Could not identify the OSG build-tree plugin directory." >&2
	exit 1
fi

osg_plugin_dir="${osg_plugin_dirs[0]}"
ktx2_plugin_dir="$native_dir/_deps/osgx-build/plugins/ktx2"

if [[ ! -f "$osg_plugin_dir/osgdb_hdr.so" ]]; then
	echo "HDR reader plugin was not built: $osg_plugin_dir/osgdb_hdr.so" >&2
	exit 1
fi

if [[ ! -f "$ktx2_plugin_dir/osgdb_ktx2.so" ]]; then
	echo "KTX2 writer plugin was not built: $ktx2_plugin_dir/osgdb_ktx2.so" >&2
	exit 1
fi

echo "Prepared asset tool: $asset_tool"

if [[ "$prepare_catalog_assets" == "1" ]]; then
	prepare_args=(
		--manifest "$repo_root/examples/assets.toml"
		--output "$catalog_asset_dir"
		--asset-tool "$asset_tool"
		--khronos-environments-dir "$khronos_environments_dir"
		--khronos-assets-dir "$khronos_assets_dir"
	)

	if [[ "$software_bake" == "1" ]]; then
		prepare_args+=(--software)
	fi

	if [[ -n "$pbribl_prefilter_size" ]]; then
		prepare_args+=(--prefilter-size "$pbribl_prefilter_size")
	fi

	if [[ -n "$pbribl_samples" ]]; then
		prepare_args+=(--samples "$pbribl_samples")
	fi

	if [[ -n "$pbribl_diffuse_cube_size" ]]; then
		prepare_args+=(--diffuse-cube-size "$pbribl_diffuse_cube_size")
	fi

	if [[ -n "$pbribl_diffuse_samples" ]]; then
		prepare_args+=(--diffuse-samples "$pbribl_diffuse_samples")
	fi

	# Catalog preparation requires a new staging directory. This prevents stale,
	# unlisted files from entering the examples wheel.
	OSG_LIBRARY_PATH="$osg_plugin_dir:$ktx2_plugin_dir${OSG_LIBRARY_PATH:+:$OSG_LIBRARY_PATH}" \
		"$python_bin" "$repo_root/etc/scripts/prepare-examples-assets.py" "${prepare_args[@]}"

	echo "Prepared catalog assets: $catalog_asset_dir"
	examples_asset_dir="$catalog_asset_dir"
fi

if [[ -n "$hdr_input" ]]; then
	if [[ ! -f "$hdr_input" ]]; then
		echo "HDR input does not exist: $hdr_input" >&2
		exit 1
	fi

	if [[ -z "$asset_name" ]]; then
		asset_name="$(basename "${hdr_input%.*}")"
	fi

	asset_output="$scratch/assets/env/$asset_name"
	mkdir -p "$(dirname "$asset_output")"
	pbribl_args=()

	if [[ "$software_bake" == "1" ]]; then
		pbribl_args+=(--software)
	fi

	# osgx-pbribl uses osgDB::readImageFile(), whose HDR reader is an OSG
	# plugin. This build-tree path is the local equivalent of an installed OSG
	# plugin directory; do not require a system-wide `make install`. Setting
	# PYOSG_PBRIBL_SOFTWARE=1 selects the CPU/OpenMP baker for headless CI.
	OSG_LIBRARY_PATH="$osg_plugin_dir:$ktx2_plugin_dir${OSG_LIBRARY_PATH:+:$OSG_LIBRARY_PATH}" \
		"$asset_tool" "$hdr_input" "$asset_output" "${pbribl_args[@]}"

	echo "Prepared environment: $asset_output.gltf"
	examples_asset_dir="$scratch/assets"
fi

if [[ "$build_base_wheel" != "0" ]]; then
	# scikit-build-core creates its own temporary CMake build for wheel assembly.
	# Keep the osgx source override and the root wheel's pinned-OSG policy explicit
	# so this local wheel follows the same dependency graph as CI. Do not enable
	# OSGX_BUILD_UTILS here: the released base wheel does not ship developer tools.
	wheel_cmake_args="${CMAKE_ARGS:-}"
	wheel_cmake_args+=" -DPYOSG_FETCH_OSG=ON"
	wheel_cmake_args+=" -DPYOSG_OSGX_SOURCE_DIR=$osgx_source"
	wheel_cmake_args+=" -DCMAKE_POLICY_VERSION_MINIMUM=3.5"

	CMAKE_ARGS="$wheel_cmake_args" \
		"$python_bin" -m build "$repo_root" --wheel --outdir "$wheelhouse"
fi

if [[ "$build_examples_wheel" != "0" ]]; then
	if [[ -z "$examples_asset_dir" || ! -d "$examples_asset_dir" ]]; then
		echo "Set PYOSG_EXAMPLES_ASSET_DIR to a prepared asset directory." >&2
		exit 1
	fi

	CMAKE_ARGS="-DPYOSG_EXAMPLES_ASSET_DIR=$examples_asset_dir" \
		"$python_bin" -m build "$repo_root/examples" --wheel --outdir "$wheelhouse"
fi

echo "Local wheelhouse: $wheelhouse"
find "$wheelhouse" -maxdepth 1 -type f -name '*.whl' -printf '  %f\n' | sort
