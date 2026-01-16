#!/usr/bin/env bash
#
# Obsidian-Memory Project Setup Script
# Converts the claude-starter-kit template into the Obsidian-Memory project.
# Preserves project-specific files and sets up Ralph Wiggum development structure.
#
# Usage:
#   ./setup-project.sh                    # Interactive mode
#   ./setup-project.sh -y                 # Skip confirmation
#   ./setup-project.sh --no-commit        # Skip git operations
#

set -euo pipefail

# Project configuration
PROJECT_NAME="Obsidian-Memory"
LANGUAGES="python,typescript"  # Multi-language for Serena
CC_MODEL="opus"  # Using Opus for Ralph Wiggum development

# Options
NO_COMMIT=false
SKIP_CONFIRM=false

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${CYAN}>>>${NC} $1"; }

show_help() {
  cat <<'EOF'
Obsidian-Memory Project Setup Script

Converts the claude-starter-kit template into the Obsidian-Memory project
with Ralph Wiggum development structure.

Usage:
  ./setup-project.sh              # Interactive mode
  ./setup-project.sh -y           # Skip confirmation
  ./setup-project.sh --no-commit  # Skip git operations

Options:
  --no-commit    Skip git commit and push
  -y, --yes      Skip confirmation prompt
  -h, --help     Show this help message

What this script does:
  1. Cleans up template symlinks and deploys actual config files
  2. Creates Obsidian-Memory project structure
  3. Sets up Ralph Wiggum development files
  4. Preserves existing project work
  5. Configures for Python + TypeScript development
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --no-commit) NO_COMMIT=true; shift ;;
    -y|--yes) SKIP_CONFIRM=true; shift ;;
    -h|--help) show_help; exit 0 ;;
    *) log_error "Unknown option: $1"; show_help; exit 1 ;;
  esac
done

# Validate environment
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  log_error "Not inside a git repository"
  exit 1
fi

REPO_ROOT=$(git rev-parse --show-toplevel)
cd "$REPO_ROOT"

if [[ ! -d ".github/templates" ]]; then
  log_error "Templates directory .github/templates not found"
  exit 1
fi

# Show plan
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}              Obsidian-Memory Project Setup                     ${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Project Configuration:${NC}"
echo "  Name:       $PROJECT_NAME"
echo "  Languages:  $LANGUAGES (Python backend, TypeScript MCP/Web)"
echo "  Model:      $CC_MODEL (for Ralph Wiggum development)"
echo ""
echo -e "${CYAN}Actions:${NC}"
echo "  1. Deploy template configs (.claude, .serena, .taskmaster)"
echo "  2. Create project structure (backend/, mcp-server/, web-ui/, hooks/)"
echo "  3. Create Ralph Wiggum files (specs/, AGENTS.md, prompts, loop.sh)"
echo "  4. Remove template-only files (keep project files)"
echo "  5. Update CLAUDE.md for Obsidian-Memory"
if ! $NO_COMMIT; then
  echo "  6. Commit changes"
fi
echo ""

# Confirm
if ! $SKIP_CONFIRM; then
  echo -ne "${BLUE}?${NC} Proceed with setup? ${CYAN}[Y/n]${NC}: "
  read -r response
  if [[ "${response,,}" == "n" || "${response,,}" == "no" ]]; then
    log_warn "Aborted by user"
    exit 0
  fi
  echo ""
fi

# Execute setup
log_step "Configuring template files..."

# Update Serena config for multi-language (primary: python)
sed -i "s/project_name: \".*\"/project_name: \"$PROJECT_NAME\"/g" .github/templates/serena/project.yml
sed -i "s/language: \".*\"/language: \"python\"/g" .github/templates/serena/project.yml

# Update TaskMaster config
sed -i "s/\"projectName\": \".*\"/\"projectName\": \"$PROJECT_NAME\"/g" .github/templates/taskmaster/config.json

# Update Claude Code model
sed -i "s/\"model\": \".*\"/\"model\": \"$CC_MODEL\"/g" .github/templates/claude/settings.json

log_step "Removing template symlinks..."
rm -rf .claude .serena .taskmaster

log_step "Deploying configuration directories..."
cp -r .github/templates/claude ./.claude
cp -r .github/templates/serena ./.serena
cp -r .github/templates/taskmaster ./.taskmaster

log_step "Creating Obsidian-Memory project structure..."

# Core project directories
mkdir -p backend/app/{api,services,models}
mkdir -p backend/tests
mkdir -p mcp-server/src/{tools,transports}
mkdir -p mcp-server/tests
mkdir -p web-ui/src/{app,components,lib}
mkdir -p hooks
mkdir -p scripts

# Ralph Wiggum directories
mkdir -p specs
mkdir -p .taskmaster/docs

log_step "Creating Ralph Wiggum development files..."

# Create loop.sh
cat > loop.sh << 'LOOP_EOF'
#!/usr/bin/env bash
#
# Ralph Wiggum Development Loop
# Usage:
#   ./loop.sh              # Build mode, unlimited
#   ./loop.sh 20           # Build mode, max 20 iterations
#   ./loop.sh plan         # Plan mode, unlimited
#   ./loop.sh plan 5       # Plan mode, 5 iterations
#

set -euo pipefail

MODE="build"
MAX_ITERATIONS=0
ITERATION=0

# Parse arguments
if [[ "${1:-}" == "plan" ]]; then
  MODE="plan"
  shift
fi

if [[ "${1:-}" =~ ^[0-9]+$ ]]; then
  MAX_ITERATIONS=$1
fi

PROMPT_FILE="PROMPT_${MODE}.md"

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "Error: $PROMPT_FILE not found"
  exit 1
fi

echo "Starting Ralph Wiggum loop in $MODE mode..."
echo "Max iterations: ${MAX_ITERATIONS:-unlimited}"
echo ""

while true; do
  ((ITERATION++))

  if [[ $MAX_ITERATIONS -gt 0 && $ITERATION -gt $MAX_ITERATIONS ]]; then
    echo "Reached max iterations ($MAX_ITERATIONS)"
    break
  fi

  echo "=== Iteration $ITERATION ==="

  # Run Claude with the prompt
  if ! claude -p --dangerously-skip-permissions --model opus < "$PROMPT_FILE"; then
    echo "Claude exited with error, continuing..."
  fi

  # Small delay between iterations
  sleep 2
done

echo "Loop complete after $ITERATION iterations"
LOOP_EOF
chmod +x loop.sh

# Create PROMPT_plan.md
cat > PROMPT_plan.md << 'PLAN_EOF'
# Planning Mode - Gap Analysis

You are in PLANNING mode. Your job is to analyze specifications and create/update the implementation plan.

## Instructions

1. Study all files in `specs/` directory thoroughly
2. Study `AGENTS.md` for operational patterns and commands
3. Review existing code in `backend/`, `mcp-server/`, `web-ui/`, `hooks/`
4. Compare specifications against current implementation
5. Use parallel subagents for reading (up to 100 concurrent reads)
6. Use Opus model for complex analysis

## Output

Create or update `IMPLEMENTATION_PLAN.md` with:
- Prioritized list of unimplemented features
- Gaps between specs and code
- Dependencies between tasks
- Estimated complexity (S/M/L/XL)

## Critical Rules

99999. DO NOT implement anything - planning only
99998. DO NOT assume something is not implemented - search first
99997. Keep plan concise - bullet points, not essays
99996. Exit after updating IMPLEMENTATION_PLAN.md

Begin by reading all specs and the current implementation plan.
PLAN_EOF

# Create PROMPT_build.md
cat > PROMPT_build.md << 'BUILD_EOF'
# Building Mode - Implementation

You are in BUILDING mode. Your job is to implement ONE task from the plan.

## Instructions

1. Read `IMPLEMENTATION_PLAN.md` to find the highest priority incomplete task
2. Read `AGENTS.md` for build commands and patterns
3. Read relevant `specs/` files for the task
4. Search codebase before making changes - don't assume not implemented
5. Implement the task fully - no placeholders or stubs
6. Run tests after each change
7. Only ONE subagent should run tests at a time

## Completion

After successful implementation:
1. Mark task complete in `IMPLEMENTATION_PLAN.md`
2. Update `AGENTS.md` with any new patterns discovered (keep brief)
3. Commit changes with descriptive message
4. Exit

## Critical Rules

99999. Implement ONE task only, then exit
99998. DO NOT skip tests - backpressure is required
99997. DO NOT assume something is not implemented - search first
99996. Commit only when tests pass
99995. Update AGENTS.md with operational learnings (brief!)

Begin by reading IMPLEMENTATION_PLAN.md and selecting the highest priority task.
BUILD_EOF

# Create AGENTS.md
cat > AGENTS.md << 'AGENTS_EOF'
# Obsidian-Memory Operational Guide

## Project Overview

Unified memory management system for Claude Code with:
- FastAPI Python backend
- TypeScript MCP server (Bun)
- Next.js web UI
- Claude Code hooks

## Build Commands

### Backend (Python/FastAPI)
```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v
mypy app/
ruff check app/
```

### MCP Server (TypeScript/Bun)
```bash
cd mcp-server
bun install
bun test
bun run typecheck
bun run lint
```

### Web UI (Next.js)
```bash
cd web-ui
npm ci
npm test
npm run typecheck
npm run lint
npm run build
```

### Full Validation
```bash
./scripts/test-all.sh
```

## Patterns Discovered

<!-- Updated by Ralph during loops -->

## Common Failures

<!-- Updated by Ralph during loops -->

## Environment Setup

- Python 3.11+
- Bun 1.0+
- Node.js 20+
- SQLite 3.35+ (FTS5 support)
AGENTS_EOF

# Create IMPLEMENTATION_PLAN.md
cat > IMPLEMENTATION_PLAN.md << 'IMPL_EOF'
# Obsidian-Memory Implementation Plan

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete

## Phase 1: Core Foundation

### Priority: Critical
- [ ] **S** Backend project scaffolding (pyproject.toml, structure)
- [ ] **S** MCP server scaffolding (package.json, tsconfig)
- [ ] **S** Web UI scaffolding (Next.js setup)
- [ ] **M** Vault manager service (read/write markdown files)
- [ ] **M** Markdown parser (frontmatter, observations, relations)
- [ ] **M** SQLite + FTS5 search index
- [ ] **M** Basic CRUD API endpoints (/api/notes/*)
- [ ] **L** MCP tools: mem_read, mem_write, mem_search

## Phase 2: Knowledge Graph

### Priority: High
- [ ] **M** Graph engine (compute nodes/edges from markdown)
- [ ] **M** Wikilink extraction and resolution
- [ ] **M** Relation parsing from markdown
- [ ] **M** Graph traversal queries
- [ ] **L** build_context tool (memory:// URI patterns)
- [ ] **M** MCP tools: graph_traverse, graph_similar

## Phase 3: AI Processing

### Priority: High
- [ ] **M** AI processor service (Claude API)
- [ ] **L** Entity extraction from content
- [ ] **L** Automatic relation inference
- [ ] **M** Session summarization
- [ ] **L** Pattern detection

## Phase 4-8: See specs/ for details

---

## Discoveries

<!-- Findings during implementation -->

## Blockers

<!-- Current blockers -->
IMPL_EOF

log_step "Creating placeholder files..."

# Backend placeholder
cat > backend/pyproject.toml << 'PYPROJECT_EOF'
[project]
name = "obsidian-memory"
version = "0.1.0"
description = "Unified memory management system for Claude Code"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "python-frontmatter>=1.1.0",
    "aiosqlite>=0.19.0",
    "anthropic>=0.18.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.mypy]
python_version = "3.11"
strict = true

[tool.ruff]
target-version = "py311"
line-length = 100
PYPROJECT_EOF

# MCP server placeholder
cat > mcp-server/package.json << 'PACKAGE_EOF'
{
  "name": "obsidian-memory-mcp",
  "version": "0.1.0",
  "description": "MCP server for Obsidian-Memory",
  "type": "module",
  "main": "dist/index.js",
  "scripts": {
    "dev": "bun run src/index.ts",
    "build": "bun build src/index.ts --outdir dist",
    "test": "bun test",
    "typecheck": "tsc --noEmit",
    "lint": "eslint src/"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0"
  },
  "devDependencies": {
    "@types/bun": "latest",
    "typescript": "^5.3.0",
    "eslint": "^8.56.0"
  }
}
PACKAGE_EOF

# Web UI placeholder
cat > web-ui/package.json << 'WEBUI_EOF'
{
  "name": "obsidian-memory-web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "jest",
    "typecheck": "tsc --noEmit",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^14.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.0",
    "typescript": "^5.3.0",
    "eslint": "^8.56.0",
    "eslint-config-next": "^14.1.0",
    "jest": "^29.7.0"
  }
}
WEBUI_EOF

# Test script
cat > scripts/test-all.sh << 'TEST_EOF'
#!/usr/bin/env bash
set -e

echo "Running backend tests..."
cd backend && pytest tests/ -v && cd ..

echo "Running MCP server tests..."
cd mcp-server && bun test && cd ..

echo "Running web UI tests..."
cd web-ui && npm test && cd ..

echo "All tests passed!"
TEST_EOF
chmod +x scripts/test-all.sh

log_step "Removing template-only files..."

# Remove template-specific files but keep project files
rm -f template-cleanup.sh
rm -rf examples/
rm -f .yamlfmt.yaml
rm -f .yamllint.yml
rm -f LICENSE.md

# Keep but will update: CLAUDE.md, README.md, docs/

log_step "Updating README.md..."
cat > README.md << 'README_EOF'
# Obsidian-Memory

Unified memory management system for Claude Code combining:
- Hook-based auto-capture (cc-obsidian-mem)
- Knowledge graph navigation (Basic Memory)
- Cross-project context library (OpenContext)
- Heavy AI processing for entity/relation extraction

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Claude Code (Hooks) │ Claude.ai (MCP/SSE) │ Web UI (Browser)  │
└──────────┬───────────┴─────────┬───────────┴────────┬──────────┘
           │                     │                    │
           ▼                     ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Server (TypeScript/Bun)                │
│  mem_read │ mem_write │ mem_search │ graph_traverse │ ...      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (Python)                     │
│  Vault Manager │ Graph Engine │ AI Processor │ Search Index    │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Storage: Markdown (truth) + SQLite (index)         │
└─────────────────────────────────────────────────────────────────┘
```

## Development

This project uses the Ralph Wiggum technique for AI-driven development.

### Quick Start

```bash
# Plan mode - analyze gaps and create TODO
./loop.sh plan

# Build mode - implement tasks iteratively
./loop.sh

# Limited iterations
./loop.sh 20
```

### Manual Development

```bash
# Backend
cd backend && pip install -e ".[dev]" && pytest

# MCP Server
cd mcp-server && bun install && bun test

# Web UI
cd web-ui && npm ci && npm test
```

## Project Structure

```
obsidian-memory/
├── specs/              # Specification documents (one per topic)
├── backend/            # FastAPI Python backend
├── mcp-server/         # TypeScript MCP server
├── web-ui/             # Next.js frontend
├── hooks/              # Claude Code lifecycle hooks
├── AGENTS.md           # Operational guide (Ralph Wiggum)
├── IMPLEMENTATION_PLAN.md  # Task tracking
├── PROMPT_plan.md      # Planning mode prompt
├── PROMPT_build.md     # Building mode prompt
└── loop.sh             # Ralph Wiggum loop script
```

## License

MIT
README_EOF

log_step "Updating .gitignore..."
cat >> .gitignore << 'GITIGNORE_EOF'

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
*.egg-info/
dist/
build/
.mypy_cache/
.ruff_cache/
.pytest_cache/

# Node/Bun
node_modules/
.next/
out/

# IDEs
.idea/
.vscode/
*.swp
*.swo

# Environment
.env
.env.local
.env.*.local

# Database
*.db
*.sqlite

# Obsidian vaults (mounted, not committed)
/vaults/

# Session data
/sessions/
GITIGNORE_EOF

if $NO_COMMIT; then
  log_info "Skipping git commit (--no-commit specified)"
else
  log_step "Committing changes..."
  git add .
  git commit -m "Initialize Obsidian-Memory project with Ralph Wiggum structure

- Deploy claude/serena/taskmaster configs from templates
- Create project structure (backend, mcp-server, web-ui, hooks)
- Set up Ralph Wiggum development files
- Add AGENTS.md, IMPLEMENTATION_PLAN.md, prompts
- Create placeholder package files
- Update README and gitignore"
fi

echo ""
log_info "Obsidian-Memory project setup complete!"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo "  1. Write specs in specs/ directory"
echo "  2. Run './loop.sh plan' to generate implementation plan"
echo "  3. Run './loop.sh' to start building"
echo "  4. Or work manually with 'claude' CLI"
echo ""
echo -e "${CYAN}Ralph Wiggum workflow:${NC}"
echo "  specs/ → ./loop.sh plan → IMPLEMENTATION_PLAN.md → ./loop.sh → done"
echo ""
