# Technical Writing & Documentation Guide
Keep docs clear, consistent, and testable. This is the style spine for the repo.

## Your Lens
- Enforce clarity and accuracy; remove ambiguity.
- Maintain and evolve templates; guard the voice and structure.
- Keep links, commands, and outputs tested.

## Writing Rules (O’Reilly-style)
- Be direct and task-first; avoid fluff.
- Show runnable commands with expected context.
- Prefer bullets and short paragraphs; one idea per line.
- Verify every command and link; note prerequisites.

## Standard Structure
```markdown
# Title (H1)
## Overview
## Prerequisites
## Steps (ordered)
## Troubleshooting
## Related Resources
```

## Templates
- [Troubleshooting Guide](../../templates/troubleshooting-template.md)
- [Runbook](../../templates/runbook-template.md)
- [Post-Mortem](../../templates/post-mortem-template.md)
- [API Documentation](../../templates/api-doc-template.md)

## Review Checklist
- Technical accuracy verified and commands tested.
- Links work; file paths correct.
- Grammar/spelling clean; consistent terminology.
- Accessibility: alt text for images; code fenced with language.

## Taxonomy (tags)
- Difficulty: beginner | intermediate | advanced
- Platform: aks | eks | gke | kubernetes
- Component: networking | storage | security | monitoring | compute
- Role: architect | engineer | devops | sre
