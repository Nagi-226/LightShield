# Security Decision Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the five approved security remediations, block unsafe roadmap work, and return the R2 multi-target ADR for revision without breaking public method signatures.

**Architecture:** Security checks move to the earliest trusted boundary: local Nuclei templates are reviewed before any subprocess, R4 is enforced in `LightShieldCore`, facade failures use typed exceptions, and non-loopback Web serving validates credentials before startup. Distribution and governance tests verify that source-tree success cannot hide broken wheels or stale decision states.

**Tech Stack:** Python 3.10+, pytest, Flask, PyYAML, setuptools/PEP 621, PowerShell build verification, graphify.

## Global Constraints

- Preserve `run_scan(..., confirm_ownership: bool = False) -> ScanResult` and `submit_scan(...) -> str` signatures.
- Do not add a legacy flag or environment variable that permits unconfirmed scans.
- Nuclei template review must complete before any Nuclei subprocess call.
- Do not implement Nuclei synchronization, WSGI migration, or AssetRegistry in this plan.
- Do not stage or commit pre-existing user changes outside files explicitly listed by each task.

---

### Task 1: Enforce roadmap and ADR blocks

**Files:**
- Modify: `docs/adr-v052-r2-multi-target-redesign.md`
- Modify: `.guardrails/PROGRESS.md`
- Modify: `.guardrails/VERSION_ROADMAP.md`
- Modify: `docs/DECISION_LOG.md`
- Test: `tests/test_decision_guards.py`

**Interfaces:**
- Produces: machine-checkable status markers `Proposed - Changes Required` and `BLOCKED` for the three gated workstreams.

- [ ] **Step 1: Write failing governance tests**

```python
def test_r2_adr_is_returned_for_revision():
    text = Path("docs/adr-v052-r2-multi-target-redesign.md").read_text(encoding="utf-8")
    assert "Proposed - Changes Required" in text

def test_unsafe_roadmap_work_is_blocked():
    progress = Path(".guardrails/PROGRESS.md").read_text(encoding="utf-8")
    assert "Nuclei synchronization: BLOCKED" in progress
    assert "v0.0.56 WSGI: BLOCKED" in progress
    assert "AssetRegistry: BLOCKED" in progress
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_decision_guards.py -q`
Expected: FAIL because the ADR remains Accepted and roadmap markers do not exist.

- [ ] **Step 3: Apply the block states**

Change the R2 ADR status to `Proposed - Changes Required`, add a rejection note for list-level public authorization, and add explicit unblock criteria copied from the approved spec. Mark Nuclei synchronization, v0.0.56 WSGI, and AssetRegistry as `BLOCKED` in both roadmap documents. Update decision #27 in the decision log so one accepted ADR does not imply all three remain accepted.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_decision_guards.py -q`
Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```bash
git add tests/test_decision_guards.py docs/adr-v052-r2-multi-target-redesign.md .guardrails/PROGRESS.md .guardrails/VERSION_ROADMAP.md docs/DECISION_LOG.md
git commit -m "docs: block unsafe roadmap work"
```

### Task 2: Move Nuclei filtering before execution

**Files:**
- Modify: `lightshield/adapters/nuclei_adapter.py`
- Modify: `tests/test_nuclei_adapter.py`

**Interfaces:**
- Produces: `NucleiAdapter._review_template_source(source: str, requested_tags: object) -> list[str]`.
- Produces: strict `is_template_safe(tags: list[str]) -> tuple[bool, str]` where every tag must be allowed.

- [ ] **Step 1: Write failing pre-execution tests**

Add tests proving that a caller cannot pass `tags="exploit"`, a mixed `detection,exploit` template is never executed, URL and workflow sources are rejected before `nuclei -version`, unknown tags are rejected, and a directory command contains repeated explicit `-t <reviewed-file>` pairs rather than the directory.

```python
with patch("lightshield.adapters.nuclei_adapter.subprocess.run") as run:
    result = adapter.scan("127.0.0.1", templates=str(template_dir), tags="exploit")
assert result.status == ScanStatus.FAILED
run.assert_not_called()
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_nuclei_adapter.py -q`
Expected: FAIL because caller tags currently override the whitelist and review occurs after execution.

- [ ] **Step 3: Implement the minimal reviewer**

Use `Path.resolve()`, `yaml.safe_load`, and SHA-256. Reject non-local sources and invalid source paths. Enumerate `.yaml`/`.yml` files, normalize tags, allow only templates whose complete tag set is a subset of `NUCLEI_ALLOWED_TAGS`, intersect with an optional allowed caller subset, reject workflows, and log each decision with path/digest/tags/reason. Build the Nuclei command from reviewed files only.

- [ ] **Step 4: Verify GREEN and focused regression**

Run: `python -m pytest tests/test_nuclei_adapter.py tests/test_interface_compliance.py -q`
Expected: PASS.

- [ ] **Step 5: Commit only Nuclei files**

```bash
git add lightshield/adapters/nuclei_adapter.py tests/test_nuclei_adapter.py
git commit -m "fix: validate nuclei templates before execution"
```

### Task 3: Repair wheel runtime resources and metadata

**Files:**
- Modify: `pyproject.toml`
- Modify: `setup.py`
- Create: `scripts/verify_wheel.py`
- Create: `tests/test_distribution.py`

**Interfaces:**
- Produces: `verify_wheel(path: Path) -> list[str]`, raising `WheelVerificationError` for missing runtime resources.

- [ ] **Step 1: Write failing archive tests**

Test required archive members for Web templates, locales, OpenAPI, Swagger assets, rules, and the Nuclei template directory. Test that `setup.py` contains no version or dependency metadata.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_distribution.py -q`
Expected: FAIL because current package data contains only `rules/*.json`.

- [ ] **Step 3: Implement package data and wheel verifier**

Add recursive Web/Nuclei resource patterns to `[tool.setuptools.package-data]`. Reduce `setup.py` to a compatibility shim importing and calling `setuptools.setup`. Implement zip archive checks plus an extracted-package subprocess smoke test that removes the repository root from `PYTHONPATH`.

- [ ] **Step 4: Verify GREEN against a real wheel**

Run: `python -m pytest tests/test_distribution.py -q`

Run: `python -m pip wheel . --no-deps --no-build-isolation --wheel-dir build/audit-wheel`

Run: `python scripts/verify_wheel.py build/audit-wheel/lightshield-*.whl`

Expected: tests PASS and verifier reports all required resources present.

- [ ] **Step 5: Commit only distribution files**

```bash
git add pyproject.toml setup.py scripts/verify_wheel.py tests/test_distribution.py
git commit -m "fix: include runtime resources in wheel"
```

### Task 4: Enforce R4 fail-closed while preserving API shapes

**Files:**
- Modify: `lightshield/core.py`
- Modify: `lightshield/web/routes.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_web.py`
- Modify: `lightshield/web/static/openapi.json`

**Interfaces:**
- Produces: module constant `R4_CONFIRMATION_REQUIRED` used by synchronous, asynchronous, and Web failure paths.

- [ ] **Step 1: Write failing core and Web tests**

Test that unconfirmed `run_scan()` returns `ScanResult(FAILED)` without calling an adapter, unconfirmed `submit_scan()` returns a task ID already in `failed` state without starting a thread, and `/api/scan` returns 400 without calling core submission. Confirmed behavior must remain unchanged.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_core.py tests/test_web.py -q`
Expected: FAIL because core and Web currently continue unconfirmed scans.

- [ ] **Step 3: Implement fail-closed compatibility behavior**

Keep method signatures and return types unchanged. Return a structured failed `ScanResult` synchronously. Store an immediately failed `_TaskInfo` asynchronously without constructing a thread. Reject missing/false confirmation in the Web route before calling core and update OpenAPI to make the field required.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_core.py tests/test_web.py tests/test_cli.py -q`
Expected: PASS.

- [ ] **Step 5: Commit only R4 files**

```bash
git add lightshield/core.py lightshield/web/routes.py lightshield/web/static/openapi.json tests/test_core.py tests/test_web.py
git commit -m "fix: enforce ownership confirmation in core"
```

### Task 5: Preserve facade operational failures

**Files:**
- Modify: `lightshield/core.py`
- Modify: `lightshield/web/routes.py`
- Modify: `lightshield/web/pages.py`
- Modify: `tests/test_core.py`
- Modify: `tests/test_web.py`
- Modify: `tests/test_web_pages.py`

**Interfaces:**
- Produces: `ScanRepositoryError`, `ScanDataError`, and `RecommendationError` from `lightshield.core`.

- [ ] **Step 1: Rewrite tests to require typed failures**

Repository failures must raise `ScanRepositoryError`; corrupt stored data must raise `ScanDataError`; rule failures must raise `RecommendationError`. Web routes must map these to 503/500 and never return “no action required.” Pages must render an operational error state instead of a false empty state.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_core.py tests/test_web.py tests/test_web_pages.py -q`
Expected: FAIL because existing facade methods return `None` or `[]`.

- [ ] **Step 3: Implement typed exceptions and route mapping**

Define the three exceptions next to core task types. Return `None` only for a successful repository miss. Raise typed exceptions with exception chaining. Catch them at Web boundaries and emit stable JSON/status codes or page error messages.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_core.py tests/test_web.py tests/test_web_pages.py -q`
Expected: PASS.

- [ ] **Step 5: Commit only facade files**

```bash
git add lightshield/core.py lightshield/web/routes.py lightshield/web/pages.py tests/test_core.py tests/test_web.py tests/test_web_pages.py
git commit -m "fix: preserve facade failure semantics"
```

### Task 6: Refuse exposed Web serving with default credentials

**Files:**
- Modify: `lightshield/web/auth.py`
- Modify: `lightshield/cli.py`
- Modify: `lightshield/web/templates/login.html`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_web.py`

**Interfaces:**
- Produces: `validate_web_exposure(host: str, username: str, password: str) -> tuple[bool, str]`.

- [ ] **Step 1: Write failing exposure tests**

Test loopback addresses with defaults are accepted; `0.0.0.0`, `::`, and public/private interface addresses with default or empty credentials are rejected; configured non-default credentials are accepted; login HTML contains no password value.

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_cli.py tests/test_web.py -q`
Expected: FAIL because no startup credential gate exists and the password is prefilled.

- [ ] **Step 3: Implement the startup gate**

Use `ipaddress.ip_address(...).is_loopback` plus `localhost` handling. Expose effective credentials from the auth module without logging their values. Validate before `create_app()`/`app.run()` and return exit code 1 with environment-variable guidance. Remove the password value attribute from the template.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_cli.py tests/test_web.py -q`
Expected: PASS.

- [ ] **Step 5: Commit only credential files**

```bash
git add lightshield/web/auth.py lightshield/cli.py lightshield/web/templates/login.html tests/test_cli.py tests/test_web.py
git commit -m "fix: block exposed web defaults"
```

### Task 7: Full verification and graph refresh

**Files:**
- Modify: `graphify-out/*` through `graphify update .`

**Interfaces:**
- Consumes: all prior task behavior.
- Produces: verified source, wheel, governance state, and updated knowledge graph.

- [ ] **Step 1: Run full tests**

Run: `python -m pytest -q`
Expected: all tests pass with only documented skips.

- [ ] **Step 2: Run static checks**

Run: `python -m ruff check lightshield tests scripts`

Run: `python -m mypy lightshield --config-file pyproject.toml`

Expected: both pass.

- [ ] **Step 3: Run repository gates**

Run: `pre-commit run --all-files`
Expected: all hooks pass. Review any auto-fix before staging; do not stage unrelated user changes.

- [ ] **Step 4: Rebuild and verify wheel**

Run the Task 3 wheel commands from a clean temporary directory and verify installed resources.

- [ ] **Step 5: Refresh graph**

Run: `graphify update .`
Expected: graph update succeeds.

- [ ] **Step 6: Record final status**

Update the remediation status in `docs/DECISION_LOG.md` from planned to verified only for checks with fresh evidence. Leave findings 7-10 open unless separately remediated.

- [ ] **Step 7: Commit verification metadata only**

```bash
git add graphify-out docs/DECISION_LOG.md
git commit -m "chore: verify security remediation"
```
