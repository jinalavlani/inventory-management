#!/bin/bash

# Pre-tool-use hook for Claude Code
# Runs a frontend build check before deploy-related Bash commands
# (git push, npm run build, deploy) and blocks them if the build fails.

# Read the JSON input from stdin
INPUT=$(cat)

# Extract the Bash command using node (always available here; jq may not be)
COMMAND=$(printf '%s' "$INPUT" | node -e '
let s = "";
process.stdin.on("data", c => s += c);
process.stdin.on("end", () => {
  try { process.stdout.write(JSON.parse(s).tool_input?.command ?? ""); } catch {}
});
')

# Only act on deploy-related commands; let everything else through
if ! printf '%s' "$COMMAND" | grep -Eq '(^|[^[:alnum:]_-])(git[[:space:]]+push|npm[[:space:]]+run[[:space:]]+build|deploy)([^[:alnum:]_-]|$)'; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CLIENT_DIR="${PROJECT_DIR}/client"

if [ ! -f "${CLIENT_DIR}/package.json" ]; then
    echo "Pre-deploy check: ${CLIENT_DIR}/package.json not found, cannot run the build check." >&2
    exit 2
fi

# Run the frontend build and capture its output
BUILD_OUTPUT=$(cd "$CLIENT_DIR" && npm run build 2>&1)
BUILD_STATUS=$?

if [ $BUILD_STATUS -ne 0 ]; then
    # Exit code 2 blocks the command; stderr is shown as the reason
    {
        echo "Pre-deploy check failed: 'npm run build' in client/ exited with code ${BUILD_STATUS}."
        echo "Blocked command: ${COMMAND}"
        echo "Last 40 lines of build output:"
        printf '%s\n' "$BUILD_OUTPUT" | tail -n 40
    } >&2
    exit 2
fi

# Build passed, allow the command to proceed
exit 0
