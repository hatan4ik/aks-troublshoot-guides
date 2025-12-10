# [API Name] Documentation

## Overview
- Purpose and audience
- Auth model (RBAC, tokens)
- Rate limits and SLAs

## Base URL
`https://api.example.com`

## Authentication
- Method (Bearer, mTLS, AWS IAM/Azure AD)
- How to obtain/refresh credentials

## Endpoints
### [METHOD] /path/{param}
- **Description**: What it does
- **Path Params**: `{param}` – description/type
- **Query Params**: optional filters
- **Request Body** (if any):
```json
{
  "field": "value"
}
```
- **Responses**:
  - 200: Success payload
  - 4xx: Client errors
  - 5xx: Server errors

## Examples
```bash
curl -H "Authorization: Bearer $TOKEN" https://api.example.com/path/123
```

## Error Handling
- Common error codes and guidance
- Retry/backoff policy

## Versioning & Deprecation
- Current version, headers, date-based deprecation policy

## Changelog
- Notable changes by version

---
**Difficulty**: [Beginner/Intermediate/Advanced]  
**Platform**: [AKS/EKS/GKE/Kubernetes]  
**Component**: [Networking/Storage/Security/Compute]  
**Last Updated**: [Date]  
**Reviewed By**: [Team/Role]
