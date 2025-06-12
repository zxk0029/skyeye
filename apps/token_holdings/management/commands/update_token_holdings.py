import asyncio
import logging
from typing import List

from django.core.management.base import BaseCommand, CommandError

from apps.cmc_proxy.models import CmcAsset
from apps.token_holdings.services import TokenHoldingsService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '更新代币持仓数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--cmc-ids',
            type=str,
            help='指定要更新的CMC ID列表，用逗号分隔，例如: 1,2,3'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            help='指定要更新的代币符号列表，用逗号分隔，例如: BTC,ETH,USDT'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='更新所有已知的CMC资产持仓数据'
        )
        parser.add_argument(
            '--max-concurrent',
            type=int,
            default=10,
            help='最大并发请求数，默认10'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将要处理的资产，不实际更新数据'
        )

    def handle(self, *args, **options):
        try:
            # 运行异步处理逻辑
            asyncio.run(self._async_handle(options))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Command failed: {str(e)}')
            )
            raise CommandError(f'Failed to update token holdings: {str(e)}')

    async def _async_handle(self, options):
        """异步处理命令逻辑"""
        cmc_ids = await self._get_cmc_ids(options)

        if not cmc_ids:
            self.stdout.write(
                self.style.WARNING('No CMC IDs found to process')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f'Found {len(cmc_ids)} CMC IDs to process')
        )

        if options['dry_run']:
            self.stdout.write('Dry run mode - listing assets to process:')
            for cmc_id in cmc_ids:
                try:
                    asset = await CmcAsset.objects.filter(cmc_id=cmc_id).afirst()
                    if asset:
                        self.stdout.write(f'  - {asset.symbol} (CMC ID: {cmc_id})')
                    else:
                        self.stdout.write(f'  - Unknown asset (CMC ID: {cmc_id})')
                except Exception as e:
                    self.stdout.write(f'  - Error getting asset info for CMC ID {cmc_id}: {str(e)}')
            return

        # 实际更新数据
        async with TokenHoldingsService() as service:
            self.stdout.write('Starting token holdings update...')

            results = await service.batch_update_holdings(cmc_ids, max_concurrent=options['max_concurrent'])

            # 统计结果
            success_count = sum(1 for success, _ in results.values() if success)
            failure_count = len(results) - success_count

            self.stdout.write(
                self.style.SUCCESS(f'Update completed: {success_count} successful, {failure_count} failed')
            )

            # 显示详细结果
            if failure_count > 0:
                self.stdout.write(self.style.WARNING('Failed updates:'))
                for cmc_id, (success, message) in results.items():
                    if not success:
                        try:
                            asset = await CmcAsset.objects.filter(cmc_id=cmc_id).afirst()
                            symbol = asset.symbol if asset else 'Unknown'
                            self.stdout.write(f'  - {symbol} (CMC ID: {cmc_id}): {message}')
                        except Exception as e:
                            self.stdout.write(f'  - CMC ID {cmc_id}: {message} (Error getting symbol: {str(e)})')

            if success_count > 0:
                self.stdout.write(self.style.SUCCESS('Successful updates:'))
                for cmc_id, (success, message) in results.items():
                    if success:
                        try:
                            asset = await CmcAsset.objects.filter(cmc_id=cmc_id).afirst()
                            symbol = asset.symbol if asset else 'Unknown'
                            self.stdout.write(f'  - {symbol} (CMC ID: {cmc_id}): {message}')
                        except Exception as e:
                            self.stdout.write(f'  - CMC ID {cmc_id}: {message} (Error getting symbol: {str(e)})')

    async def _get_cmc_ids(self, options) -> List[int]:
        """根据选项获取要处理的CMC ID列表"""
        cmc_ids = []

        if options['cmc_ids']:
            # 处理指定的CMC ID列表
            try:
                cmc_ids = [int(id.strip()) for id in options['cmc_ids'].split(',')]
                self.stdout.write(f'Processing specified CMC IDs: {cmc_ids}')
            except ValueError as e:
                raise CommandError(f'Invalid CMC ID format: {str(e)}')

        elif options['symbols']:
            # 处理指定的代币符号列表
            symbols = [symbol.strip().upper() for symbol in options['symbols'].split(',')]
            self.stdout.write(f'Looking up CMC IDs for symbols: {symbols}')

            for symbol in symbols:
                try:
                    asset = await CmcAsset.objects.filter(symbol__iexact=symbol).afirst()
                    if asset:
                        cmc_ids.append(asset.cmc_id)
                        self.stdout.write(f'  - {symbol}: CMC ID {asset.cmc_id}')
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  - {symbol}: Not found in database')
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  - {symbol}: Error looking up: {str(e)}')
                    )

        elif options['all']:
            # 处理所有已知的CMC资产
            self.stdout.write('Getting all CMC assets from database...')
            try:
                assets = CmcAsset.objects.all()
                async for asset in assets:
                    cmc_ids.append(asset.cmc_id)

                self.stdout.write(f'Found {len(cmc_ids)} assets in database')
            except Exception as e:
                raise CommandError(f'Error getting CMC assets: {str(e)}')
        else:
            raise CommandError(
                'Must specify one of: --cmc-ids, --symbols, or --all'
            )

        return cmc_ids
