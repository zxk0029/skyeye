import ccxt
from django.core.management.base import BaseCommand

from apps.exchange.ccxt_client import get_client
from apps.exchange.models import Exchange, CommonStatus, ExchangeCate


def get_exchange_by_slug_or_alias(slug):
    try:
        return Exchange.objects.get(slug=slug)
    except Exchange.DoesNotExist:
        return Exchange.objects.filter(meta_data__ccxt_alias_ids__contains=[slug]).first()


def _collect_unique_exchanges():
    exchange_map = {}
    for exchange_id in ccxt.exchanges:
        client = get_client(exchange_id)
        if not client: continue
        exchange_name = getattr(client, 'name', exchange_id)
        if exchange_name not in exchange_map:
            exchange_map[exchange_name] = {'slug': exchange_id, 'aliases': []}
        else:
            # 已有主 slug，当前 slug 作为别名
            if exchange_id != exchange_map[exchange_name]['slug'] and exchange_id not in exchange_map[exchange_name]['aliases']:
                exchange_map[exchange_name]['aliases'].append(exchange_id)
    return exchange_map

class Command(BaseCommand):
    help = '全量同步 CCXT 支持的所有交易所（新建/更新/激活）'

    def _get_exchange_details_from_ccxt(self, slug, original_name):
        """获取 CCXT 交易所详细信息"""
        details = {'name': original_name, 'www_url': None, 'api_url': None, 'logo_url': None, "pro": None, "ws_symbols": None}
        client = get_client(slug)
        try:
            if getattr(client, 'name', None):
                details['name'] = client.name

            if not hasattr(client, 'urls') or not client.urls:
                return details

            urls = client.urls
            api_url_info = urls.get('api')
            api_urls = []
            for _, value in api_url_info.items():
                # 处理包含 {hostname} 的 API URL
                if "{hostname}" in value:
                    hostname = getattr(client, 'hostname', None)
                    if hostname:
                        value = value.replace("{hostname}", hostname)
                api_urls.append(value)

            details['www_url'] = urls.get('www')
            details['api_url'] = api_urls
            details['logo_url'] = urls.get('logo')

            if client.pro:
                details['pro'] = True
                pro_client = get_client(slug, "async", "pro")
                if pro_client.has.get('watchOrderBookForSymbols'):
                    print(original_name)
                    details['ws_symbols'] = True

        except Exception as e:
            self.stderr.write(f"获取 {slug} 详情时出错: {str(e)}")

        return details

    def _sync_exchanges_to_db(self, exchange_map):
        created_count = 0
        updated_count = 0
        skipped_count = 0
        for ex_name, info in exchange_map.items():
            slug = info['slug']
            aliases = info['aliases']
            details = self._get_exchange_details_from_ccxt(slug, ex_name)
            try:
                meta_data = {k: v for k, v in [('home_url', details.get('www_url')), ('ccxt_alias_ids', aliases), ('pro', details.get('pro')), ('ws_symbols', details.get('ws_symbols'))] if v}
                defaults = {
                    'name': details['name'],
                    'exchange_category': ExchangeCate.CEX.value,
                    'base_api_url': details['api_url'],
                    'logo_url': details['logo_url'],
                    'meta_data': meta_data,
                    'status': CommonStatus.ACTIVE.value
                }
                obj, created = Exchange.objects.update_or_create(slug=slug, defaults=defaults)
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                self.stderr.write(e)
                skipped_count += 1
        return created_count, updated_count, skipped_count

    def handle(self, *args, **options):
        self.stdout.write("开始全量同步 CCXT 交易所数据...")
        exchange_map = _collect_unique_exchanges()
        if not exchange_map:
            self.stdout.write("无可用交易所，退出。")
            return

        created, updated, skipped = self._sync_exchanges_to_db(exchange_map)
        self.stdout.write(f"完成全量同步。创建: {created}, 更新: {updated}, 跳过: {skipped}")
