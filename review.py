#!/usr/bin/env python3
"""Backwards-compatible entry point: ``python review.py``.

The implementation lives in the ``ai_reviewer`` package; see ``ai_reviewer/cli.py``.
"""

import sys

from ai_reviewer.cli import main

if __name__ == "__main__":
    sys.exit(main())
