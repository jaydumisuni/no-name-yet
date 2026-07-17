from __future__ import annotations

from pathlib import Path

import pytest

from main_review.capability_engine import run_capability_engine
from main_review.capability_policy import normalize_capability_review
from main_review.verification import verify_repository_standard


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _review(root: Path, path: str, text: str, test_path: str, test_text: str) -> dict[str, object]:
    _write(root, path, text)
    _write(root, test_path, test_text)
    return normalize_capability_review(
        run_capability_engine(root, [path, test_path]),
        root,
    )


def _actionable(packet: dict[str, object]) -> list[dict[str, object]]:
    return [
        item
        for item in packet["findings"]  # type: ignore[index]
        if isinstance(item, dict) and item.get("severity") in {"blocker", "major", "minor"}
    ]


def test_go_query_taint_detects_concatenation_and_accepts_binding(tmp_path: Path) -> None:
    unsafe = _review(
        tmp_path,
        "internal/users.go",
        """package internal
func user(db DB, r *Request) Rows {
    id := r.URL.Query().Get("id")
    return db.Query("SELECT * FROM users WHERE id = " + id)
}
""",
        "internal/users_test.go",
        "package internal\nfunc TestUser() {}\n",
    )
    assert unsafe["verdict"] == "NEEDS WORK"
    findings = _actionable(unsafe)
    assert {item["capability"] for item in findings} == {"data_flow", "security_taint"}
    assert {item["line_start"] for item in findings} == {4}

    safe = _review(
        tmp_path,
        "internal/users.go",
        """package internal
func user(db DB, r *Request) Rows {
    id := r.URL.Query().Get("id")
    return db.Query("SELECT * FROM users WHERE id = $1", id)
}
""",
        "internal/users_test.go",
        "package internal\nfunc TestUser() {}\n",
    )
    assert safe["verdict"] == "PASS"
    assert _actionable(safe) == []


def test_rust_file_path_requires_containment(tmp_path: Path) -> None:
    unsafe = _review(
        tmp_path,
        "src/files.rs",
        """use std::fs;
use std::path::Path;
pub fn download(requested: &str) -> std::io::Result<Vec<u8>> {
    let root = Path::new("/srv/files");
    fs::read(root.join(requested))
}
""",
        "tests/files.rs",
        "#[test]\nfn symbol_exists() {}\n",
    )
    assert unsafe["verdict"] == "NEEDS WORK"
    assert len(_actionable(unsafe)) == 2
    assert {item["root_cause"] for item in _actionable(unsafe)} == {"unsafe-file-access"}

    safe = _review(
        tmp_path,
        "src/files.rs",
        """use std::fs;
use std::path::Path;
pub fn download(requested: &str) -> std::io::Result<Vec<u8>> {
    let root = Path::new("/srv/files").canonicalize()?;
    let candidate = root.join(requested).canonicalize()?;
    candidate.strip_prefix(&root).map_err(|_| std::io::ErrorKind::PermissionDenied)?;
    fs::read(candidate)
}
""",
        "tests/files.rs",
        "#[test]\nfn symbol_exists() {}\n",
    )
    assert safe["verdict"] == "PASS"
    assert _actionable(safe) == []


def test_java_privileged_route_requires_authorization(tmp_path: Path) -> None:
    unsafe = _review(
        tmp_path,
        "src/main/java/app/AdminController.java",
        """class AdminController {
  @DeleteMapping("/admin/users/{id}")
  void deleteUser(String id) {}
}
""",
        "src/test/java/app/AdminControllerTest.java",
        "class AdminControllerTest {}\n",
    )
    finding = _actionable(unsafe)[0]
    assert unsafe["verdict"] == "NEEDS WORK"
    assert finding["root_cause"] == "authorization-gap"
    assert finding["line_start"] == 2

    safe = _review(
        tmp_path,
        "src/main/java/app/AdminController.java",
        """class AdminController {
  @PreAuthorize("hasRole('ADMIN')")
  @DeleteMapping("/admin/users/{id}")
  void deleteUser(String id) {}
}
""",
        "src/test/java/app/AdminControllerTest.java",
        "class AdminControllerTest {}\n",
    )
    assert safe["verdict"] == "PASS"
    assert _actionable(safe) == []


def test_csharp_shared_mutation_requires_atomic_guard(tmp_path: Path) -> None:
    unsafe = _review(
        tmp_path,
        "src/JobCounter.cs",
        """using System.Threading.Tasks;
class JobCounter {
  static int sharedCounter = 0;
  async Task<int> ProcessAsync() {
    await Task.Yield();
    sharedCounter++;
    return sharedCounter;
  }
}
""",
        "tests/JobCounterTests.cs",
        "class JobCounterTests {}\n",
    )
    finding = _actionable(unsafe)[0]
    assert unsafe["verdict"] == "PASS"
    assert finding["capability"] == "concurrency"
    assert finding["line_start"] == 6

    safe = _review(
        tmp_path,
        "src/JobCounter.cs",
        """using System.Threading;
using System.Threading.Tasks;
class JobCounter {
  static int sharedCounter = 0;
  async Task<int> ProcessAsync() {
    await Task.Yield();
    return Interlocked.Increment(ref sharedCounter);
  }
}
""",
        "tests/JobCounterTests.cs",
        "class JobCounterTests {}\n",
    )
    assert safe["verdict"] == "PASS"
    assert _actionable(safe) == []


def test_csharp_guard_in_one_method_does_not_hide_unguarded_mutation(tmp_path: Path) -> None:
    mixed = _review(
        tmp_path,
        "src/JobCounter.cs",
        """using System.Threading;
using System.Threading.Tasks;
class JobCounter {
  static int sharedCounter = 0;
  int SafeIncrement() {
    return Interlocked.Increment(ref sharedCounter);
  }
  async Task<int> UnsafeIncrement() {
    await Task.Yield();
    sharedCounter++;
    return sharedCounter;
  }
}
""",
        "tests/JobCounterTests.cs",
        "class JobCounterTests {}\n",
    )

    findings = _actionable(mixed)
    assert any(item["capability"] == "concurrency" for item in findings)
    assert {item["line_start"] for item in findings if item["capability"] == "concurrency"} == {10}


def test_csharp_lock_is_scoped_to_the_mutation_it_guards(tmp_path: Path) -> None:
    mixed = _review(
        tmp_path,
        "src/LockedJobCounter.cs",
        """using System.Threading.Tasks;
class LockedJobCounter {
  static int sharedCounter = 0;
  static object counterLock = new object();
  int SafeIncrement() {
    lock (counterLock) {
      sharedCounter++;
      return sharedCounter;
    }
  }
  async Task<int> UnsafeIncrement() {
    await Task.Yield();
    sharedCounter++;
    return sharedCounter;
  }
}
""",
        "tests/LockedJobCounterTests.cs",
        "class LockedJobCounterTests {}\n",
    )

    findings = _actionable(mixed)
    assert any(item["capability"] == "concurrency" for item in findings)
    assert {item["line_start"] for item in findings if item["capability"] == "concurrency"} == {13}


def test_ruby_nested_each_is_performance_advisory(tmp_path: Path) -> None:
    nested = _review(
        tmp_path,
        "lib/report.rb",
        """class Report
  def self.pairs(rows)
    rows.each do |left|
      rows.each do |right|
        yield left, right
      end
    end
  end
end
""",
        "spec/report_spec.rb",
        "RSpec.describe Report do; end\n",
    )
    finding = _actionable(nested)[0]
    assert nested["verdict"] == "PASS"
    assert finding["capability"] == "performance"
    assert finding["line_start"] == 3

    linear = _review(
        tmp_path,
        "lib/report.rb",
        "class Report\n  def self.labels(rows)\n    rows.map(&:to_s)\n  end\nend\n",
        "spec/report_spec.rb",
        "RSpec.describe Report do; end\n",
    )
    assert linear["verdict"] == "PASS"
    assert _actionable(linear) == []


def test_sequential_ruby_each_blocks_are_not_nested(tmp_path: Path) -> None:
    sequential = _review(
        tmp_path,
        "lib/report.rb",
        """class Report
  def self.labels(rows, tags)
    rows.each do |row|
      puts row
    end
    tags.each do |tag|
      puts tag
    end
  end
end
""",
        "spec/report_spec.rb",
        "RSpec.describe Report do; end\n",
    )

    assert not any(item["capability"] == "performance" for item in _actionable(sequential))


@pytest.mark.parametrize("manifest", ["Service.csproj", "Service.sln", "Package.swift"])
def test_generic_verification_recognizes_cross_language_manifests(tmp_path: Path, manifest: str) -> None:
    _write(tmp_path, manifest, "project\n")
    _write(tmp_path, "README.md", "# Service\n")
    _write(tmp_path, ".github/workflows/ci.yml", "name: ci\n")
    _write(tmp_path, "src/Service.cs", "class Service {}\n")
    _write(tmp_path, "tests/ServiceTests.cs", "class ServiceTests {}\n")

    report = verify_repository_standard(tmp_path, mode="generic")

    checks = {item.name: item.passed for item in report.checks}
    assert checks["project_manifest"] is True
    assert checks["tests_present"] is True


def test_go_short_lock_receiver_guards_shared_mutation(tmp_path: Path) -> None:
    guarded = _review(
        tmp_path,
        "internal/counter.go",
        """package internal
func update() {
    go func() {
        mu.Lock()
        sharedCounter++
        mu.Unlock()
    }()
}
""",
        "internal/counter_test.go",
        "package internal\nfunc TestCounter() {}\n",
    )
    assert not any(item.get("capability") == "concurrency" for item in _actionable(guarded))
