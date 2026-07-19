from __future__ import annotations

from pathlib import Path

from main_review.static_authenticated_owner_review import run_static_authenticated_owner_review


ROOT = "authenticated-resource-read-uses-caller-owner-id"


def _roots(result: dict) -> set[str]:
    return {str(item.get("root_cause")) for item in result.get("findings", [])}


def test_client_owner_id_path_when_authenticated_route_exists_is_reported(tmp_path: Path) -> None:
    client = tmp_path / "api_helper.dart"
    client.write_text(
        """
Future<WalletData?> getWalletData() async {
  int? userId = (await auth.currentUser).id;
  final response = await dio.get('$baseUrl/user_wallet_data/$userId');
  return WalletData.fromJson(response.data);
}
        """,
        encoding="utf-8",
    )
    routes = tmp_path / "api.php"
    routes.write_text(
        """
Route::get('/v1/wallet', 'Api\\WalletController@show')->middleware('auth:api,web');
Route::get('/v1/wallet/statement', 'Api\\WalletController@statement')->middleware('auth:api,web');
        """,
        encoding="utf-8",
    )
    result = run_static_authenticated_owner_review(tmp_path, ["api_helper.dart", "api.php"])
    assert ROOT in _roots(result)


def test_authenticated_ownerless_client_route_is_clean(tmp_path: Path) -> None:
    client = tmp_path / "api_helper.dart"
    client.write_text(
        """
Future<WalletData?> getWalletData() async {
  final response = await dio.get('$baseUrl/v1/wallet');
  return WalletData.fromJson(response.data);
}
        """,
        encoding="utf-8",
    )
    routes = tmp_path / "api.php"
    routes.write_text(
        """
Route::get('/v1/wallet', 'Api\\WalletController@show')->middleware('auth:api,web');
        """,
        encoding="utf-8",
    )
    result = run_static_authenticated_owner_review(tmp_path, ["api_helper.dart", "api.php"])
    assert ROOT not in _roots(result)


def test_public_catalog_id_route_without_authenticated_owner_contract_is_clean(tmp_path: Path) -> None:
    client = tmp_path / "catalog.ts"
    client.write_text(
        """
export async function loadProduct(productId: string) {
  return api.get(`/products/${productId}`);
}
        """,
        encoding="utf-8",
    )
    result = run_static_authenticated_owner_review(tmp_path, ["catalog.ts"])
    assert ROOT not in _roots(result)
