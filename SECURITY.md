# Security Policy

## Supported Versions

Security fixes are applied to the latest version on the default branch. Older packaged builds may not receive fixes.

## Reporting a Vulnerability

Please report security issues privately through [GitHub Security Advisories](https://github.com/roanpy/file-organizer/security/advisories/new). Do not open a public issue containing API keys, local filesystem paths, configuration files, logs, or proof-of-concept data from a real machine.

Include:

- affected version or commit;
- operating system and installation method;
- minimal reproduction steps using synthetic files and paths;
- impact and any proposed mitigation.

## Privacy Boundaries

- Configuration and history stay under the user's local application directory.
- Provider keys are read from local configuration and are masked in API responses.
- AI is optional and disabled by default.
- Batch path suggestions send local directory identifiers and folder labels, not absolute filesystem paths.
- Do not attach `~/.software_organizer/`, application logs, or real file listings to issues.
