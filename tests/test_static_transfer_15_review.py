from __future__ import annotations

from pathlib import Path

from main_review.static_status_review import run_static_status_review
from main_review.static_transfer_15_review import run_static_transfer_15_review


TRANSPORT_ROOT = "transport-no-answer-collapsed-into-authoritative-failure-envelope"
CANCELLATION_ROOT = "coroutine-cancellation-swallowed-by-per-item-isolation"
PRESENCE_ROOT = "present-invalid-optional-field-collapsed-into-absent-semantics"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_websocket_transport_and_remote_rejection_soft_envelope_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "client.py"
    source.write_text(
        '''
class Client:
    async def send_websocket_message(self, message: dict) -> dict:
        try:
            ws_client = await get_websocket_client()
            return await ws_client.send_command(message["type"])
        except Exception as error:
            return {"success": False, "error": str(error)}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["client.py"])

    assert TRANSPORT_ROOT in _roots(result)


def test_typed_no_answer_failures_rethrow_before_remote_rejection_envelope_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "client.py"
    source.write_text(
        '''
class Client:
    async def send_websocket_message(self, message: dict) -> dict:
        try:
            ws_client = await get_websocket_client()
            return await ws_client.send_command(message["type"])
        except (ConnectionError, TimeoutError, OSError):
            raise
        except Exception as error:
            return {"success": False, "error": str(error)}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["client.py"])

    assert TRANSPORT_ROOT not in _roots(result)


def test_local_parser_result_wrapper_is_not_treated_as_transport_contract(tmp_path: Path) -> None:
    source = tmp_path / "parser.py"
    source.write_text(
        '''
async def parse_message(raw: str) -> dict:
    try:
        return {"success": True, "value": json.loads(raw)}
    except Exception as error:
        return {"success": False, "error": str(error)}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["parser.py"])

    assert TRANSPORT_ROOT not in _roots(result)


def test_kotlin_suspend_runcatching_that_logs_all_refresh_failures_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Registry.kt"
    source.write_text(
        '''
internal class Registry {
    suspend fun refreshInstalled(context: Context) {
        installedDescriptors(context).forEach { descriptor ->
            runCatching { widgetUpdater(descriptor.widgetFactory(), context) }
                .onFailure { failure ->
                    Log.w("Registry", "Unable to refresh", failure)
                }
        }
    }
}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Registry.kt"])

    assert CANCELLATION_ROOT in _roots(result)


def test_kotlin_cancellation_rethrow_keeps_per_item_isolation_clean(tmp_path: Path) -> None:
    source = tmp_path / "Registry.kt"
    source.write_text(
        '''
internal class Registry {
    suspend fun refreshInstalled(context: Context) {
        installedDescriptors(context).forEach { descriptor ->
            runCatching { widgetUpdater(descriptor.widgetFactory(), context) }
                .onFailure { failure ->
                    if (failure is CancellationException) throw failure
                    Log.w("Registry", "Unable to refresh", failure)
                }
        }
    }
}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Registry.kt"])

    assert CANCELLATION_ROOT not in _roots(result)


def test_non_suspend_runcatching_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Registry.kt"
    source.write_text(
        '''
fun refreshLabel(): String =
    runCatching { loadLabel() }.getOrElse { "unknown" }
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Registry.kt"])

    assert CANCELLATION_ROOT not in _roots(result)


def test_swift_present_invalid_limit_collapsed_by_optional_chain_is_reported(tmp_path: Path) -> None:
    source = tmp_path / "Probe.swift"
    source.write_text(
        '''
private struct SpendData: Decodable {
    let used: MoneyData?
    let limit: MoneyData?
    let enabled: Bool?
}

private struct MoneyData: Decodable {
    let amountMinor: Decimal?
    let exponent: Int?

    var amount: Decimal? {
        guard let amountMinor, amountMinor >= 0, let exponent, exponent >= 0 else { return nil }
        return Decimal(sign: .plus, exponent: -exponent, significand: amountMinor)
    }
}

func parse(_ response: Response) -> CostUsage? {
    if response.spend?.enabled == true,
       let used = response.spend?.used?.amount {
        return CostUsage(totalCost: used, budget: response.spend?.limit?.amount)
    }
    return nil
}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Probe.swift"])

    assert PRESENCE_ROOT in _roots(result)


def test_swift_explicit_presence_then_validation_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Probe.swift"
    source.write_text(
        '''
private struct SpendData: Decodable {
    let used: MoneyData?
    let limit: MoneyData?
}

private struct MoneyData: Decodable {
    let amountMinor: Decimal?
    let exponent: Int?
    var amount: Decimal? {
        guard let amountMinor, amountMinor >= 0, let exponent, exponent >= 0 else { return nil }
        return Decimal(sign: .plus, exponent: -exponent, significand: amountMinor)
    }
}

func pair(_ spend: SpendData) -> (Decimal, Decimal?)? {
    guard let used = spend.used?.amount else { return nil }
    guard let limit = spend.limit else { return (used, nil) }
    guard let cap = limit.amount else { return nil }
    return (used, cap)
}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Probe.swift"])

    assert PRESENCE_ROOT not in _roots(result)


def test_optional_descriptive_field_is_clean(tmp_path: Path) -> None:
    source = tmp_path / "Profile.swift"
    source.write_text(
        '''
private struct Profile: Decodable {
    let subtitle: String?
}
func render(_ profile: Profile) -> String {
    profile.subtitle ?? "No subtitle"
}
        ''',
        encoding="utf-8",
    )

    result = run_static_transfer_15_review(tmp_path, ["Profile.swift"])

    assert PRESENCE_ROOT not in _roots(result)


def test_status_bundle_exposes_all_transfer_15_roots(tmp_path: Path) -> None:
    py = tmp_path / "client.py"
    py.write_text(
        '''
async def send_websocket_message(message: dict) -> dict:
    try:
        client = await get_websocket_client()
        return await client.send_command(message["type"])
    except Exception as error:
        return {"success": False, "error": str(error)}
        ''',
        encoding="utf-8",
    )
    kt = tmp_path / "Registry.kt"
    kt.write_text(
        '''
suspend fun refreshInstalled(context: Context) {
    items.forEach { item ->
        runCatching { updateWidget(item, context) }
            .onFailure { Log.w("Registry", "refresh failed", it) }
    }
}
        ''',
        encoding="utf-8",
    )
    swift = tmp_path / "Probe.swift"
    swift.write_text(
        '''
private struct SpendData { let limit: MoneyData? }
private struct MoneyData {
    let raw: Decimal?
    var amount: Decimal? {
        guard let raw, raw >= 0 else { return nil }
        return raw
    }
}
func build(_ spend: SpendData) -> Usage {
    Usage(budget: spend.limit?.amount)
}
        ''',
        encoding="utf-8",
    )

    result = run_static_status_review(tmp_path, ["client.py", "Registry.kt", "Probe.swift"])

    assert {TRANSPORT_ROOT, CANCELLATION_ROOT, PRESENCE_ROOT}.issubset(_roots(result))
    assert result["static_transfer_15_review"]["finding_count"] == 3
