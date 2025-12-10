# Technical Writing & Documentation Guide

## Overview
Documentation standards, templates, and style guides for maintaining high-quality technical documentation across all Kubernetes troubleshooting materials.

## Key Responsibilities
- Documentation quality and consistency
- Template creation and maintenance
- Style guide enforcement
- Knowledge base organization

## Documentation Standards

### Writing Guidelines
- **Clarity**: Use simple, direct language
- **Consistency**: Follow established terminology
- **Completeness**: Include all necessary steps
- **Accuracy**: Verify all technical information

### Document Structure
```markdown
# Title (H1)
## Overview (H2)
## Prerequisites (H2)
## Step-by-Step Instructions (H2)
### Substep (H3)
## Troubleshooting (H2)
## Related Resources (H2)
```

### Templates Available
- [Troubleshooting Guide Template](../../templates/troubleshooting-template.md)
- [Runbook Template](../../templates/runbook-template.md)
- [Post-Mortem Template](../../templates/post-mortem-template.md)
- [API Documentation Template](../../templates/api-doc-template.md)

### Style Guide
- **Code blocks**: Use syntax highlighting
- **Commands**: Prefix with `$` for shell commands
- **File paths**: Use backticks for inline code
- **Links**: Use descriptive link text
- **Images**: Include alt text for accessibility

### Content Review Checklist
- [ ] Technical accuracy verified
- [ ] Steps tested and validated
- [ ] Links functional and current
- [ ] Grammar and spelling checked
- [ ] Formatting consistent
- [ ] Accessibility guidelines followed

### Documentation Metrics
- **Completeness**: All scenarios covered
- **Usability**: Clear step-by-step instructions
- **Findability**: Proper tagging and categorization
- **Maintainability**: Regular review and updates

## Content Organization

### Information Architecture
```
docs/
├── getting-started/     # Onboarding materials
├── troubleshooting/     # Issue-specific guides
├── reference/           # API docs, CLI references
├── tutorials/           # Step-by-step learning
└── best-practices/      # Recommendations and patterns
```

### Tagging System
- **Difficulty**: beginner, intermediate, advanced
- **Platform**: aks, eks, gke, kubernetes
- **Component**: networking, storage, security, monitoring
- **Role**: architect, engineer, devops, sre

## Quality Assurance
Regular documentation audits ensure:
- Technical accuracy
- Link validity
- Content freshness
- User feedback integration
