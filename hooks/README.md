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

### Claude Code Setup

1. Add hooks directory to Claude Code's hook path in settings
2. Ensure hooks are executable: `chmod +x hooks/*.sh`
3. Configure environment variables (see below)

### Environment Variables

- `OBSIDIAN_MEMORY_API_URL` - Backend API URL (default: `http://localhost:8000`)
- `OBSIDIAN_MEMORY_PROJECT` - Current project name
- `OBSIDIAN_MEMORY_VAULT` - Default vault name
- `OBSIDIAN_MEMORY_SESSION_ID` - Session ID (auto-set by SessionStart)
- `CLAUDE_SESSION_ID` - Claude Code session ID (if available)

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

Test hooks manually:
```bash
# Test SessionStart
OBSIDIAN_MEMORY_PROJECT="test" ./hooks/session-start.sh

# Test PostToolUse
OBSIDIAN_MEMORY_SESSION_ID="test-session" \
  ./hooks/post-tool-use.sh "write_file" "Created file" ""

# Test SessionEnd
OBSIDIAN_MEMORY_SESSION_ID="test-session" ./hooks/session-end.sh
```
