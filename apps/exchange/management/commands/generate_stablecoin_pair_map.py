from django.core.management.base import BaseCommand
from apps.exchange.models import Market, Asset, Exchange, TradingPair
from django.db.models import Count, Q
import json
import csv
from datetime import datetime
from apps.exchange.consts import STABLECOIN_SYMBOLS

# 交易所ID映射 (如果数据库中的id与ccxt不同)
EXCHANGE_ID_MAP = {
    'gate': 'gateio',
    'myokx': 'okx',
    'htx': 'huobi',
}

class Command(BaseCommand):
    help = '生成唯一稳定币币对池并输出币对-交易所映射表（目标9000）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-pairs', 
            type=int, 
            default=9000,
            help='目标唯一币对数量（默认9000）'
        )
        parser.add_argument(
            '--only-active', 
            action='store_true',
            help='只选择交易所标记为活跃的币对'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            default='stablecoin_pair_map.json',
            help='输出文件名（默认stablecoin_pair_map.json）'
        )

    def handle(self, *args, **options):
        max_pairs = options['max_pairs']
        only_active = options['only_active']
        output_file = options['output_file']
        
        self.stdout.write(f"开始生成唯一稳定币币对池（目标数量: {max_pairs}，仅活跃: {only_active}）")
        
        # 1. 查询并按现货币对数量排序交易所
        self.stdout.write("查询所有交易所的现货稳定币币对数量...")
        
        base_filter = Q(
            category='Spot',
            status='Trading',
            trading_pair__quote_asset__symbol__in=STABLECOIN_SYMBOLS
        )
        
        if only_active:
            base_filter &= Q(is_active_on_exchange=True)
        
        exchange_counts = (
            Market.objects
            .filter(base_filter)
            .values('exchange__slug')
            .annotate(
                pair_count=Count('trading_pair__id', distinct=True)
            )
            .order_by('-pair_count')
        )
        
        EXCHANGE_PRIORITY = [item['exchange__slug'] for item in exchange_counts if item['pair_count'] > 0]
        
        self.stdout.write("交易所稳定币币对数量统计:")
        for exchange in exchange_counts:
            self.stdout.write(f"  {exchange['exchange__slug']}: {exchange['pair_count']} 个稳定币币对")
        
        # 2. 准备汇总数据结构
        pair_map = {}  
        seen = set()
        total_pairs = 0
        exchange_formats = {}
        
        # 4. 主循环 - 按优先级合并币对
        for slug in EXCHANGE_PRIORITY:
            markets = (
                Market.objects
                .filter(base_filter, exchange__slug=slug)
                .select_related(
                    'exchange',
                    'trading_pair',
                    'trading_pair__base_asset', 
                    'trading_pair__quote_asset'
                )
            )
            
            new_pairs = 0
            ccxt_exchange_id = EXCHANGE_ID_MAP.get(slug, slug)
            
            for m in markets:
                base_asset_symbol = m.trading_pair.base_asset.symbol.upper()
                quote_asset_symbol = m.trading_pair.quote_asset.symbol.upper()
                
                if quote_asset_symbol not in STABLECOIN_SYMBOLS:
                    continue
                    
                key = (base_asset_symbol, quote_asset_symbol)
                if key in seen:
                    continue
                
                original_symbol = m.market_symbol
                ccxt_symbol = m.trading_pair.symbol_display 
                constructed_standard_symbol = f"{base_asset_symbol}/{quote_asset_symbol}"
                
                if slug not in exchange_formats:
                    exchange_formats[slug] = []
                if len(exchange_formats[slug]) < 5: 
                    exchange_formats[slug].append({
                        'market_symbol_id_ccxt': original_symbol,
                        'trading_pair_symbol_display_ccxt': m.trading_pair.symbol_display,
                        'final_ccxt_symbol_for_json': ccxt_symbol,
                        'constructed_base_quote': constructed_standard_symbol,
                        'base_asset': base_asset_symbol,
                        'quote_asset': quote_asset_symbol,
                        'market_id_db': m.market_identifier,
                        'is_active_db': m.is_active_on_exchange,
                    })
                
                pair_map[key] = {
                    'exchange': ccxt_exchange_id,  
                    'symbol': original_symbol, 
                    'ccxt_symbol': ccxt_symbol, 
                    'standard_symbol': constructed_standard_symbol, 
                    'market_id': m.market_identifier,  
                    'is_active': m.is_active_on_exchange,
                }
                seen.add(key)
                new_pairs += 1
                
            total_pairs = len(seen)
            self.stdout.write(f"After {slug}: unique pairs = {total_pairs}, new added = {new_pairs}")
            
            if total_pairs >= max_pairs:
                self.stdout.write(f"达到目标币对数量 {max_pairs}，停止添加更多交易所")
                break

        self.stdout.write(f"\n最终唯一币对数: {total_pairs}")
        self.stdout.write(f"最终优先级交易所: {EXCHANGE_PRIORITY[:10]} ...")

        json_map = {f"{base}/{quote}": v for (base, quote), v in pair_map.items()}
        with open(output_file, 'w') as f:
            json.dump(json_map, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"已保存 {output_file}"))
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f'exchange_symbol_formats_{timestamp}.csv', 'w', newline='') as csvfile:
            fieldnames = [
                'exchange', 'ccxt_exchange', 
                'market_symbol_id_ccxt', 'trading_pair_symbol_display_ccxt', 
                'final_ccxt_symbol_for_json', 'constructed_base_quote',
                'base_asset', 'quote_asset', 
                'market_id_db', 'is_active_db'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for exchange_slug_key, samples in exchange_formats.items():
                ccxt_exchange_name = EXCHANGE_ID_MAP.get(exchange_slug_key, exchange_slug_key)
                for sample in samples:
                    writer.writerow({
                        'exchange': exchange_slug_key,
                        'ccxt_exchange': ccxt_exchange_name,
                        'market_symbol_id_ccxt': sample['market_symbol_id_ccxt'],
                        'trading_pair_symbol_display_ccxt': sample['trading_pair_symbol_display_ccxt'],
                        'final_ccxt_symbol_for_json': sample['final_ccxt_symbol_for_json'],
                        'constructed_base_quote': sample['constructed_base_quote'],
                        'base_asset': sample['base_asset'],
                        'quote_asset': sample['quote_asset'],
                        'market_id_db': sample.get('market_id_db', ''), 
                        'is_active_db': sample.get('is_active_db', '')  
                    })
            
        self.stdout.write(self.style.SUCCESS(f"已保存交易所符号格式样本到 exchange_symbol_formats_{timestamp}.csv")) 