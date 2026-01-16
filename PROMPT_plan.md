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
