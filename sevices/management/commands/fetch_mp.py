#encoding=utf-8


import logging
from django.core.management.base import BaseCommand
from sevices.mp_client import MpClient


class Command(BaseCommand):
    def handle(self, *args, **options):
        mp_client = MpClient()
        ret_info = mp_client.get_market()
        print("ret_info====", ret_info)