#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

ANSWER=$(cat workspace/answer.txt 2>/dev/null || echo "")
ANSWER_TRIMMED="${ANSWER%$'\n'}"

if [ "$ANSWER_TRIMMED" = "correct" ]; then
  PASS=true
  EXIT=0
  SCORE=100
else
  PASS=false
  EXIT=1
  SCORE=0
fi

python3 -c "
import json, sys
pass_ = sys.argv[1] == 'true'
score = int(sys.argv[2])
answer = sys.argv[3]
print(json.dumps({
    'pass': pass_,
    'score': score,
    'signals': {
        'answer_correct': pass_,
        'observed': answer,
    },
    'notes': 'simple fixture grader',
}))
" "$PASS" "$SCORE" "$ANSWER_TRIMMED"
exit $EXIT
