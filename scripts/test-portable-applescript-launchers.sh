#!/usr/bin/env bash

set -euo pipefail
umask 077

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/.." && pwd -P)"
cd "$repo_root"

if matches="$(git grep -nE '/Users/[^/]+/|PersonalProjects/gmail-organizer' -- '*.applescript' 2>/dev/null)" && [[ -n "$matches" ]]; then
  printf 'stale or concrete launcher paths remain:\n%s\n' "$matches" >&2
  exit 1
fi

launchers=(
  "scripts/GmailOrganizer.applescript"
  "scripts/GmailOrganizer_Updated.applescript"
)

for launcher in "${launchers[@]}"; do
  grep -Fq 'POSIX path of (path to home folder)' "$launcher"
  grep -Fq 'Desktop/Projects/gmail-organizer' "$launcher"
  grep -Fq './scripts/launch_gmail_organizer.sh' "$launcher"
done

test_root="$(mktemp -d "$HOME/.Trash/GmailOrganizer-AppleScript-Tests.XXXXXX")"
chmod 700 "$test_root"

for launcher in "${launchers[@]}"; do
  output_name="$(basename "$launcher" .applescript).scpt"
  osacompile -o "$test_root/$output_name" "$launcher"
  [[ -f "$test_root/$output_name" ]]
  [[ "$(stat -f '%Lp' "$test_root/$output_name")" == "600" ]]
done

printf 'portable AppleScript launcher checks passed; retained evidence: %s\n' "$test_root"
