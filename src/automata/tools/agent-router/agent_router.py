#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["cyclopts>=4.11.1", "uvicorn>=0.30.0", "websockets>=12.0"]
# ///
"""Standalone entry point; importing the library never starts a listener."""

from automata_router.cli import main

if __name__ == "__main__":
    main()
