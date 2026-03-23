#!/bin/bash
# Daily auto-commit script for study tracker

cd /home/vivek/study-tracker

MESSAGES=(
  "update study notes"
  "track session progress"
  "log revision block"
  "update tracker config"
  "minor style tweaks"
  "refine subject layout"
  "update session timings"
  "adjust module ordering"
  "clean up notes section"
  "log daily study block"
  "update progress tracker"
  "revision session logged"
  "tweak UI spacing"
  "update weekly plan"
  "log morning session"
  "log afternoon session"
  "track module progress"
  "update study schedule"
)

NUM_COMMITS=$(( RANDOM % 5 + 1 ))

# ~30% chance of applying a feature patch on any given day
APPLY_PATCH=$(( RANDOM % 10 ))
if [ $APPLY_PATCH -lt 3 ]; then
  PATCH_MSG=$(python3 apply_patch.py 2>&1)
  EXIT=$?
  if [ $EXIT -eq 0 ] && [ -n "$PATCH_MSG" ]; then
    git add index.html patch_idx.txt
    git commit -m "$PATCH_MSG"
    sleep $(( RANDOM % 60 + 30 ))
    NUM_COMMITS=$(( NUM_COMMITS - 1 ))  # one commit already done
  fi
fi

for i in $(seq 1 $NUM_COMMITS); do
  echo "$(date '+%Y-%m-%d %H:%M:%S') session-$i" >> activity.log

  MSG="${MESSAGES[$RANDOM % ${#MESSAGES[@]}]}"
  git add activity.log
  git commit -m "$MSG"

  sleep $(( RANDOM % 90 + 30 ))
done

git push origin main
