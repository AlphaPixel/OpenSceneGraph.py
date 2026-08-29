#!/usr/bin/env bash
# Reproduce the Linux wheel job locally on the GitHub Actions self-hosted
# runner. Run this as the runner account from a checkout with submodules.
set -euo pipefail

tool_cache="${RUNNER_TOOL_CACHE:-$HOME/githubinstall/_work/_tool}"
venv_dir="${PYOSG_CIBW_VENV:-$HOME/.cache/pyosg-cibuildwheel}"
output_dir="${PYOSG_WHEELHOUSE:-wheelhouse-local}"

if [[ ! -d "$tool_cache/Python" ]]; then

	echo "No GitHub Actions Python tool cache found at: $tool_cache" >&2
	echo "Run this as the self-hosted runner user after setup-python has run." >&2
	exit 1
fi

mapfile -t python_candidates < <(
	find "$tool_cache/Python" \( -type f -o -type l \) -path '*/x64/bin/python' -print | sort -V
)

if [[ ${#python_candidates[@]} -eq 0 ]]; then

	echo "No x64 CPython interpreter found in: $tool_cache/Python" >&2
	exit 1
fi

# cibuildwheel 3.x requires Python 3.11+. The GitHub Action has already
# populated this cache with a compatible interpreter.
python_bin="${python_candidates[${#python_candidates[@]} - 1]}"
python_root="$(cd "$(dirname "$python_bin")/.." && pwd)"

export LD_LIBRARY_PATH="$python_root/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CIBW_BUILD="${CIBW_BUILD:-cp312-manylinux_x86_64}"
export CIBW_ARCHS_LINUX="${CIBW_ARCHS_LINUX:-x86_64}"
export CIBW_MANYLINUX_X86_64_IMAGE="${CIBW_MANYLINUX_X86_64_IMAGE:-manylinux_2_28}"
export CIBW_TEST_COMMAND="${CIBW_TEST_COMMAND:-python -c \"import OpenSceneGraph; registry = OpenSceneGraph.osgDB.Registry.instance(); extensions = ('osg', 'obj', 'stl', 'bmp', 'dds', 'hdr', 'jpeg', 'jpg', 'pnm', 'png', 'rgb', 'tga', 'tif', 'tiff', 'gltf', 'ktx2'); assert all(registry.getReaderWriterForExtension(extension) for extension in extensions); import osgx\"}"

# Match the CI container setup by default. Set PYOSG_CIBW_BEFORE_ALL to override
# it while experimenting with a different plugin/dependency set.
export CIBW_BEFORE_ALL="${PYOSG_CIBW_BEFORE_ALL:-dnf install -y libXrandr-devel libjpeg-turbo-devel libpng-devel libtiff-devel}"

# Do not put cibuildwheel's {dest_dir}/{wheel} placeholders inside Bash's
# ${variable:-default} expansion: its closing brace would terminate that
# expansion early.
if [[ -z "${CIBW_REPAIR_WHEEL_COMMAND:-}" ]]; then
	export CIBW_REPAIR_WHEEL_COMMAND='auditwheel repair -w {dest_dir} {wheel} && python /project/etc/scripts/compact-wheel-libraries.py {dest_dir}'
fi

if [[ ! -x "$venv_dir/bin/cibuildwheel" ]]; then
	"$python_bin" -m venv "$venv_dir"
	"$venv_dir/bin/pip" install 'git+https://github.com/pypa/cibuildwheel.git@v3.4.1'
fi

echo "Using host Python: $python_bin"
echo "Building $CIBW_BUILD with $CIBW_MANYLINUX_X86_64_IMAGE"
"$venv_dir/bin/cibuildwheel" . --output-dir "$output_dir" "$@"
