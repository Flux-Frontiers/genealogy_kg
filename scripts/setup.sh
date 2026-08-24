#!/bin/bash
# Development environment setup for GenealogyKG.
#
# Usage: ./scripts/setup.sh [--with-kg]
#
#   --with-kg   also install the dockg/pycodekg CLIs (Poetry group `kg`)
#
# Runs with VIRTUAL_ENV and POETRY_ACTIVE unset so an environment inherited
# from another repo's shell cannot hijack the install (fleet convention).

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if ! command -v poetry &> /dev/null; then
    echo "Poetry is not installed. Install it with:"
    echo "   curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

GROUPS="dev"
if [[ "$1" == "--with-kg" ]]; then
    GROUPS="dev,kg"
fi

echo "Installing genealogy-kg with Poetry groups: $GROUPS"
env -u VIRTUAL_ENV -u POETRY_ACTIVE poetry install --with "$GROUPS"

echo
env -u VIRTUAL_ENV -u POETRY_ACTIVE poetry run python -c \
    "import genealogy_kg; print('genealogy_kg', genealogy_kg.__version__)"

echo
echo "Next steps:"
echo "  poetry run pytest"
echo "  poetry run genealogykg build --source path/to/family.ged"
echo "  make help"
