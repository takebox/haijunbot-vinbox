---
name: security
description: Triggered when secure coding or vulnerability protection is needed. Triggered whenever the user mentions "secure coding", "secure programming", "vulnerability protection", "security standards", "code security", "security practices", "secure development". Not triggered: feature development without security concerns; performance optimization; code refactoring without security implications.
---

# Secure Coding Standards

## Basic Principles

- **Input validation**: All user input must be validated to prevent injection attacks (SQL injection, XSS, command injection, etc.)
- **Authentication and session management**: Strong authentication mechanisms must be used, and session tokens managed properly
- **Access control**: The principle of least privilege must be enforced to ensure users can only access the resources they need
- **Encrypted storage**: Sensitive data (passwords, keys, personally identifiable information) must be stored encrypted
- **Secure communication**: TLS/HTTPS must be used for network communication

## Common Vulnerability Protection

### SQL Injection Protection

```python
# Correct: use parameterized queries
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# Wrong: string concatenation
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
```

### XSS Protection

- Output encoding: content output to HTML must be encoded
- Use the Content-Security-Policy header
- Avoid using `dangerouslySetInnerHTML` (React) or `innerHTML` (vanilla JS)

### CSRF Protection

- Use CSRF tokens
- Validate the Referer response header
- Use POST requests for sensitive operations

## Security Configuration

- **Dependency management**: Regularly update dependency libraries to fix known vulnerabilities
- **Error handling**: Do not leak sensitive error information to users
- **Logging**: Record security-related events, but do not log sensitive data
- **Secure by default**: The default configuration should be a secure configuration

## Secure Development Process

1. Threat modeling: perform threat modeling at the requirements stage
2. Secure coding: follow secure coding standards
3. Security testing: perform SAST, DAST, and penetration testing
4. Security review: focus on security issues during code review
5. Secure deployment: ensure the deployment environment is secure

## Checklist

- [ ] All user input has been validated
- [ ] Parameterized queries are used
- [ ] Output has been encoded
- [ ] HTTPS is used
- [ ] Passwords are stored hashed
- [ ] Session management is secure
- [ ] Error messages do not leak sensitive data
- [ ] Dependency libraries are up to date
