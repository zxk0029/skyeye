# encoding=utf-8

from typing import List

import pytz
from django.conf import settings

from apps.backoffice.models import MgObPersistence, TradingPair, OtcAssetPrice
from common.helpers import getLogger
from apps.exchange.models import Exchange, Market, MarketStatusChoices, Asset
from services.savourrpc import market_pb2_grpc, common_pb2, market_pb2

logger = getLogger(__name__)

tz = pytz.timezone(settings.TIME_ZONE)


class PriceServer(market_pb2_grpc.PriceServiceServicer):
    def __init__(self):
        self.logger = logger

    def getExchanges(self, request, context) -> market_pb2.ExchangeResponse:
        exchange_return_list: List[market_pb2.Exchange] = []
        exchange_list = Exchange.objects.filter(status='Active').order_by("-id")
        for exchange in exchange_list:
            item = market_pb2.Exchange(
                id=exchange.id,
                name=exchange.name,
                type=exchange.exchange_category
            )
            exchange_return_list.append(item)
        return market_pb2.ExchangeResponse(
            code=common_pb2.SUCCESS,
            msg="get exchange info success",
            exchanges=exchange_return_list
        )

    def getAssets(self, request, context) -> market_pb2.AssetResponse:
        asset_return_list: List[market_pb2.Asset] = []
        asset_list = Asset.objects.filter(status='Active').order_by("-id")
        for asset in asset_list:
            item = market_pb2.Asset(
                id=asset.id,
                name=asset.symbol,
            )
            asset_return_list.append(item)
        return market_pb2.AssetResponse(
            code=common_pb2.SUCCESS,
            msg="get asset success",
            assets=asset_return_list
        )

    def getSymbols(self, request, context) -> market_pb2.SymbolResponse:
        try:
            exchange_name = request.exchange_name
            self.logger.info(f"Received getSymbols request for exchange: {exchange_name}")

            # Query active markets for the given exchange
            market_list = Market.objects.filter(
                exchange__name=exchange_name,
                status=MarketStatusChoices.TRADING,  # Only include actively trading markets
                exchange__status='Active'  # Ensure the exchange itself is active
            ).select_related('trading_pair__base_asset', 'trading_pair__quote_asset', 'exchange')

            symbols_response = []
            for market in market_list:
                symbol_pb = market_pb2.Symbol(
                    name=market.market_symbol,  # Use market_symbol (e.g., BTCUSDT)
                    base=market.trading_pair.base_asset.symbol,  # e.g., BTC
                    quote=market.trading_pair.quote_asset.symbol,  # e.g., USDT
                    exchange_name=market.exchange.name,
                    # category=market.category, # Add if category is part of your protobuf Symbol message
                    # status=market.status,     # Add if status is part of your protobuf Symbol message
                )
                symbols_response.append(symbol_pb)

            self.logger.info(f"Returning {len(symbols_response)} symbols for exchange: {exchange_name}")
            return market_pb2.SymbolResponse(error=None, symbols=symbols_response)
        except Exchange.DoesNotExist:
            self.logger.warning(f"Exchange not found: {exchange_name}")
            error = market_pb2.Error(code=404, message=f"Exchange {exchange_name} not found")
            return market_pb2.SymbolResponse(error=error)
        except Exception as e:
            self.logger.error(f"Error in getSymbols for {exchange_name}: {e}", exc_info=True)
            error = market_pb2.Error(code=500, message=str(e))
            return market_pb2.SymbolResponse(error=error)

    def getSymbolPrices(self, request, context) -> market_pb2.SymbolPriceResponse:
        exchange_id = int(request.exchange_id) if request.exchange_id else 0
        symbol_id = int(request.symbol_id) if request.symbol_id else 0
        symbol_price_data: List[market_pb2.SymbolPrice] = []
        if exchange_id == 0 and symbol_id == 0:
            symbol_price_list = MgObPersistence.objects.all().order_by("-id")
        elif exchange_id != 0 and symbol_id == 0:
            exchange = Exchange.objects.filter(id=exchange_id).order_by("-id").first()
            symbol_price_list = MgObPersistence.objects.filter(
                exchange=exchange,
            ).order_by("-id")
        elif exchange_id == 0 and symbol_id != 0:
            symbol = TradingPair.objects.filter(id=symbol_id).order_by("-id").first()
            symbol_price_list = MgObPersistence.objects.filter(
                symbol=symbol,
            ).order_by("-id")
        else:
            exchange = Exchange.objects.filter(id=exchange_id).order_by("-id").first()
            symbol = TradingPair.objects.filter(id=symbol_id).order_by("-id").first()
            symbol_price_list = MgObPersistence.objects.filter(
                exchange=exchange,
                symbol=symbol,
            ).order_by("-id")
        for symbol_price in symbol_price_list:
            item = market_pb2.SymbolPrice(
                id=str(symbol_price.id),
                name=str(symbol_price.symbol.symbol_display) if symbol_price.symbol else "",
                base=str(symbol_price.symbol.base_asset.symbol) if symbol_price.symbol and symbol_price.symbol.base_asset else "",
                quote=str(symbol_price.symbol.quote_asset.symbol) if symbol_price.symbol and symbol_price.symbol.quote_asset else "",
                exchange=str(symbol_price.exchange.name) if symbol_price.exchange else "",
                symbol=str(symbol_price.symbol.symbol_display) if symbol_price.symbol else "",
                buy_price=str(symbol_price.buy_price),
                sell_price=str(symbol_price.sell_price),
                avg_price=str(symbol_price.avg_price),
                usd_price=str(symbol_price.usd_price),
                cny_price=str(symbol_price.cny_price),
                margin=str(symbol_price.margin),
            )
            symbol_price_data.append(item)
        return market_pb2.SymbolPriceResponse(
            code=common_pb2.SUCCESS,
            msg="get symbol prices success",
            symbol_prices=symbol_price_data
        )

    def getStableCoins(self, request, context) -> market_pb2.StableCoinResponse:
        stable_coin_list: List[market_pb2.StableCoin] = []
        stable_coins = Asset.objects.filter(status='Active', is_stablecoin=True).order_by("-id")
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

    def getStableCoinPrice(self, request, context) -> market_pb2.StableCoinPriceResponse:
        coin_id = int(request.coin_id) if request.coin_id else 0
        stablecoin_price_list: List[market_pb2.StableCoin] = []
        if coin_id == 0:
            stable_coin_prices = OtcAssetPrice.objects.all().order_by("-id")
        else:
            db_asset = Asset.objects.filter(id=coin_id).first()
            stable_coin_prices = OtcAssetPrice.objects.filter(
                asset=db_asset
            ).order_by("-id")
        for stable_coin_price in stable_coin_prices:
            item = market_pb2.StableCoinPrice(
                id=str(stable_coin_price.id),
                name=stable_coin_price.asset.symbol,
                usd_price=str(stable_coin_price.usd_price),
                cny_price=str(stable_coin_price.cny_price),
                margin=str(stable_coin_price.margin),
            )
            stablecoin_price_list.append(item)
        return market_pb2.StableCoinPriceResponse(
            code=common_pb2.SUCCESS,
            msg="get stable coin price success",
            coin_prices=stablecoin_price_list
        )
