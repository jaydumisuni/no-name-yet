from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_19_review import run_static_transfer_19_review


GO_ROOT = "repeat-registration-panics-before-equivalence-check"
JAVA_ROOT = "common-or-server-code-references-client-only-runtime-type"
C_ROOT = "publication-flag-read-without-acquire-semantics"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_repeat_global_registration_panics_without_equivalence_check(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seccomp.go",
        '''
package seccomp

var (
    registeredPolicy *Policy
)

func MustRegisterPolicy(p *Policy) {
    if p == nil { panic("nil") }
    if registeredPolicy != nil {
        panic("already registered")
    }
    registeredPolicy = p
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, ["seccomp.go"])

    assert GO_ROOT in _roots(result)


def test_identical_repeat_registration_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "seccomp.go",
        '''
package seccomp

var registeredPolicy *Policy

func MustRegisterPolicy(p *Policy) {
    if p == nil { panic("nil") }
    if registeredPolicy != nil {
        if policiesEqual(registeredPolicy, p) { return }
        panic("different policy")
    }
    registeredPolicy = p
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, ["seccomp.go"])

    assert GO_ROOT not in _roots(result)


def test_common_java_code_referencing_client_runtime_type_is_blocked(tmp_path: Path) -> None:
    relative = "common/src/main/java/example/SpecifiedMenuAttachingConfig.java"
    _write(
        tmp_path,
        relative,
        '''
package example;
import net.minecraft.client.gui.screens.inventory.CreativeModeInventoryScreen;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.InventoryMenu;

public final class SpecifiedMenuAttachingConfig {
    public boolean isMenuAttachable(AbstractContainerMenu menu) {
        return menu instanceof InventoryMenu
            || menu instanceof CreativeModeInventoryScreen.ItemPickerMenu;
    }
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, [relative])

    assert JAVA_ROOT in _roots(result)


def test_common_java_code_using_server_safe_type_is_clean(tmp_path: Path) -> None:
    relative = "common/src/main/java/example/SpecifiedMenuAttachingConfig.java"
    _write(
        tmp_path,
        relative,
        '''
package example;
import net.minecraft.world.inventory.AbstractContainerMenu;
import net.minecraft.world.inventory.InventoryMenu;

public final class SpecifiedMenuAttachingConfig {
    public boolean isMenuAttachable(AbstractContainerMenu menu) {
        return menu instanceof InventoryMenu;
    }
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, [relative])

    assert JAVA_ROOT not in _roots(result)


def test_explicit_client_source_boundary_is_clean(tmp_path: Path) -> None:
    relative = "client/src/main/java/example/ClientMenu.java"
    _write(
        tmp_path,
        relative,
        '''
package example;
import net.minecraft.client.gui.screens.inventory.CreativeModeInventoryScreen;

public final class ClientMenu {
    boolean isPicker(Object menu) {
        return menu instanceof CreativeModeInventoryScreen.ItemPickerMenu;
    }
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, [relative])

    assert JAVA_ROOT not in _roots(result)


def test_publication_flag_requires_acquire_read(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "class-init.c",
        '''
void setup_interfaces (MonoClass *klass) {
    if (klass->interfaces_inited)
        return;

    klass->interface_count = count;
    klass->interfaces = interfaces;
    mono_memory_barrier ();
    klass->interfaces_inited = 1;
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, ["class-init.c"])

    assert C_ROOT in _roots(result)


def test_acquire_load_before_publication_fast_path_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "class-init.c",
        '''
void setup_interfaces (MonoClass *klass) {
    if (atomic_load_explicit(&klass->interfaces_inited, memory_order_acquire))
        return;

    klass->interface_count = count;
    klass->interfaces = interfaces;
    atomic_thread_fence(memory_order_release);
    klass->interfaces_inited = 1;
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, ["class-init.c"])

    assert C_ROOT not in _roots(result)


def test_unrelated_plain_ready_flag_without_publication_fence_is_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "simple.c",
        '''
void render (Widget *widget) {
    if (widget->ready)
        return;
    widget->ready = 1;
}
''',
    )

    result = run_static_transfer_19_review(tmp_path, ["simple.c"])

    assert C_ROOT not in _roots(result)
