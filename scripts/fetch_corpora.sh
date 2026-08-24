#!/bin/bash
# Fetch the public GEDCOM test corpora into corpora/ (gitignored).
#
# Usage: ./scripts/fetch_corpora.sh
#
# Nothing fetched here is ever committed. The torture-test files are licensed
# for non-commercial use only and the collections carry their authors' own
# terms, so this repo points at them rather than vendoring them. See
# docs/CORPORA.md for what each set is and what it exercises.
#
# Idempotent: re-running updates the clone and skips downloads that exist.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPORA="$REPO_DIR/corpora"
mkdir -p "$CORPORA"

# 1. D-Jeffrey/gedcom-samples: dual MIT / CC0. Contains royal92, pres2020,
#    the SourceForge "famous family trees" collection, and a size ladder from
#    14 people (bronte.ged) to 203,154 (longsword/WilliamLongsword.ged).
if [ -d "$CORPORA/gedcom-samples/.git" ]; then
    git -C "$CORPORA/gedcom-samples" pull --quiet --ff-only
else
    git clone --quiet --depth 1 https://github.com/D-Jeffrey/gedcom-samples.git \
        "$CORPORA/gedcom-samples"
fi
echo "gedcom-samples: $(find "$CORPORA/gedcom-samples" -name '*.ged' | wc -l | tr -d ' ') files"

# 2. GEDitCOM GEDCOM 5.5 torture test (H. Eichmann, J. A. Nairn). Every tag
#    the 5.5 standard allows, ANSEL, both line-ending conventions.
#    "Feel free to copy and use this GEDCOM file for any non-commercial
#    purpose." The site's TLS chain does not verify on macOS, hence -k.
if [ ! -f "$CORPORA/torture/TGC551LF.ged" ]; then
    mkdir -p "$CORPORA/torture"
    curl -skL --max-time 120 -o "$CORPORA/torture/TestGED.zip" \
        https://www.geditcom.com/downlds/TestGED.zip
    unzip -o -q "$CORPORA/torture/TestGED.zip" -d "$CORPORA/torture" \
        'TGC55*.ged' 'README.txt'
    rm "$CORPORA/torture/TestGED.zip"
fi
echo "torture: $(ls "$CORPORA"/torture/*.ged | wc -l | tr -d ' ') files"

# 3. Gramps example (42 people, GEDCOM 5.5, UTF-8). Data file inside a
#    GPL-2.0 repository; used here as test input only.
if [ ! -f "$CORPORA/gramps/sample.ged" ]; then
    mkdir -p "$CORPORA/gramps"
    curl -sL --max-time 60 -o "$CORPORA/gramps/sample.ged" \
        https://raw.githubusercontent.com/gramps-project/gramps/master/example/gedcom/sample.ged
fi
echo "gramps: 1 file"

echo "corpora ready under $CORPORA"
