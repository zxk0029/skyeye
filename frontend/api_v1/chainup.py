#encoding=utf-8

import pytz
import json
import logging
from common.helpers import (
    ok_json,
    error_json
)
from backoffice.models import MgObPersistence, Asset, OtcAssetPrice


def market_price(request):
    base_asset = request.GET.get("base_asset")
    order_by = request.GET.get("order_by")
    price_list = MgObPersistence.objects.all().order_by("id")
    if base_asset not in ["", None]:
        price_list = price_list.filter(base_asset=Asset.objects.filter(name=base_asset).first())
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
    otc_price = OtcAssetPrice.objects.filter(asset=Asset.objects.filter(name=asset_name).first()).first()
    return ok_json(otc_price.as_dict())


def symbol_market_price(request):
    price_list = MgObPersistence.objects.all().order_by("id")
    price_result = []
    for price in price_list:
        price_result.append(price.as_dict())
    return ok_json(price_result)



