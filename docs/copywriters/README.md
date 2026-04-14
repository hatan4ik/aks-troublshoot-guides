# Technical Writing & Documentation Guide

Keep docs clear, consistent, and testable. This is the style spine for the repo and should be used with the book structure in [BOOK.md](../../BOOK.md).

## Your Lens
- Enforce clarity and accuracy; remove ambiguity.
- Maintain and evolve templates; guard the voice and structure.
- Keep links, commands, and outputs tested.

## Writing Rules (O’Reilly-style)
- Be direct and task-first; avoid fluff.
- Show runnable commands with expected context.
- Prefer bullets and short paragraphs; one idea per line.
- Verify every command and link; note prerequisites.
- Prefer "Kubernetes" in prose and reserve "K8s" for code, command output, or package names.
- Use "Argo CD" and "Flux CD" consistently.
- Use "bare metal" as a normal noun and "Bare Metal" only in titles.
- Avoid emoji-heavy headings in book chapters. They are acceptable in lab output or CLI output, but the manuscript should read cleanly in plain text.
- Avoid vague claims such as "robust," "comprehensive," or "best practice" unless the text proves the claim.

## Standard Structure
```markdown
# Title (H1)
## When to Use This
## Mental Model
## Fast Triage
## Failure Matrix
## Fix Safely
## Verify
## Provider Notes
## Interview Signals
## Related Reading
```

## Templates
- [Book Spine](../../BOOK.md)
- [Command Conventions](../COMMAND-CONVENTIONS.md)
- [Glossary](../GLOSSARY.md)
- [Troubleshooting Guide](../../templates/troubleshooting-template.md)
- [Runbook](../../templates/runbook-template.md)
- [Post-Mortem](../../templates/post-mortem-template.md)
- [API Documentation](../../templates/api-doc-template.md)

## Review Checklist
- Technical accuracy verified and commands tested.
- Links work; file paths correct.
- Grammar/spelling clean; consistent terminology.
- Accessibility: alt text for images; code fenced with language.
- Every state-changing command has a safety note or dry-run equivalent where possible.
- Each chapter has a clear reader entry point and a verification step.
- Provider-specific content is clearly labeled instead of mixed into generic Kubernetes guidance.

## Taxonomy (tags)
- Difficulty: beginner | intermediate | advanced
- Platform: aks | eks | gke | kubernetes
- Component: networking | storage | security | monitoring | compute
- Role: architect | engineer | devops | sre
