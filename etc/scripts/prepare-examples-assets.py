#!/usr/bin/env python3
"""Prepare the curated openscenegraph-examples third-party payload.

This script deliberately consumes already-pinned source checkouts. CI will
check those sources out at the revisions recorded in examples/assets.toml;
developer mode can point at equivalent local checkouts.
"""

import argparse
import pathlib
import shutil
import subprocess
import sys
import tomllib


def copy_model(source_root, entry, output_root):
	model_source = source_root / entry["path"]
	model_output = output_root / "models" / entry["name"]

	if not (model_source / entry["entrypoint"]).is_file():
		raise FileNotFoundError(f"Model entrypoint does not exist: {model_source / entry['entrypoint']}")

	shutil.copytree(model_source, model_output)


def bake_environment(source_root, entry, output_root, asset_tool, software, quality):
	hdr_path = source_root / entry["path"]
	output = output_root / "env" / entry["name"]
	command = [str(asset_tool), str(hdr_path), str(output)]

	if not hdr_path.is_file():
		raise FileNotFoundError(f"Environment HDR does not exist: {hdr_path}")

	if software:
		command.append("--software")

	for option, value in quality.items():
		if value is not None:
			command.extend((option, str(value)))

	output.parent.mkdir(parents=True, exist_ok=True)
	print("Baking environment:", entry["name"], flush=True)
	subprocess.run(command, check=True)


def write_notices(document, output_root):
	lines = [
		"# Third-Party Asset Notices",
		"",
		"This payload was prepared from the following pinned upstream sources.",
		""
	]

	for name, source in document["sources"].items():
		lines.extend((
			f"## {name}",
			"",
			f"- Repository: {source['repository']}",
			f"- Commit: `{source['commit']}`",
			""
		))

	(output_root / "THIRD_PARTY_NOTICES.md").write_text("\n".join(lines), encoding="utf-8")


def verify_source(name, path, expected_commit):
	result = subprocess.run(
		("git", "-C", str(path), "rev-parse", "HEAD"),
		check=True,
		capture_output=True,
		encoding="utf-8"
	)
	actual_commit = result.stdout.strip()

	if actual_commit != expected_commit:
		raise RuntimeError(
			f"{name} is at {actual_commit}, expected pinned commit {expected_commit}"
		)


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--manifest", type=pathlib.Path, required=True)
	parser.add_argument("--output", type=pathlib.Path, required=True)
	parser.add_argument("--asset-tool", type=pathlib.Path, required=True)
	parser.add_argument("--khronos-environments-dir", type=pathlib.Path, required=True)
	parser.add_argument("--khronos-assets-dir", type=pathlib.Path, required=True)
	parser.add_argument("--software", action="store_true")
	parser.add_argument("--prefilter-size", type=int)
	parser.add_argument("--samples", type=int)
	parser.add_argument("--diffuse-cube-size", type=int)
	parser.add_argument("--diffuse-samples", type=int)
	arguments = parser.parse_args()

	if arguments.output.exists():
		raise RuntimeError(f"Output directory already exists: {arguments.output}")

	if not arguments.asset_tool.is_file():
		raise FileNotFoundError(f"Asset tool does not exist: {arguments.asset_tool}")

	with arguments.manifest.open("rb") as stream:
		document = tomllib.load(stream)

	sources = {
		"khronos_environments": arguments.khronos_environments_dir,
		"khronos_assets": arguments.khronos_assets_dir
	}

	for name, path in sources.items():
		verify_source(name, path, document["sources"][name]["commit"])

	quality = {
		"--prefilter-size": arguments.prefilter_size,
		"--samples": arguments.samples,
		"--diffuse-cube-size": arguments.diffuse_cube_size,
		"--diffuse-samples": arguments.diffuse_samples
	}

	arguments.output.mkdir(parents=True)

	for entry in document.get("environments", []):
		bake_environment(
			sources[entry["source"]],
			entry,
			arguments.output,
			arguments.asset_tool,
			arguments.software,
			quality
		)

	for entry in document.get("models", []):
		copy_model(sources[entry["source"]], entry, arguments.output)

	write_notices(document, arguments.output)


if __name__ == "__main__":
	try:
		main()
	except (FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
		print(f"prepare-examples-assets: {error}", file=sys.stderr)
		sys.exit(1)
