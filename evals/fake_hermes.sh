#!/bin/sh
# CI fixture for interface discovery. It never loads a model.
if [ "$1" = "--version" ]; then
  echo "Hermes Agent eval fixture"
  exit 0
fi
if [ "$1" = "chat" ] && [ "$2" = "--help" ]; then
  echo "--max-turns --checkpoints --source"
  exit 0
fi
echo "--tui --cli --pass-session-id sessions serve logs"
