#encoding=utf-8

import grpc
from sevices.coincorerpc import market_pb2_grpc, market_pb2
from django.conf import settings


class MpClient:
    def __init__(self):
        options = [
            ('grpc.max_receive_message_length', settings.GRPC_MAX_MESSAGE_LENGTH),
        ]
        channel = grpc.insecure_channel("60.205.1.144:50250", options=options)
        self.stub = market_pb2_grpc.MarketPriceServiceStub(channel)

    def get_market(self, consumer_token: str = None):
        return self.stub.getMarket(
            market_pb2.MarketPriceRequest(
                consumer_token=consumer_token
            )
        )

