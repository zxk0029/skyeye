# encoding=utf-8

from apps.backoffice.models import MgObPersistence, Asset, OtcAssetPrice
from common.helpers import (
    ok_json,
    error_json
)


def market_price(request):
    base_asset = request.GET.get("base_asset")
    order_by = request.GET.get("order_by")
    price_list = MgObPersistence.objects.all().order_by("id")
    if base_asset not in ["", None]:
        price_list = price_list.filter(base_asset=Asset.objects.filter(symbol=base_asset).first())
    if order_by in ["price", "Price"]:
        price_list = price_list.order_by("avg_price")
    if order_by in ["ratio", "Ratio"]:
        price_list = price_list.order_by("ratio")
    price_result = []
    for price in price_list:
        price_result.append(price.as_dict())
    return ok_json(price_result)


def asset_otc_price(request):
    asset_name = request.GET.get("asset_name")
    if not asset_name:
        return error_json("Parameter 'asset_name' (asset symbol) is required.", code=400, status=400)
    asset = Asset.objects.filter(symbol=asset_name).first()
    if not asset:
        return error_json(f"Asset with symbol '{asset_name}' not found.", code=404, status=404)
    otc_price = OtcAssetPrice.objects.filter(asset=asset).first()
    if otc_price is None:
        return error_json(f"OTC price data not available for asset '{asset_name}'.", code=404, status=404)
    return ok_json(otc_price.as_dict())


def symbol_market_price(request):
    price_list = MgObPersistence.objects.all().order_by("id")
    price_result = []
    for price in price_list:
        price_result.append(price.as_dict())
    return ok_json(price_result)
