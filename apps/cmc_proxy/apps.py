from django.apps import AppConfig


class CmcProxyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.cmc_proxy'
    verbose_name = "CoinMarketCap 代理"
