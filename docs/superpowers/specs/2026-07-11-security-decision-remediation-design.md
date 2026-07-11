# Security Decision Remediation Design

**Date:** 2026-07-11
**Status:** Approved for implementation
**Scope:** Remediate audit findings 1-5, block unsafe roadmap work, and return the R2 multi-target ADR for revision.

## Goals

1. Make Nuclei filtering a pre-execution security boundary.
2. Make built distributions contain every runtime resource used by Web and Nuclei features.
3. Enforce R4 ownership confirmation in the core without changing public method signatures or return types.
4. Preserve operational failures instead of converting them into not-found or no-risk responses.
5. Prevent non-loopback Web exposure with default credentials.
6. Block Nuclei synchronization, v0.0.56 WSGI work, and AssetRegistry until their prerequisites are verified.

## Non-Goals

- Implement Nuclei synchronization, WSGI migration, or AssetRegistry.
- Add an environment variable or configuration switch that permits unconfirmed scans.
- Verify legal ownership of an IP address or domain automatically.
- Redesign the complete Web authentication system.

## 1. Nuclei Pre-Execution Policy

`NucleiAdapter.scan()` must never pass an unreviewed template source to the Nuclei process.

Before invoking any Nuclei subprocess, the adapter resolves the requested local template file or directory and parses candidate YAML files with `yaml.safe_load`. URL sources, missing paths, unreadable files, invalid YAML, workflows, and templates without a non-empty `info.tags` list are rejected. Symlinks are resolved before inspection. An invalid source fails the scan rather than silently falling back to another template directory.

A template is executable only when every declared tag belongs to `NUCLEI_ALLOWED_TAGS` and no tag belongs to `NUCLEI_BLOCKED_TAGS`. Unknown tags are denied. Caller-supplied `tags` may narrow the allowed set but may not introduce a tag outside `NUCLEI_ALLOWED_TAGS`.

The subprocess command receives explicit reviewed template files through repeated `-t <file>` arguments. It never receives the original directory or URL. Rejected files are skipped, and each allowed or rejected file produces an audit record containing its resolved path, SHA-256 digest when readable, normalized tags, and decision reason. Output filtering remains as defense in depth, not as the primary gate.

If no approved template remains, scanning returns `ScanStatus.FAILED` without invoking any Nuclei subprocess. Local template validation runs before the Nuclei availability probe, so invalid input cannot trigger even a version probe. Tests must prove neither the version probe nor the scan command is invoked.

## 2. Distribution Integrity

Setuptools package data must include:

- `lightshield/rules/*.json`
- `lightshield/nuclei-templates/**/*`
- `lightshield/web/templates/**/*`
- `lightshield/web/static/**/*`
- `lightshield/web/locales/*.json`

The project must build a wheel and validate its archive contents. A smoke test installs or extracts the wheel into an isolated directory, imports the installed package without using the source tree, creates the Flask app, loads both locales, resolves the OpenAPI file, and confirms the Nuclei template directory exists.

The build must continue to use `pyproject.toml` as the authoritative metadata source. `setup.py` becomes a compatibility shim containing only `setup()` and no duplicated metadata, so direct and PEP 517 builds resolve the same PEP 621 version and dependencies.

## 3. R4 Fail-Closed Compatibility Envelope

The existing public signatures remain stable, including `confirm_ownership: bool = False`. No legacy bypass is added.

For synchronous core calls, a missing confirmation returns the existing `ScanResult` type with `status=FAILED`, the original target, and an actionable R4 error explaining that callers must pass `confirm_ownership=True` only after obtaining authorization. It does not raise a new exception and does not invoke adapters.

For asynchronous core calls, submission remains type-compatible: it returns a task ID and records an immediately failed task state containing the same R4 migration message. No worker thread or adapter starts.

The Web API validates confirmation before submission and returns HTTP 400. CLI behavior remains interactive and continues passing `True` only after confirmation. Tests cover direct core use, async use, Web use, confirmed use, and proof that adapters were not called.

## 4. Facade Failure Semantics

Introduce explicit domain exceptions under the core boundary:

- `ScanRepositoryError`: repository creation/query failures.
- `ScanDataError`: persisted scan data cannot be reconstructed.
- `RecommendationError`: rule loading or recommendation generation fails.

`load_scan()` returns `None` only when the repository successfully reports that the scan ID does not exist. It raises the corresponding domain exception for operational or data failures. `get_recommendations()` returns an empty list only for a valid scan with no findings or no matching rules; it raises `RecommendationError` for rule-engine failures and propagates load failures.

Web routes map not-found to 404, repository/service failures to 503, and corrupt persisted data to 500. Hardening must never report "no action required" when recommendation generation failed.

## 5. Web Credential Exposure Gate

Local development remains backward compatible on loopback addresses. `lightshield serve` may use the documented default credentials only when binding to a loopback host such as `127.0.0.1`, `::1`, or `localhost`.

For a non-loopback bind, startup fails before creating the server if either effective credential is still the built-in default or is empty. The error explains how to set `LS_WEB_USERNAME` and `LS_WEB_PASSWORD`. This validation is a reusable pure function with focused tests.

The login template must not prefill the password. Existing authentication and CSRF behavior remain unchanged.

## 6. Roadmap Blocks

The project governance documents must record these enforceable states:

- **Nuclei synchronization: BLOCKED** until pre-execution template validation, command-level bypass tests, provenance logging, and distribution smoke tests pass.
- **v0.0.56 WSGI: BLOCKED** until package resources, non-loopback credential validation, explicit operational error semantics, and a multi-process task-state design are verified.
- **AssetRegistry: BLOCKED** until the R2 ADR is revised and accepted again.

The decision log must distinguish `Accepted`, `Implemented`, `Verified`, `Blocked`, and `Superseded`; a check mark alone must not imply implementation.

## 7. R2 ADR Re-Review

`docs/adr-v052-r2-multi-target-redesign.md` returns from `Accepted` to `Proposed - Changes Required`.

The current design is rejected because it claims per-asset confirmation while later permitting one list-level confirmation, and because a public CIDR can be expanded into a JSON list to bypass the policy's intent.

The replacement ADR must separately define:

- Private-address batch scanning, with bounded targets and list preview.
- Public targets, with authorization evidence stronger than a single batch boolean.
- Atomic target normalization and duplicate/range-expansion detection.
- Audit records that bind authorization evidence to the exact immutable target set.
- Revocation, expiry, and re-confirmation behavior after a target list changes.

No AssetRegistry schema or implementation may make `ownership_confirmed: true` a durable authorization fact before the replacement ADR is accepted.

## 8. Verification

Each production behavior follows a separate red-green-refactor cycle. Required final verification:

1. Focused Nuclei, packaging, core, Web, and CLI tests.
2. Full `pytest` suite.
3. Ruff and Mypy.
4. Wheel build plus installed-artifact smoke test.
5. Pre-commit gates without auto-fixing unrelated user changes.
6. `graphify update .` after code and documentation changes.

## Compatibility Summary

The remediation preserves public call signatures, result classes, task IDs, CLI flags, local Web defaults, and confirmed-scan behavior. It intentionally removes only the unsafe behavior of executing a scan without confirmed authorization. External callers receive structured failures and actionable migration text instead of exceptions or silent execution.
