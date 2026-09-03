#!/usr/bin/env python3
"""Drive the Blender-exported G1 glTF proxy with NVIDIA MotionBricks in OSG.py.

This deliberately keeps the bridge simple: MotionBricks produces G1 MuJoCo-``qpos``-
shaped values on CUDA, this script applies its 29 hinge angles to the glTF armature's
named MatrixTransforms, and osgGLTF performs its usual GPU skinning. The real
``mujoco`` package is never imported: MotionBricks' demo plumbing only ever reads a
few scalar fields off its MjModel/MjData pair, so those are stubbed out and the 29
hinge joints are discovered by parsing the G1 MJCF skeleton XML directly.

Run from the MotionBricks virtual environment, for example::

	PYTHONPATH=~/tmp/GR00T-WholeBodyControl/motionbricks:~/local/lib/python3.12/site-packages:~/dev/OpenSceneGraph.py/BUILD-g++-13.3.0-NOASAN:~/dev/osgx/BUILD-g++-13.3.0-NOASAN \\
	LD_LIBRARY_PATH=~/dev/osgx/BUILD-g++-13.3.0-NOASAN \\
	~/tmp/GR00T-WholeBodyControl/.venv-motionbricks/bin/python \\
	~/dev/OpenSceneGraph.py/examples/pyosg-motionbricks.py

W/A/S/D selects walking direction. Hold V, Z, X, B, R, T, C, E, F, G, or Q to
select the corresponding MotionBricks locomotion style. Unlike the MuJoCo demo,
these keys are handled by the OSG window, so they do not trigger MuJoCo shortcuts.
"""

import argparse
import math
import os
import pathlib
import sys
import time
import types
import xml.etree.ElementTree as ET
from types import SimpleNamespace

import numpy as np
import torch

os.environ.setdefault("OSG_WINDOW", "50 50 1420 933")
os.environ.setdefault(
	"OSG_LIBRARY_PATH", ":".join((
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/ktx2",
		"/home/cubicool/dev/osgx/BUILD-g++-13.3.0-NOASAN/plugins/gltf"
	))
)

# Import side effect: fills in OSG_THREADING/OSG_GL_* env var defaults (see pyosg_example.py).
# Deliberately after the OSG_WINDOW/OSG_LIBRARY_PATH overrides above (setdefault() means order
# between these doesn't actually matter, but matching pyosg-khronos-viewer.py's style) and before
# `from OpenSceneGraph import *` -- these need to land before OSG's DisplaySettings reads them.
from pyosg_example import window_size

from OpenSceneGraph import *

# MotionBricks' demo utilities only touch the real MuJoCo package for two things
# this script doesn't need: building a full MjModel/MjData pair, and a module-level
# `import mujoco` used purely for type hints (WASD_controller.generate_control_signals
# only ever reads mj_data.qpos and mj_model.nq/opt.timestep, never real forward
# kinematics). Stub the module and its model/data builder so `mujoco` itself is not
# a runtime dependency of this example.
sys.modules.setdefault("mujoco", types.ModuleType("mujoco")).__dict__.update(
	MjModel=object, MjData=object
)

from motionbricks.motion_backbone.demo import utils as motionbricks_demo_utils

navigation_demo = motionbricks_demo_utils.navigation_demo

def dummy_mj_simulator(humanoid_xml, fps=30):
	"""Stand in for MotionBricks' build_mj_simulator() with the bare fields
	WASD_controller.generate_control_signals() actually reads."""

	return (
		SimpleNamespace(nq=36, opt=SimpleNamespace(timestep=1.0 / fps)),
		SimpleNamespace(qpos=np.zeros(36))
	)

motionbricks_demo_utils.build_mj_simulator = dummy_mj_simulator

THIS_DIR = pathlib.Path(__file__).resolve().parent
DEFAULT_MOTIONBRICKS_ROOT = pathlib.Path.home() / "tmp" / "GR00T-WholeBodyControl" / "motionbricks"
DEFAULT_MODEL = pathlib.Path.home() / "tmp" / "3dmodels" / "g1stick" / "g1stick.gltf"
CLEAR_COLOR = (0.012, 0.014, 0.020, 1.0)
CONTROL_KEYS = "wasdvzxb rtcefgq".replace(" ", "")

SKINNING_VERTEX_SHADER = """
#version 460 core

in vec4 osg_Vertex;
in vec3 osg_Normal;
layout(location = 8) in uvec4 osgx_gltf_JointIndices;
layout(location = 9) in vec4 osgx_gltf_JointWeights;

layout(std430, binding = 2) readonly buffer osgx_gltf_JointMatrixBuffer {
	mat4 osgx_gltf_jointMatrices[];
};

uniform mat4 osg_ModelViewProjectionMatrix;
uniform mat4 osg_ModelViewMatrix;
uniform mat3 osg_NormalMatrix;

out vec3 vNormal;
out vec3 vPosition;

void main() {
	mat4 skin =
		osgx_gltf_JointWeights.x * osgx_gltf_jointMatrices[osgx_gltf_JointIndices.x] +
		osgx_gltf_JointWeights.y * osgx_gltf_jointMatrices[osgx_gltf_JointIndices.y] +
		osgx_gltf_JointWeights.z * osgx_gltf_jointMatrices[osgx_gltf_JointIndices.z] +
		osgx_gltf_JointWeights.w * osgx_gltf_jointMatrices[osgx_gltf_JointIndices.w]
	;

	vec4 localVertex = skin * osg_Vertex;

	vPosition = (osg_ModelViewMatrix * localVertex).xyz;
	vNormal = normalize(osg_NormalMatrix * mat3(skin) * osg_Normal);
	gl_Position = osg_ModelViewProjectionMatrix * localVertex;
}
"""

SKINNING_FRAGMENT_SHADER = """
#version 460 core

in vec3 vNormal;
in vec3 vPosition;

out vec4 fragColor;

void main() {
	vec3 normal = normalize(vNormal);
	vec3 lightDirection = normalize(vec3(0.4, 0.7, 1.0));
	float diffuse = 0.25 + 0.75 * max(dot(normal, lightDirection), 0.0);
	fragColor = vec4(vec3(0.85, 0.9, 1.0) * diffuse, 1.0);
}
"""

def collect_matrix_transforms(node, transforms):
	"""Collect named MatrixTransforms from an osgGLTF-loaded hierarchy."""

	if hasattr(node, "matrix") and node.name:
		if node.name in transforms:
			raise RuntimeError(f"duplicate transform name in glTF: {node.name!r}")

		transforms[node.name] = node

	if hasattr(node, "children"):
		for child in node.children:
			collect_matrix_transforms(child, transforms)

def parse_mjcf_hinge_joints(skeleton_xml):
	"""Return [(joint_name, qpos_address), ...] for a G1-style MJCF skeleton.

	Mirrors motionbricks' own worldbody joint walk (motionbricks/helper/mujoco_helper.py),
	which is also how MotionBricks derives its mujoco_qpos joint order: the root
	<freejoint> occupies qpos[0:7], then every <joint> under <worldbody> follows in
	document order, one qpos slot each.
	"""

	worldbody = ET.parse(skeleton_xml).getroot().find("worldbody")

	return [
		(joint.get("name"), 7 + index)
		for index, joint in enumerate(worldbody.findall(".//joint"))
	]

def install_skinning_shader(model):
	"""Use the known-good Python skinning path without changing osgx's PBR helper."""

	program = osg.Program(name="motionbricks_skinning", shaders=(
		osg.Shader(osg.Shader.VERTEX, SKINNING_VERTEX_SHADER),
		osg.Shader(osg.Shader.FRAGMENT, SKINNING_FRAGMENT_SHADER)
	))

	state_set = model.stateSet
	state_set.attributes[osg.StateAttribute.PROGRAM] = (
		program,
		osg.StateAttribute.ON | osg.StateAttribute.OVERRIDE | osg.StateAttribute.PROTECTED
	)

def matrix_from_quaternion(quaternion):
	"""Return an OSG row-vector rotation Matrix from a MuJoCo WXYZ quaternion."""

	w, x, y, z = quaternion
	xx, yy, zz = x * x, y * y, z * z
	xy, xz, yz = x * y, x * z, y * z
	wx, wy, wz = w * x, w * y, w * z

	# This is the transpose of the conventional column-vector matrix because OSG
	# stores transforms in its row-vector convention.
	return osg.Matrix(
		1.0 - 2.0 * (yy + zz), 2.0 * (xy + wz), 2.0 * (xz - wy), 0.0,
		2.0 * (xy - wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz + wx), 0.0,
		2.0 * (xz + wy), 2.0 * (yz - wx), 1.0 - 2.0 * (xx + yy), 0.0,
		0.0, 0.0, 0.0, 1.0
	)

def quaternion_multiply(left, right):
	"""Multiply WXYZ quaternions."""

	lw, lx, ly, lz = left
	rw, rx, ry, rz = right

	return (
		lw * rw - lx * rx - ly * ry - lz * rz,
		lw * rx + lx * rw + ly * rz - lz * ry,
		lw * ry - lx * rz + ly * rw + lz * rx,
		lw * rz + lx * ry - ly * rx + lz * rw
	)

def relative_quaternion(current, reference):
	"""Return the rotation taking reference WXYZ orientation to current."""

	# Plain indexing works whether `reference` itself is a numpy array, a torch tensor
	# (both from MotionBricks -- see qpos/reference_qpos), or a plain tuple; only the
	# .copy()+slice-assignment numpy idiom this replaced actually required an array type.
	conjugate = (reference[0], -reference[1], -reference[2], -reference[3])

	return quaternion_multiply(current, conjugate)

class OSGKeyboard(osgGA.GUIEventHandler):
	"""Keep MotionBricks' controller state in the OSG event loop."""

	def __init__(self):
		super().__init__()

		self.keys = dict.fromkeys(CONTROL_KEYS, False)

	def handle(self, event, action):
		if event.type not in (osgGA.GUIEventAdapter.KEYDOWN, osgGA.GUIEventAdapter.KEYUP):
			return False

		key = event.key

		if not isinstance(key, int) or key < 0 or key > 255:
			return False

		key = chr(key).lower()

		if key not in self.keys:
			return False

		self.keys[key] = event.type == osgGA.GUIEventAdapter.KEYDOWN

		return False

class MotionBricksDriver:
	"""Advance the stock NVIDIA agent and copy its qpos to the glTF armature."""

	def __init__(self, demo_agent, model, model_root, keyboard, debug_joint=None, debug_angle=0.0):
		self.demo_agent = demo_agent
		self.model_root = model_root
		self.keyboard = keyboard
		self.camera = SimpleNamespace(
			cam=SimpleNamespace(
				lookat=np.zeros(3), distance=4.0, azimuth=-130.0, elevation=-20.0
			)
		)
		self.transforms = {}
		self.rest_matrices = {}
		self.joints = []
		self.reference_qpos = None
		self.next_step = 0.0
		self.step_seconds = demo_agent.mj_model.opt.timestep
		self.debug_joint = debug_joint
		self.debug_angle = debug_angle

		collect_matrix_transforms(model, self.transforms)

		for joint_name, qpos_address in parse_mjcf_hinge_joints(demo_agent.args.skeleton_xml):
			transform = self.transforms.get(joint_name)

			if transform is None:
				raise RuntimeError(f"glTF is missing MotionBricks joint {joint_name!r}")

			self.joints.append((joint_name, qpos_address, transform))
			# MatrixTransform.matrix returns a live C++ reference in pyosg. Keep an
			# independent value: otherwise every later setMatrix() mutates the
			# supposed rest pose and the angle compounds once per update.
			self.rest_matrices[joint_name] = osg.Matrix(transform.matrix)

		if len(self.joints) != 29:
			raise RuntimeError(f"expected 29 G1 hinge joints, found {len(self.joints)}")

		if self.debug_joint is not None and self.debug_joint not in self.rest_matrices:
			raise RuntimeError(f"unknown G1 debug joint {self.debug_joint!r}")

		print(f"[MotionBricks] mapped {len(self.joints)} MuJoCo joints to glTF MatrixTransforms")

	def advance(self):
		now = time.perf_counter()

		if now < self.next_step:
			return

		# Avoid unbounded catch-up inference after an interactive pause.
		self.next_step = now + self.step_seconds
		qpos = self.demo_agent.full_agent.get_next_frame().copy()
		context_motion_features = self.demo_agent.full_agent.get_context_motion_features()
		context_mujoco_qpos = self.demo_agent.full_agent.get_context_mujoco_qpos()
		self.demo_agent.mj_data.qpos[:] = qpos

		control_signals = self.demo_agent.controller.generate_control_signals(
			self.camera,
			self.demo_agent.mj_model,
			self.demo_agent.mj_data,
			visualize=False,
			control_info={"force_idle": False, "key_pressed": self.keyboard.keys}
		)

		if self.demo_agent.args.use_qpos:
			control_signals["context_mujoco_qpos"] = context_mujoco_qpos
		else:
			control_signals["context_motion_features"] = context_motion_features

		with torch.no_grad():
			self.demo_agent.full_agent.generate_new_frames(
				control_signals,
				self.demo_agent.controller.get_controller_dt() * self.demo_agent.args.generate_dt
			)

		self.camera.cam.lookat[:] = self.demo_agent.controller.get_prev_qpos()[:, :3].mean(axis=0)

		if self.reference_qpos is None:
			self.reference_qpos = qpos.copy()

		if self.debug_joint is not None:
			# A small, deterministic skeletal test independent of learned motion.
			# Use the exported zero-joint bind pose, not MotionBricks' generated
			# starting pose, then perturb exactly one physical hinge.
			qpos = self.reference_qpos.copy()

			for joint_name, qpos_address, transform in self.joints:
				qpos[qpos_address] = 0.0

			for joint_name, qpos_address, transform in self.joints:
				if joint_name == self.debug_joint:
					qpos[qpos_address] += self.debug_angle
					break

		self.apply_qpos(qpos)

	def apply_qpos(self, qpos):
		for joint_name, qpos_address, transform in self.joints:
			# blender_mujoco made every physical hinge bone's local Y its MuJoCo axis.
			# OSG's row-vector equivalent of Blender's rest * local-pose is
			# local-pose * rest.
			rotation = osg.Matrix.rotate(qpos[qpos_address], osg.Vec3(0.0, 1.0, 0.0))
			transform.matrix = rotation * self.rest_matrices[joint_name]

		position_delta = qpos[:3] - self.reference_qpos[:3]
		orientation_delta = relative_quaternion(qpos[3:7], self.reference_qpos[3:7])
		self.model_root.matrix = matrix_from_quaternion(orientation_delta) * osg.Matrix.translate(
			position_delta[0], position_delta[1], position_delta[2]
		)

class MotionBricksUpdateCallback(osg.NodeCallback):
	"""Run pose assignment in OSG's update traversal before skin-palette upload."""

	def __init__(self, driver):
		super().__init__()

		self.driver = driver

	def __call__(self, node, visitor):
		self.driver.advance()

		# Returning True asks the binding's NodeCallback trampoline to continue
		# traversal, including osgGLTF's descendant skin-palette callback.
		return True

def make_motionbricks_args(args):
	root = args.motionbricks_root

	return argparse.Namespace(
		humanoid_scene_xml=str(root / "assets" / "skeletons" / "g1" / "scene_29dof.xml"),
		skeleton_xml=str(root / "assets" / "skeletons" / "g1" / "g1.xml"),
		result_dir=str(root / "out"),
		data_root=str(root / "datasets"),
		explicit_dataset_folder=str(root / "datasets" / "motionbricks-G1"),
		clips_ckpt=str(root / "out" / "G1-clip.ckpt"),
		reprocess_clips=0,
		controller=args.controller,
		lookat_movement_direction=0,
		pre_filter_qpos=1,
		source_root_realignment=1,
		target_root_realignment=1,
		force_canonicalization=1,
		skip_ending_target_cond=0,
		random_speed_scale=0,
		speed_scale=[0.8, 1.2],
		generate_dt=args.generate_dt,
		random_seed=args.random_seed,
		use_qpos=1,
		planner="default",
		allowed_mode=None,
		clips="G1",
		return_model_configs=True,
		return_dataloader=True,
		recording_dir=None,
		EXP="default"
	)


# Set by build_scene(), read by configure_viewer() -- keyboard/args have no natural home in the
# returned Node (build_scene()'s contract is just "return a Node"); same shape/reason as
# pyosg-khronos-viewer.py's _args/_pbr.
_args = None
_keyboard = None

# The real pipeline-assembly entrypoint -- returns the root Node, no viewer/window side effects.
def build_scene(w, h):
	global _args, _keyboard

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--model", type=pathlib.Path, default=DEFAULT_MODEL)
	parser.add_argument("--motionbricks-root", type=pathlib.Path, default=DEFAULT_MOTIONBRICKS_ROOT)
	parser.add_argument("--controller", choices=("wasd", "random"), default="wasd")
	parser.add_argument("--generate-dt", type=float, default=2.0)
	parser.add_argument("--random-seed", type=int, default=1234)
	parser.add_argument(
		"--debug-joint",
		help="freeze the first MotionBricks pose and add --debug-angle radians to this joint"
	)
	parser.add_argument("--debug-angle", type=float, default=0.5)
	_args = args = parser.parse_args()

	for path, description in (
		(args.model, "g1stick glTF"),
		(args.motionbricks_root, "MotionBricks checkout")
	):
		if not path.exists():
			raise FileNotFoundError(f"{description} not found: {path}")

	osg.DisplaySettings.instance.numMultiSamples = 8
	model = osgDB.readNodeFile(str(args.model))

	if model is None:
		raise RuntimeError(f"failed to load glTF model {args.model}")

	install_skinning_shader(model)

	print("[MotionBricks] loading stock NVIDIA G1 checkpoints...")
	# NVIDIA's Hydra configs contain a few paths relative to the motionbricks
	# checkout (notably out/motionbricks_pose/.../skeleton/joints.p). Their
	# interactive_demo_g1.py is normally launched from that directory.
	os.chdir(args.motionbricks_root)
	demo_agent = navigation_demo(make_motionbricks_args(args))
	keyboard = OSGKeyboard()
	motion_root = osg.MatrixTransform()
	motion_root.name = "MotionBricks_RootMotion"
	motion_root.children.append(model)
	driver = MotionBricksDriver(
		demo_agent,
		model,
		motion_root,
		keyboard,
		args.debug_joint,
		args.debug_angle
	)
	motion_root.updateCallback = MotionBricksUpdateCallback(driver)

	root = osg.Group()
	root.children.append(motion_root)

	_keyboard = keyboard

	return root

# clearColor/eventHandlers registration need the live viewer, which build_scene() never receives.
def configure_viewer(viewer, root):
	args = _args

	viewer.camera.clearColor = osg.Vec4(*CLEAR_COLOR)
	viewer.eventHandlers.append(_keyboard)

	if args.debug_joint is None:
		print("[MotionBricks] OSG controls: WASD walk; V/Z/X/B/R/T/C/E/F/G/Q styles")

	else:
		print(
			f"[MotionBricks] skeletal test: {args.debug_joint} += {args.debug_angle:.3f} radians"
		)

if __name__ == "__main__":
	W, H = window_size()

	viewer = osgViewer.Viewer()
	root = build_scene(W, H)

	viewer.sceneData = root
	viewer.cameraManipulator = osgGA.TrackballManipulator()

	configure_viewer(viewer, root)

	while not viewer.done:
		viewer.frame()
