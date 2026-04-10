# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AnvilOps, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email: **justin.conover@gmail.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

| Action | Target |
|--------|--------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix for critical issues | Within 14 days |
| Fix for high issues | Within 30 days |

## Scope

The following are in scope:
- AnvilOps API (FastAPI backend)
- AnvilOps Frontend (Next.js)
- Terraform modules and configurations
- Helm charts and Kubernetes manifests
- Ansible playbooks and Puppet manifests
- CI/CD pipeline configurations
- Authentication and authorization flows

## Security Measures

AnvilOps implements the following security controls:

- **Authentication**: AWS Cognito with JWT (RS256) verification on both frontend and backend
- **Authorization**: Role-based access control with 5 hierarchical roles
- **Transport**: HTTPS-only with HSTS in production
- **Secrets**: AWS Secrets Manager with KMS encryption; no plaintext credentials in code
- **Headers**: CSP, X-Frame-Options (DENY), X-Content-Type-Options, Referrer-Policy
- **Rate Limiting**: SlowAPI (100 requests/minute default)
- **Container Security**: Non-root users, multi-stage builds, Trivy scanning
- **Kubernetes**: Pod Security (restricted), NetworkPolicies (default-deny), IRSA
- **Infrastructure**: IMDSv2 enforced, KMS encryption at rest, VPC isolation
- **CI/CD**: GitHub Actions pinned to SHAs, OIDC-based AWS auth, no long-lived keys
- **Audit**: Comprehensive audit logging with IP validation

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x (current) | Yes |

## Acknowledgments

We appreciate the security research community's efforts in helping keep AnvilOps secure.
