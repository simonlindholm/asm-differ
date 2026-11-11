#!/usr/bin/env python3
"""
Manual flicker test for watch mode (-w).

Builds a reference object and a set of variants of the watched object, prints
the command to run diff.py in watch mode on them, then keeps overwriting the
watched object with a random variant at random short intervals until Ctrl-C.
Run the printed command in another terminal and watch for flickering.

All generated files go in flicker_test_fixture/ next to this script
(gitignored), which is recreated on each run. The fixture is test.py's
TestFixture, shared with the automated watch mode tests there.

Usage: tests/flicker_test.py
"""

import argparse
import os
import random
import shutil
import sys
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
FIXTURE_DIR = os.path.join(TESTS_DIR, "flicker_test_fixture")

# the repo's test.py, not the standard library's test package
sys.path.insert(0, REPO_DIR)
from test import TestFixture  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=str(__doc__).split("\n\n")[1])
    parser.add_argument(
        "--min", type=float, default=0.15, help="min seconds between edits"
    )
    parser.add_argument(
        "--max", type=float, default=0.6, help="max seconds between edits"
    )
    parser.add_argument(
        "--lines", type=int, default=300, help="instructions in the function"
    )
    parser.add_argument(
        "--variants", type=int, default=8, help="number of object variants"
    )
    args = parser.parse_args()
    if args.min <= 0.1:
        print(
            "warning: edits closer than the 100ms debounce get merged",
            file=sys.stderr,
        )

    for tool in ["gcc", "objdump"]:
        if not shutil.which(tool):
            sys.exit(f"missing required tool: {tool}")

    workdir = FIXTURE_DIR
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir)
    try:
        fixture = TestFixture(workdir)
        variants = fixture.setup(args.lines, args.variants)

        PYTHON = "python3"
        print(
            "Run this in another terminal (using your python3 that has the dependencies installed):\n"
        )
        print(f"    {fixture.command(PYTHON)}\n")
        _ = input("Press Enter to start editing (Ctrl-C to stop)...")

        current = 0
        count = 0
        while True:
            nxt = random.choice([i for i in range(len(variants)) if i != current])
            fixture.write_obj(variants[nxt])
            current = nxt
            count += 1
            print(f"\redits: {count} (variant {nxt})   ", end="", flush=True)
            time.sleep(random.uniform(args.min, args.max))
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
