"""Withhold submitter contact details from GEDCOM files, in place.

Usage: python3 scripts/scrub_submitters.py <file-or-dir> [...]

Every level-0 ``SUBM`` record is cut down to its header line and
``1 NAME Withheld``. These records hold the compiler's name, postal address,
phone and email, which are no part of the family history. The record itself
is kept so ``HEAD.SUBM`` pointers still resolve. Bytes are edited as-is, so
encoding and line endings survive; re-running changes nothing.

Author: Eric G. Suchanek, PhD
License: Elastic 2.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_LEVEL0 = re.compile(rb"^(?:\xef\xbb\xbf)?\s*0\s")
_SUBMITTER = re.compile(rb"^(?:\xef\xbb\xbf)?\s*0\s+@[^@]+@\s+SUBM\b")
_WITHHELD = b"1 NAME Withheld"


def scrub(data: bytes) -> bytes:
    """Return *data* with every submitter record reduced to a stub.

    :param data: Raw GEDCOM bytes.
    :return: The scrubbed bytes; equal to *data* when there is nothing to do.
    """
    out: list[bytes] = []
    in_submitter = False
    for line in data.splitlines(keepends=True):
        if _LEVEL0.match(line):
            in_submitter = bool(_SUBMITTER.match(line))
            out.append(line)
            if in_submitter:
                ending = line[len(line.rstrip(b"\r\n")) :] or b"\n"
                out.append(_WITHHELD + ending)
        elif not in_submitter:
            out.append(line)
    return b"".join(out)


def main(argv: list[str]) -> int:
    """Scrub every ``.ged`` file under the given paths.

    :param argv: Files or directories.
    :return: Process exit status.
    """
    if not argv:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    changed = 0
    for arg in argv:
        root = Path(arg)
        files = [root] if root.is_file() else sorted(root.rglob("*.ged"))
        for path in files:
            data = path.read_bytes()
            scrubbed = scrub(data)
            if scrubbed != data:
                path.write_bytes(scrubbed)
                changed += 1
    print(f"scrub_submitters: {changed} file(s) changed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
