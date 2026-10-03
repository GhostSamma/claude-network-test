#!/usr/bin/env bash
# Gate watch-research files: check.py with this brief's trailer + every SOURCE
# line class-tagged. Commits and pushes the ones that pass. Usage: gate_watch.sh FILE...
set -u
cd "$(git rev-parse --show-toplevel)"
PASS=""
for f in "$@"; do
  python3 research/judge/check.py --require "SOURCE:,SEPARATED FROM TOPIC?" "$f"; rc=$?
  total=$(grep -c "^SOURCE:" "$f"); tagged=$(grep -cE "^SOURCE: *\[(PEER-REVIEWED|PREPRINT|PLATFORM DOC|DATASET|VENDOR)\]" "$f")
  if [ "$total" = "$tagged" ]; then echo "  tags: $tagged/$total OK"; else echo "  FAIL tags: $tagged/$total untagged:"; grep "^SOURCE:" "$f" | grep -vE "^SOURCE: *\[" | head -3 | sed 's/^/    /'; rc=1; fi
  echo "  class mix: $(grep -oE '^SOURCE: *\[[A-Z -]+\]' "$f" | sed 's/SOURCE: *//' | sort | uniq -c | awk '{printf "%s×%s ", $2" "$3, $1}' | sed 's/×/ ×/g')"
  echo "  separated: $(grep -oiE '^SEPARATED FROM TOPIC\? *(yes|no|partly)' "$f" | awk '{print tolower($NF)}' | sort | uniq -c | awk '{printf "%s %s  ", $2, $1}')"
  [ $rc -eq 0 ] && PASS="$PASS $f"
done
echo; echo "passing:${PASS:- none}"
if [ -n "$PASS" ]; then
  names=$(echo $PASS | sed 's#research/watch/##g; s#\.txt##g; s# #, #g')
  git add $PASS && git commit -q -m "Watch research: $names

Pass check.py with the SEPARATED FROM TOPIC? trailer and the class-tag gate.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_017PEq4nTMc2NbxFgw3w7X43" && git push -q origin claude/stoic-goodall-wpjypm 2>&1 | grep -v "acknowledgments\|negotiation"; git log --oneline | head -1
fi
