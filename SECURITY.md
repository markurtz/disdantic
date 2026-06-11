<!--
Copyright 2026 markurtz

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Security Policy for Disdantic

We take the security of Disdantic seriously. This document outlines our security policies, supported versions, and how to responsibly disclose a vulnerability.

## Supported Versions

Please check the table below for the versions of Disdantic that are currently being supported with security updates.

| Version   | Supported          |
| :-------- | :----------------- |
| `0.1.x`   | :white_check_mark: |
| `< 0.1.0` | :x:                |

## Reporting a Vulnerability

> [!IMPORTANT]
> **Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

If you discover a security vulnerability, please bring it to our attention right away using one of the following methods:

1. **GitHub Security Advisories (Preferred):** Use the "Report a vulnerability" button on the **[Security tab](https://github.com/markurtz/disdantic/security/advisories)** of this repository.
1. **Direct Message:** Send a message directly to the maintainer's GitHub user account, **[markurtz](https://github.com/markurtz)**, if applicable or through other provided direct pathways for the user.

### What to Include in Your Report

To help us resolve the issue quickly, please include the following information:

- **Type of vulnerability** (e.g., arbitrary code execution, path traversal, command injection).
- **Detailed description** of the vulnerability and its potential impact.
- **Step-by-step instructions** to reproduce the issue.
- **Proof of Concept (PoC)** code or screenshots, if available.
- **Environment details** (e.g., version of Disdantic, OS, Python version, relevant configurations).

## Triage and Resolution Process

We will handle your report with strict confidentiality. Our process is as follows:

1. **Acknowledgment:** We will respond to your report as soon as possible, usually within a few business days.
1. **Triage:** We will investigate the issue and determine its validity and severity. We may contact you for further clarification.
1. **Fix:** If the vulnerability is verified, we will develop and test a patch.
1. **Disclosure:** We will coordinate with you to publicly disclose the vulnerability once a fix is released. We will publicly acknowledge your responsible disclosure, if you wish.

## Scope

**In Scope:**

- Vulnerabilities within the core Disdantic codebase.
- Security issues resulting from our default configurations or execution paths.

**Out of Scope:**

- Theoretical issues without a reproducible PoC.
- Vulnerabilities in third-party dependencies that are not exploitable through Disdantic.
- Issues requiring the victim to intentionally clone and run Disdantic against a malicious, untrusted Git repository, unless it leads to unexpected system compromise beyond the expected permissions.

*(Note: We currently do not operate a bug bounty program. Disclosures are greatly appreciated but are not eligible for financial rewards at this time.)*
