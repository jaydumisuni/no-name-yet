# Sergeant 0.3 Command Center review closure

This document closes the findings raised by Sergeant Main Review for the Command Center integration.

## Decision

The Command Center remains part of the 0.3 release line. The implementation is accepted only with explicit evidence for the automation changes, exported runtime contracts, and single-mission execution boundary described below.

## High-risk automation paths

The earlier Command Center pull request changed:

- `.github/workflows/multiplatform-proof.yml`
- `scripts/build-command-center-preview.js`

These paths were correctly classified as high risk because they influence proof and packaging. Their intended impact is limited to build-time verification:

- They do not execute target-repository code.
- They do not alter production application state.
- They do not receive write credentials.
- The preview builder reads the committed Command Center HTML, CSS, and JavaScript and writes a deterministic local proof page.
- The workflow renders the page at desktop and compact IDE sizes, clicks every major navigation surface, checks JavaScript syntax, packages the VSIX and Python artifacts, builds the JetBrains plugin, and verifies that the shared UI resources are present in the plugin package.
- Marketplace credentials remain confined to separate publication workflows.

Rollback is straightforward: revert the proof workflow and preview-builder commits without changing the Sergeant review engine or IDE runtime.

## Exported VS Code contracts

The exported and cross-file functions in `src/vscode/actions.js`, `src/vscode/results.js`, and `src/vscode/extension.js` are intentional boundaries:

- `createActions` supplies the command manifest used by the extension runtime.
- Result parsing and rendering functions are consumed by the review panel and Command Center provider.
- The extension entry point registers commands and routes them to the shared Sergeant CLI.

Package-contract tests verify the command IDs, action mappings, result-panel sections, Command Center bridge messages, and bundled resources. Browser proof verifies the visible controls and navigation.

## Single-mission execution boundary

The Command Center now enforces one active mission per IDE host.

- The shared UI locks every mission-launch control immediately after the first accepted launch.
- A second launch is stopped before it can reach the host.
- The lock is released only when the IDE host reports that no mission is running.
- VS Code also keeps an authoritative active child-process gate, so command-palette or duplicate webview requests cannot start a parallel mission.
- Extension deactivation terminates an active child process rather than leaving an orphan review.

This protects report ownership, mission progress, latest-result state, and Evidence Locker history from overlapping-run races.

## Acceptance evidence

The follow-up is acceptable when all of the following are green:

1. Python package and contract tests.
2. JavaScript syntax checks.
3. Browser proof at desktop and compact IDE widths.
4. Duplicate-launch browser test proving only one `run` message reaches the host.
5. VSIX packaging.
6. JetBrains compilation and shared-resource inspection.
7. Sergeant Main Review consensus with no unanswered major finding.

The engineering rule remains: **finish, review, freeze, then prove.**
