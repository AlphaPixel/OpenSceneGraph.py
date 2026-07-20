# aipython + OpenSceneGraph.py — Index

This directory is OpenSceneGraph.py's own accumulated knowledge for driving a
live OSG viewer through the `aipython` MCP bridge (tmux or Jupyter-kernel
backed IPython). It exists because this project's REPL setup has a handful of
sharp, non-obvious edges that get rediscovered by trial and error unless
written down -- several of them cost real debugging sessions before being
pinned down.

**Always read [`01-core.md`](01-core.md) first**, in any session that's about
to drive `viewer.frame()` live via `aipython`, before writing any callback or
running any multi-line block through a tmux-backed session. Everything in it
has been hit for real, more than once, across different sessions.

Read the others situationally:

| File | Read when... |
|---|---|
| [`01-core.md`](01-core.md) | Always, first. Session bootstrap, callback safety, tmux/IPython mechanics. |
| [`05-camera-manipulator.md`](05-camera-manipulator.md) | Building/customizing an `osgGA.CameraManipulator` subclass, or doing camera-relative work (e.g. "light the subject from the camera's upper-right"). |
| [`10-rtt.md`](10-rtt.md) | Building a render-to-texture / multi-camera scene graph live (RTT cameras, `osg.Camera()` construction quirks, `Group.children` limitations). |
| [`15-shader-hotswap.md`](15-shader-hotswap.md) | Debugging shader-side logic live by patching GLSL and hot-swapping a `Program`, or when a live variable reassignment "has no effect." |
| [`20-object-lifetime.md`](20-object-lifetime.md) | Investigating a leak, a "removed but still alive" object, or verifying true C++ destruction vs. just scene-graph detachment. |

## Why this exists as `aipython/*.md` and not a Claude Code skill

This is deliberately a plain, agent-agnostic directory of markdown files at
the repo root, not `.claude/skills/`. Multiple "agentic scaffolding" tools
(Claude Code, Codex, others) use this project via the `aipython` MCP server;
putting this knowledge in a Claude-Code-specific location would hide it from
everyone else. The intent is for `aipython` itself to grow a small discovery
feature (scan `<repo>/aipython/*.md`, surface the index) so any connected
agent finds this automatically -- until then, an agent working in this repo
should proactively `ls`/`Read` this directory before starting REPL work here,
the same way it would check `CLAUDE.md`.
