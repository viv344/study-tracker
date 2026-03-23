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

for i in $(seq 1 $NUM_COMMITS); do
  # Append a small invisible change to activity.log
  echo "$(date '+%Y-%m-%d %H:%M:%S') session-$i" >> activity.log

  MSG="${MESSAGES[$RANDOM % ${#MESSAGES[@]}]}"
  git add activity.log
  git commit -m "$MSG"

  # Small random sleep between commits (30-120s) so timestamps differ
  sleep $(( RANDOM % 90 + 30 ))
done

git push origin main
