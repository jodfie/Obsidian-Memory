# Contributing to Obsidian-Memory

Thank you for your interest in contributing to Obsidian-Memory! This guide will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for everyone, regardless of:
- Gender identity and expression
- Sexual orientation
- Disability
- Physical appearance
- Body size
- Race or ethnicity
- Age
- Religion or lack thereof
- Technology choices

### Our Standards

**Positive behaviors:**
- Using welcoming and inclusive language
- Respecting differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards others

**Unacceptable behaviors:**
- Harassment, trolling, or insulting comments
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Violations may be reported to the project maintainers. All complaints will be reviewed and investigated promptly and fairly.

## Getting Started

### Prerequisites

- Python 3.11+
- Bun 1.0+
- Node.js 20+
- Git
- Docker (optional, recommended)

### Fork and Clone

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Obsidian-Memory.git
   cd Obsidian-Memory
   ```
3. Add upstream remote:
   ```bash
   git remote add upstream https://github.com/jodfie/Obsidian-Memory.git
   ```

### Development Setup

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

#### MCP Server
```bash
cd mcp-server
bun install
```

#### Web UI
```bash
cd web-ui
npm ci
```

### Environment Configuration

Create a `.env` file:
```bash
# Backend
VAULT_PATH=/path/to/test/vault
ANTHROPIC_API_KEY=your-test-key
DEBUG=true
LOG_LEVEL=DEBUG

# MCP Server
MCP_TRANSPORT=stdio
OBSIDIAN_MEMORY_API_URL=http://localhost:8765
```

## Development Workflow

### Branching Strategy

- `main` - Stable release branch
- `develop` - Integration branch for features (if exists)
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring

### Creating a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### Making Changes

1. **Write Code**
   - Follow coding standards (see below)
   - Add comments for complex logic
   - Keep functions small and focused

2. **Write Tests**
   - Add unit tests for new functions
   - Add integration tests for new features
   - Ensure all tests pass

3. **Update Documentation**
   - Update README if interface changes
   - Add/update docstrings
   - Update relevant guides in docs/

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "type: brief description

   Detailed explanation if needed

   Co-Authored-By: Your Name <your.email@example.com>"
   ```

### Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): subject

body

footer
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(mcp): add graph similarity tool

Implements hybrid similarity algorithm combining graph structure
and content similarity using embeddings.

Closes #123
```

```
fix(backend): resolve vault permission issues

Fixed bug where vault writes failed due to incorrect UID in Docker
container. Changed ownership to match appuser (UID 1000).

Fixes #456
```

```
docs: add Claude.ai integration guide

Created comprehensive guide with step-by-step setup instructions
and OAuth configuration details.
```

## Pull Request Process

### Before Submitting

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run tests**:
   ```bash
   # Backend
   cd backend && pytest

   # MCP Server
   cd mcp-server && bun test

   # Web UI
   cd web-ui && npm test
   ```

3. **Run linters**:
   ```bash
   # Backend
   cd backend && ruff check . && mypy .

   # MCP Server
   cd mcp-server && bun run lint

   # Web UI
   cd web-ui && npm run lint
   ```

4. **Check formatting**:
   ```bash
   # Backend
   cd backend && ruff format --check .

   # MCP Server
   cd mcp-server && bun run format:check

   # Web UI
   cd web-ui && npm run format:check
   ```

### Submitting PR

1. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request** on GitHub:
   - Use a clear, descriptive title
   - Reference related issues
   - Describe changes in detail
   - Include screenshots for UI changes
   - List breaking changes if any

3. **PR Template**:
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix (non-breaking change which fixes an issue)
   - [ ] New feature (non-breaking change which adds functionality)
   - [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
   - [ ] Documentation update

   ## How Has This Been Tested?
   Describe tests that you ran

   ## Checklist
   - [ ] My code follows the project's coding standards
   - [ ] I have performed a self-review of my own code
   - [ ] I have commented my code, particularly in hard-to-understand areas
   - [ ] I have made corresponding changes to the documentation
   - [ ] My changes generate no new warnings
   - [ ] I have added tests that prove my fix is effective or that my feature works
   - [ ] New and existing unit tests pass locally with my changes
   - [ ] Any dependent changes have been merged and published

   ## Related Issues
   Closes #XXX
   ```

### Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, maintainers will merge

## Coding Standards

### Python (Backend)

**Style:**
- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use [ruff](https://github.com/astral-sh/ruff) for linting and formatting
- Use type hints ([PEP 484](https://peps.python.org/pep-0484/))
- Maximum line length: 100 characters

**Example:**
```python
from typing import Optional

async def get_note(
    note_id: int,
    vault_name: Optional[str] = None,
) -> Note:
    """Get a note by ID.

    Args:
        note_id: The note ID to retrieve
        vault_name: Optional vault name filter

    Returns:
        Note object

    Raises:
        NotFoundError: If note doesn't exist
    """
    # Implementation
    pass
```

**Naming Conventions:**
- `snake_case` for functions and variables
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Private members prefix with `_`

### TypeScript (MCP Server)

**Style:**
- Follow [TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html)
- Use Biome for linting and formatting
- Use explicit types (avoid `any`)
- Maximum line length: 100 characters

**Example:**
```typescript
interface NoteResponse {
  id: number;
  title: string;
  content: string;
  tags: string[];
}

async function getNote(
  noteId: number,
  vaultName?: string
): Promise<NoteResponse> {
  // Implementation
}
```

**Naming Conventions:**
- `camelCase` for functions and variables
- `PascalCase` for classes and interfaces
- `UPPER_CASE` for constants
- Private members prefix with `#` or `_`

### JavaScript/React (Web UI)

**Style:**
- Follow [Airbnb Style Guide](https://github.com/airbnb/javascript)
- Use ESLint and Prettier
- Use functional components and hooks
- Use TypeScript for type safety

**Example:**
```tsx
interface NoteCardProps {
  note: Note;
  onSelect: (id: number) => void;
}

export function NoteCard({ note, onSelect }: NoteCardProps) {
  const handleClick = () => {
    onSelect(note.id);
  };

  return (
    <div className="note-card" onClick={handleClick}>
      <h3>{note.title}</h3>
      <p>{note.content}</p>
    </div>
  );
}
```

### Documentation

**Docstrings (Python):**
```python
def function(arg1: str, arg2: int) -> bool:
    """Short one-line description.

    Longer description if needed. Can span multiple lines.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When validation fails
    """
```

**JSDoc (TypeScript):**
```typescript
/**
 * Short one-line description.
 *
 * Longer description if needed.
 *
 * @param arg1 - Description of arg1
 * @param arg2 - Description of arg2
 * @returns Description of return value
 * @throws {Error} When validation fails
 */
function myFunction(arg1: string, arg2: number): boolean {
  // Implementation
}
```

## Testing Requirements

### Python Tests

```python
import pytest
from app.services import NoteService

@pytest.fixture
def note_service():
    return NoteService()

def test_get_note(note_service):
    """Test getting a note by ID."""
    note = note_service.get_note(1)
    assert note.id == 1
    assert note.title is not None

def test_get_note_not_found(note_service):
    """Test getting non-existent note raises error."""
    with pytest.raises(NotFoundError):
        note_service.get_note(99999)
```

### TypeScript Tests

```typescript
import { describe, test, expect } from 'bun:test';
import { getNote } from './notes';

describe('getNote', () => {
  test('returns note by ID', async () => {
    const note = await getNote(1);
    expect(note.id).toBe(1);
    expect(note.title).toBeTruthy();
  });

  test('throws error for non-existent note', async () => {
    await expect(getNote(99999)).rejects.toThrow();
  });
});
```

### Test Coverage

- Aim for 80%+ code coverage
- All new features must have tests
- All bug fixes must have regression tests
- Run coverage reports:
  ```bash
  # Backend
  pytest --cov=app

  # MCP Server
  bun test --coverage
  ```

## Documentation

### When to Update Docs

- New features added
- API changes
- Configuration changes
- New environment variables
- Breaking changes
- Bug fixes (if user-facing)

### Documentation Files

| File | Update When |
|------|-------------|
| `README.md` | Major features, setup changes |
| `docs/api.md` | New endpoints, parameter changes |
| `docs/mcp-integration.md` | MCP configuration changes |
| `docs/ARCHITECTURE.md` | Design changes |
| `docs/TROUBLESHOOTING.md` | New common issues |
| `CONTRIBUTING.md` | Process changes |

### Documentation Standards

- Use Markdown
- Include code examples
- Add command outputs
- Keep up-to-date with code
- Test all commands/examples

## Community

### Getting Help

- **Documentation**: Start with [docs/](docs/)
- **Issues**: Search [existing issues](https://github.com/jodfie/Obsidian-Memory/issues)
- **Discussions**: Use [GitHub Discussions](https://github.com/jodfie/Obsidian-Memory/discussions)

### Reporting Bugs

Use the bug report template:

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
1. Step one
2. Step two
3. See error

**Expected behavior**
What you expected to happen

**Screenshots**
If applicable, add screenshots

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- Bun version: [e.g., 1.0.20]
- Docker version: [e.g., 24.0.5]

**Additional context**
Any other context
```

### Requesting Features

Use the feature request template:

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
What you want to happen

**Describe alternatives you've considered**
Other solutions you thought about

**Additional context**
Mockups, examples, etc.
```

### Asking Questions

- Check [documentation](docs/) first
- Search [existing discussions](https://github.com/jodfie/Obsidian-Memory/discussions)
- Create new discussion if not found
- Be specific and provide context

## Release Process

(For maintainers)

1. **Update version numbers**:
   - `backend/pyproject.toml`
   - `mcp-server/package.json`
   - `web-ui/package.json`

2. **Update CHANGELOG.md**:
   ```markdown
   ## [1.2.0] - 2024-01-15

   ### Added
   - New feature X

   ### Changed
   - Updated Y

   ### Fixed
   - Bug Z
   ```

3. **Create release**:
   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```

4. **GitHub Release**:
   - Create release from tag
   - Copy CHANGELOG entry
   - Attach binaries if applicable

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors are recognized in:
- Git commit history
- GitHub contributors page
- Release notes (for significant contributions)
- Co-Author tags in commits

## Thank You! 🎉

Your contributions make Obsidian-Memory better for everyone. We appreciate your time and effort!

---

*Questions? Open an issue or discussion on GitHub.*
