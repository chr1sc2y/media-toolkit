#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)
SKILLS_ROOT=${CODEX_HOME:-"$HOME/.codex"}/skills
SKILL_NAMES="initial-cull extract-feature learn-color-style"

mkdir -p "$SKILLS_ROOT"

for name in $SKILL_NAMES; do
    source_path="$REPO_ROOT/skills/$name"
    destination="$SKILLS_ROOT/$name"

    if [ ! -f "$source_path/SKILL.md" ]; then
        echo "Missing repository skill: $source_path/SKILL.md" >&2
        exit 1
    fi

    if [ -L "$destination" ]; then
        rm "$destination"
    elif [ -e "$destination" ]; then
        echo "Refusing to replace $destination because it is not a symlink." >&2
        exit 1
    fi

    ln -s "$source_path" "$destination"
    echo "Linked $destination -> $source_path"
done
