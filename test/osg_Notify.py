from .conftest import f32

import os
import pytest

from OpenSceneGraph import *

# import logging

os.putenv("OSG_THREADING", "SingleThreaded")

# log = logging.getLogger("osg")
#
# log.setLevel(logging.DEBUG)
#
# if not log.handlers:
# 	h = logging.StreamHandler()
# 	f = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
#
# 	h.setFormatter(f)
#
# 	log.addHandler(h)
#
# SEVERITY_MAP = {
# 	osg.NotifySeverity.FATAL: logging.CRITICAL,
# 	osg.NotifySeverity.WARN: logging.WARNING,
# 	osg.NotifySeverity.NOTICE: logging.INFO,
# 	osg.NotifySeverity.INFO: logging.INFO,
# 	osg.NotifySeverity.DEBUG_INFO: logging.DEBUG,
# 	osg.NotifySeverity.DEBUG_FP: logging.DEBUG
# }

def notify_handler(sev, msg):
	msg = msg.strip()

	if not msg:
		return

	print(f"{sev}: {msg}")

osg.setNotifyLevel(osg.NotifySeverity.INFO)

def test_notify_handler(capsys, emit_notify):
	osg.setNotifyHandler(notify_handler)

	emit_notify()

	msg = [s for s in capsys.readouterr().out.split("\n") if len(s)]

	print(msg)

	assert len(msg) == 4
	assert msg[0] == f"{osg.NotifySeverity.FATAL}: FATAL"
	assert msg[1] == f"{osg.NotifySeverity.WARN}: WARN"
	assert msg[2] == f"{osg.NotifySeverity.NOTICE}: NOTICE"
	assert msg[3] == f"{osg.NotifySeverity.INFO}: INFO"

def test_notify():
	assert osg.getNotifyHandler() == notify_handler

	osg.setNotifyHandler(None)

	assert osg.getNotifyHandler() == None

# def notify_log(sev, msg):
# 	msg = msg.strip()
#
# 	if not msg:
# 		return
#
# 	level = SEVERITY_MAP.get(sev, logging.INFO)
#
# 	log.log(level, msg)
