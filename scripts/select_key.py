#!/usr/bin/env python3
import os, sys, subprocess
HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TARGET = os.path.join(ROOT, "launcher", "scripts", "select_key.py")
if not os.path.exists(TARGET):
    sys.stderr.write(f"select_key.py not found at {TARGET}\n")
    sys.exit(1)
os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[1:])
