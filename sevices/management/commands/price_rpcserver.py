#encoding=utf-8

import grpc
from django.core.management.base import BaseCommand
from concurrent import futures
from sevices.savourrpc import market_pb2_grpc
from sevices.grpc_server import PriceServer


class Command(BaseCommand):
    def handle(self, *args, **options):
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        market_pb2_grpc.add_PriceServiceServicer_to_server(
            PriceServer(),
            server
        )
        server.add_insecure_port('[::]:50250')
        server.start()
        print("price rpc server start")
        server.wait_for_termination()