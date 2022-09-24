#encoding=utf-8

import pytz
from backoffice.models import MgObPersistence, Symbol, Asset
from sevices.savourrpc import market_pb2_grpc, common_pb2, market_pb2
from django.conf import settings
from exchange.models import Exchange
from typing import Dict, List, Sequence, Tuple


tz = pytz.timezone(settings.TIME_ZONE)


class PriceServer(market_pb2_grpc.PriceServiceServicer):
    def getExchanges(self, request, context) -> market_pb2.ExchangeResponse:
        global exchange_return_list
        exchange_return_list: List[market_pb2.Exchange]
        exchange_list = Exchange.objects.filter(status='Active').order_by("-id")
        for exchange in exchange_list:
            item = market_pb2.Exchange(
                id=exchange.id,
                name=exchange.name,
                type=exchange.market_type
            )
            exchange_return_list.append(item)
        return market_pb2.ExchangeResponse(
            code=common_pb2.SUCCESS,
            msg="get exchange info success",
            exchanges=exchange_return_list
        )


    def getAssets(self, request, context) -> market_pb2.AssetResponse:
        global asset_return_list
        asset_return_list: List[market_pb2.Asset]
        asset_list = Asset.objects.filter(status='Active').order_by("-id")
        for asset in asset_list:
            item = market_pb2.Asset(
                id=asset.id,
                name=asset.name,
            )
            asset_return_list.append(item)
        return market_pb2.AssetResponse(
            code=common_pb2.SUCCESS,
            msg="get asset success",
            exchanges=asset_return_list
        )


    def getSymbols(self, request, context)-> market_pb2.SymbolResponse:
        exchange_id = request.exchange_id  # todo: query exchange by exchange id
        global symbol_return_list
        symbol_return_list: List[market_pb2.Symbol]
        symbol_list = Symbol.objects.filter(status='Active').order_by("-id")
        for symbol in symbol_list:
            item = market_pb2.Symbol(
                id=symbol.id,
                name=symbol.name,
                base=symbol.base_asset,
                quote=symbol.quote_asset
            )
            symbol_return_list.append(item)
        return market_pb2.SymbolResponse(
            code=common_pb2.SUCCESS,
            msg="get asset success",
            symbols=symbol_return_list
        )

    def getSymbolPrices(self, request, context)-> market_pb2.SymbolPriceResponse:
        exchange_id = request.exchange_id
        symbol_id = request.symbol_id
        global symbol_price_list
        symbol_price_list: List[market_pb2.SymbolPrice]
        symbol = Symbol.objects.filter(id=symbol_id).order_by("-id").first()
        exchange  = Exchange.objects.filter(id=exchange_id).order_by("-id").first()
        if symbol and exchange is not None:
            symbol_prices = MgObPersistence.objects.filter(status='Active').order_by("-id")
            for sprice in symbol_prices:
                item = market_pb2.SymbolPrice(
                    id=sprice.id,
                    name=sprice.symbol.name,
                    base =sprice.symbol.base_asset,
                    quote = sprice.symbol.quote_asset,
                    buy_price=sprice.buy_price,
                    sell_price =sprice.sell_price,
                    avg_price =sprice.avg_price,
                    usd_price =sprice.usd_price,
                    cny_price =sprice.cny_price,
                    margin =sprice.margin,
                )
                symbol_price_list.append(item)
            return market_pb2.SymbolPriceResponse(
                code=common_pb2.SUCCESS,
                msg="get symbol prices success",
                symbol_prices=symbol_price_list
            )
        else:
            return market_pb2.SymbolPriceResponse(
                code=common_pb2.ERROR,
                msg="get symbol prices fail, not this exchange or symbol",
            )


    def getStableCoins(self, request, context) -> market_pb2.StableCoinResponse:
        global stable_coin_list
        stable_coin_list: List[market_pb2.StableCoin]
        stable_coins = Asset.objects.filter(status='Active', is_stable="Yes").order_by("-id")
        for stable_coin in stable_coins:
            item = market_pb2.StableCoin(
                id=stable_coin.id,
                name=stable_coin.name,
            )
            stable_coin_list.append(item)
        return market_pb2.StableCoinResponse(
            code=common_pb2.SUCCESS,
            msg="get stable coin success",
            stable_coins=stable_coin_list
        )

    def getStableCoinPrice(self, request, context)-> market_pb2.StableCoinPriceResponse:
        coin_id = request.coin_id
        global stablecoin_price_list
        stablecoin_price_list: List[market_pb2.StableCoin]
        stable_coin_prices = MgObPersistence.objects.filter(
            qoute_asset=Asset.objects.filter(id=coin_id).first()
        ).order_by("-id")
        for stable_coin_price in stable_coin_prices:
            item = market_pb2.StableCoin(
                id=stable_coin_price.id,
                name=stable_coin_price.symbol.name,
                usd_price=stable_coin_price.usd_price,
                cny_price=stable_coin_price.cny_price,
                margin=stable_coin_price.margin,
            )
            stablecoin_price_list.append(item)
        return market_pb2.StableCoinPriceResponse(
            code=common_pb2.SUCCESS,
            msg="get stable coin price success",
            coin_prices=stablecoin_price_list
        )

