from django.urls import path

from . import views

app_name = 'token_holdings'

urlpatterns = [
    # GET /api/v1/holdings?cmc_id=1 - 语义：对持仓集合进行过滤
    path('', views.token_holdings_api, name='token_holdings_api'),
]