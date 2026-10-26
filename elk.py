#!/usr/bin/env python3
"""Compatibility shim. Prefer `elk` or `python -m elkbleddm.cli`."""

from elkbleddm.cli import main

if __name__ == "__main__":
    main()
