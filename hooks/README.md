# Claude Code Hooks

This directory contains Claude Code lifecycle hooks for Obsidian-Memory integration.

## Overview

Claude Code hooks allow the Obsidian-Memory system to automatically capture knowledge, inject context, and manage sessions throughout the Claude Code development workflow.

## Available Hooks

### SessionStart (`session-start.sh`)
**Trigger**: When a new Claude Code session begins  
**Purpose**: Load project context and inject recent memories  
**Features**:
- Creates or retrieves session
- Loads recent notes for context injection
- Lists available projects if no project specified

### UserPromptSubmit (`user-prompt-submit.sh`)
**Trigger**: When user submits a prompt  
**Purpose**: Log user intent for session tracking  
**Features**:
- Captures user prompts as session events
- Tracks prompt metadata (length, project context)

### PostToolUse (`post-tool-use.sh`)
**Trigger**: After a tool is used  
**Purpose**: Capture file edits, commands, errors, web research  
**Features**:
- Automatically detects event type (file_edit, command, research, error)
- Captures tool results and errors
- Tracks file paths for file operations

### PreCompact (`pre-compact.sh`)
**Trigger**: Before context is compacted/lost  
**Purpose**: Trigger AI summarization to preserve important information  
**Features**:
- Generates AI summary before context loss
- Captures key learnings, decisions, errors, solutions

### SessionEnd (`session-end.sh`)
**Trigger**: When session ends  
**Purpose**: Finalize session, extract patterns, sync  
**Features**:
- Generates final session summary
- Ends session and marks as completed
- Prepares for pattern extraction (future enhancement)

## Configuration

### Prerequisites

1. **Make hooks executable** (required):
   ```bash
   chmod +x hooks/*.sh
   ```

2. **Configure environment variables**:
   ```bash
   # Copy the example configuration
   cp .env.example .env

   # Edit .env with your settings
   nano .env  # or use your preferred editor
   ```

### Claude Code Setup

1. Add hooks directory to Claude Code's hook path in `.claude/settings.json`
2. Ensure backend is running: `cd backend && uvicorn app.main:app --reload`
3. Configure environment variables (see below)

### Environment Variables

Create a `.env` file from `.env.example` and configure:

- `OBSIDIAN_MEMORY_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `OBSIDIAN_MEMORY_PROJECT` - Current project name (required for context)
- `OBSIDIAN_MEMORY_VAULT` - Default vault name (optional, uses first vault if not set)
- `OBSIDIAN_MEMORY_SESSION_ID` - Session ID (auto-set by SessionStart hook)
- `CLAUDE_SESSION_ID` - Claude Code session ID (auto-provided by Claude Code)

Example `.env` file:
```bash
OBSIDIAN_MEMORY_API_URL=http://localhost:8000
OBSIDIAN_MEMORY_PROJECT=my-project
OBSIDIAN_MEMORY_VAULT=default
```

## Integration

Each hook communicates with the Obsidian-Memory backend via:
- **REST API** (primary method) - Direct HTTP calls to backend
- **MCP server** (future) - Could use MCP tools if available
- **File system** (future) - Direct vault access for advanced operations

## Usage Example

```bash
# Set environment variables
export OBSIDIAN_MEMORY_API_URL="http://localhost:8000"
export OBSIDIAN_MEMORY_PROJECT="my-project"

# Hooks will be automatically called by Claude Code
# Manual testing:
./hooks/session-start.sh
./hooks/user-prompt-submit.sh "Implement user authentication"
./hooks/post-tool-use.sh "write_file" "Created auth.py" ""
./hooks/session-end.sh
```

## Error Handling

All hooks are designed to:
- Fail gracefully if backend is unavailable
- Skip execution if required environment variables are missing
- Log warnings for non-critical failures
- Never interrupt Claude Code workflow

## Testing

### Manual Hook Execution

Test individual hooks manually:

```bash
# Test SessionStart - creates a new session
OBSIDIAN_MEMORY_PROJECT="test" ./hooks/session-start.sh

# Test UserPromptSubmit - logs a user prompt
OBSIDIAN_MEMORY_SESSION_ID="test-session" \
  ./hooks/user-prompt-submit.sh "Implement user authentication"

# Test PostToolUse - logs different tool events
OBSIDIAN_MEMORY_SESSION_ID="test-session" \
  ./hooks/post-tool-use.sh "write_file" "Created auth.py" ""

OBSIDIAN_MEMORY_SESSION_ID="test-session" \
  ./hooks/post-tool-use.sh "bash" "npm test" "All tests passed"

OBSIDIAN_MEMORY_SESSION_ID="test-session" \
  ./hooks/post-tool-use.sh "web_search" "authentication best practices" "Found 10 results"

# Test PreCompact - triggers AI summary
OBSIDIAN_MEMORY_SESSION_ID="test-session" ./hooks/pre-compact.sh

# Test SessionEnd - finalizes session
OBSIDIAN_MEMORY_SESSION_ID="test-session" ./hooks/session-end.sh
```

### Integration Testing

Full workflow test:

```bash
#!/bin/bash
# integration-test.sh

# Start backend if not running
cd backend && uvicorn app.main:app --reload &
BACKEND_PID=$!
sleep 2

# Set test environment
export OBSIDIAN_MEMORY_API_URL="http://localhost:8000"
export OBSIDIAN_MEMORY_PROJECT="integration-test"

# Run full session lifecycle
echo "Starting session..."
./hooks/session-start.sh
export OBSIDIAN_MEMORY_SESSION_ID="test-$(date +%s)"

echo "Simulating user prompt..."
./hooks/user-prompt-submit.sh "Build a REST API"

echo "Simulating tool uses..."
./hooks/post-tool-use.sh "write_file" "Created main.py" ""
./hooks/post-tool-use.sh "bash" "python main.py" "Server started"

echo "Triggering pre-compact..."
./hooks/pre-compact.sh

echo "Ending session..."
./hooks/session-end.sh

# Cleanup
kill $BACKEND_PID
```

## Troubleshooting

### Common Issues

#### 1. Backend Unavailable
**Symptom**: Hooks fail with connection errors
```
curl: (7) Failed to connect to localhost port 8000: Connection refused
```

**Solution**: Ensure backend is running:
```bash
cd backend && uvicorn app.main:app --reload
```

#### 2. Missing Environment Variables
**Symptom**: Hooks skip execution with warnings
```
Warning: OBSIDIAN_MEMORY_PROJECT not set, skipping hook
```

**Solution**: Set required environment variables:
```bash
export OBSIDIAN_MEMORY_PROJECT="my-project"
# Or use .env file
source .env
```

#### 3. Permission Denied
**Symptom**: Hooks fail to execute
```
bash: ./hooks/session-start.sh: Permission denied
```

**Solution**: Make hooks executable:
```bash
chmod +x hooks/*.sh
```

#### 4. Session Not Found
**Symptom**: Post-tool-use or session-end fail
```
Error: Session not found
```

**Solution**: Ensure SessionStart ran first and OBSIDIAN_MEMORY_SESSION_ID is set

### Viewing Hook Logs in Claude Code

To debug hook execution in Claude Code:

1. **Enable hook debugging**:
   ```bash
   claude --hooks-debug
   ```

2. **Check Claude Code logs**:
   - Hook execution appears in console output
   - Look for `[Hook: SessionStart]` style messages
   - Errors will be prefixed with `[Hook Error:]`

3. **Verify hook registration**:
   - Check `.claude/settings.json` for hook configuration
   - Ensure hooks path is correct

### Testing Without Backend

Hooks gracefully handle backend unavailability:

```bash
# Stop backend
# Hooks will still execute but skip API calls
./hooks/session-start.sh
# Output: "Warning: Backend unavailable, skipping..."
```
