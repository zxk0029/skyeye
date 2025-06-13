#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from django.urls import path

from .views import get_price

app_name = 'price_oracle'

urlpatterns = [
    # 单个资产最优价格
    path('price', get_price, name='price'),
]