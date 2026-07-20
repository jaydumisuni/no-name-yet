from __future__ import annotations

from pathlib import Path

from main_review.static_transfer_16_review import run_static_transfer_16_review


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_flags_expirable_client_stop_with_synchronous_ipc(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Request.cpp",
        """
bool Request::stop()
{
    auto had_active_request = m_client->stop_request({}, *this);
    return had_active_request;
}

void Request::release_for_transfer()
{
    if (auto client = m_client.strong_ref())
        client->release_request_for_transfer({}, *this);
}
""",
    )
    _write(
        tmp_path,
        "RequestClient.cpp",
        """
bool RequestClient::stop_request(Request& request)
{
    (void)IPCProxy::stop_request(request.id());
    return true;
}
""",
    )

    result = run_static_transfer_16_review(
        tmp_path,
        ["Request.cpp", "RequestClient.cpp"],
    )

    assert "lifecycle-stop-dereferences-expirable-client-and-sends-synchronously" in _roots(result)


def test_accepts_strong_client_guard_and_async_stop(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Request.cpp",
        """
bool Request::stop()
{
    auto client = m_client.strong_ref();
    auto had_active_request = client && client->stop_request({}, *this);
    return had_active_request;
}
""",
    )
    _write(
        tmp_path,
        "RequestClient.cpp",
        """
bool RequestClient::stop_request(Request& request)
{
    async_stop_request(request.id());
    return true;
}
""",
    )

    result = run_static_transfer_16_review(
        tmp_path,
        ["Request.cpp", "RequestClient.cpp"],
    )

    assert "lifecycle-stop-dereferences-expirable-client-and-sends-synchronously" not in _roots(result)


def test_does_not_assume_every_direct_client_is_expirable(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "Request.cpp",
        """
bool Request::stop()
{
    return m_client->stop_request({}, *this);
}
""",
    )
    _write(
        tmp_path,
        "RequestClient.cpp",
        """
bool RequestClient::stop_request(Request& request)
{
    (void)IPCProxy::stop_request(request.id());
    return true;
}
""",
    )

    result = run_static_transfer_16_review(
        tmp_path,
        ["Request.cpp", "RequestClient.cpp"],
    )

    assert "lifecycle-stop-dereferences-expirable-client-and-sends-synchronously" not in _roots(result)


def test_flags_collapsed_promise_species_undefined_and_null(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "then.rs",
        """
// SpeciesConstructor(promiseReceiver, %Promise%)
fn promise_species_constructor(receiver: f64) -> f64 {
    let c = get_property(receiver, "constructor");
    let sp = well_known_symbol("species");
    let s = get_symbol_property(c, sp);
    if s.to_bits() == TAG_UNDEFINED || s.to_bits() == TAG_NULL {
        return get_intrinsic_promise();
    }
    s
}
""",
    )

    result = run_static_transfer_16_review(tmp_path, ["then.rs"])

    assert "promise-species-undefined-collapsed-into-null-default" in _roots(result)


def test_accepts_promise_brand_aware_undefined_species(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "then.rs",
        """
// SpeciesConstructor(promiseReceiver, %Promise%)
fn promise_species_constructor(receiver: f64) -> f64 {
    let c = get_property(receiver, "constructor");
    let sp = well_known_symbol("species");
    let s = get_symbol_property(c, sp);
    if s.to_bits() == TAG_NULL {
        return get_intrinsic_promise();
    }
    if s.to_bits() == TAG_UNDEFINED {
        if is_promise_brand_constructor(c) {
            return c;
        }
        return get_intrinsic_promise();
    }
    s
}
""",
    )

    result = run_static_transfer_16_review(tmp_path, ["then.rs"])

    assert "promise-species-undefined-collapsed-into-null-default" not in _roots(result)


def test_ignores_generic_optional_default_logic(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "options.rs",
        """
fn resolve_option(value: f64) -> f64 {
    if value.to_bits() == TAG_UNDEFINED || value.to_bits() == TAG_NULL {
        return default_value();
    }
    value
}
""",
    )

    result = run_static_transfer_16_review(tmp_path, ["options.rs"])

    assert result["finding_count"] == 0
