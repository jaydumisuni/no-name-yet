from __future__ import annotations

from main_review.offline_investigation import _executed_test_paths, _workflow_run_commands


def test_double_quoted_inline_run_command_is_decoded() -> None:
    workflow = '''
name: quoted-run
on:
  pull_request:
    paths:
      - tests/test_required.py
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: "pytest tests/test_required.py"
'''

    commands = _workflow_run_commands(workflow)

    assert [command.text for command in commands] == ["pytest tests/test_required.py"]
    assert _executed_test_paths(workflow) == {"tests/test_required.py"}


def test_single_quoted_inline_run_command_is_decoded() -> None:
    workflow = '''
name: quoted-run
on:
  pull_request:
    paths:
      - tests/test_required.py
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: 'python -m pytest tests/test_required.py'
'''

    commands = _workflow_run_commands(workflow)

    assert [command.text for command in commands] == ["python -m pytest tests/test_required.py"]
    assert _executed_test_paths(workflow) == {"tests/test_required.py"}
