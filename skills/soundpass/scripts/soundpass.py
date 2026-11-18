#!/usr/bin/env python3
"""soundpass CLI. Pure Python 3.8+, no dependencies.

    python3 soundpass.py list | palettes | scan | render | pack | analyze | sampler | preview | play
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sp.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
