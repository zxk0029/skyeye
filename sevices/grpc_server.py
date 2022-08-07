#encoding=utf-8

import pytz
from backoffice.models import MgObPersistence, Symbol
from sevices.coincorerpc import market_pb2_grpc, common_pb2, market_pb2
from django.conf import settings


tz = pytz.timezone(settings.TIME_ZONE)


def grpc_error(error_msg='', response=None):
    error = common_pb2.Error(
        code=1,
        brief=error_msg,
        detail=error_msg,
        can_retry=True)
    if response:
        return response(error=error)
    return error


class MarketPriceServer(market_pb2_grpc.MarketPriceServiceServicer):
    def getMarket(self, request, context):
        price_return_list = []
        symbol_list = Symbol.objects.filter(status='Active')
        for symbol in symbol_list:
            MgobPrice = MgObPersistence.objects.filter(symbol=symbol).order_by("-id").first()
            item = market_pb2.MarketPrice(
                symbol_name=symbol.name,
                buy_price=str(MgobPrice.buy_price),
                sell_price=str(MgobPrice.sell_price),
                avg_price=str(MgobPrice.avg_price),
                usd_price=str(MgobPrice.usd_price),
                cny_price=str(MgobPrice.cny_price),
                margin=str(MgobPrice.margin)
            )
            price_return_list.append(item)
        return market_pb2.MarketPriceResponse(
            market_price=price_return_list
        )
