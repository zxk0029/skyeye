import asyncio
import json
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.cmc_proxy.consts import CMC_QUOTE_DATA_KEY
from apps.cmc_proxy.models import CmcAsset, CmcMarketData
from apps.cmc_proxy.utils import CMCRedisClient
from common.helpers import getLogger

logger = getLogger(__name__)


class Command(BaseCommand):
    help = 'Fetches CMC data from Redis and persists it to the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=600,
            help='The interval in seconds to run the sync task in a loop.'
        )
        parser.add_argument(
            '--run-once',
            action='store_true',
            help='Run the sync task once and exit.'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        run_once = options['run_once']

        if run_once:
            logger.info("Running CMC data sync task once.")
        else:
            logger.info(f"Starting CMC data sync task to run every {interval} seconds.")

        try:
            asyncio.run(self.run_sync_loop(interval, run_once))
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Sync process interrupted by user."))
        except Exception as e:
            logger.error(f"An unhandled exception occurred in the sync loop: {e}", exc_info=True)

    async def run_sync_loop(self, interval, run_once):
        cmc_redis = None
        try:
            cmc_redis = await CMCRedisClient.create(settings.REDIS_CMC_URL)

            while True:
                start_time = time.time()
                logger.info("Starting CMC data sync from Redis to Database...")

                await self.sync_data_from_redis(cmc_redis)

                elapsed = time.time() - start_time
                logger.info(f"CMC data sync finished in {elapsed:.2f} seconds.")

                if run_once:
                    break

                wait_time = max(0.1, interval - elapsed)
                logger.info(f"Waiting for {wait_time:.2f} seconds before next sync.")
                await asyncio.sleep(wait_time)

        finally:
            if cmc_redis:
                await cmc_redis.aclose()
                logger.info("Redis connection closed.")

    async def sync_data_from_redis(self, cmc_redis: CMCRedisClient):
        # 使用 scan_iter 高效地遍历所有代币数据的键
        pattern = CMC_QUOTE_DATA_KEY.replace("%(symbol_id)s", "*")
        keys = [key async for key in cmc_redis.scan_iter(match=pattern)]

        if not keys:
            logger.warning("No CMC data keys found in Redis to sync.")
            return

        logger.info(f"Found {len(keys)} CMC data keys in Redis.")

        assets_created_count = 0
        assets_updated_count = 0
        market_data_updated_count = 0
        failed_count = 0
        total_count = len(keys)

        for key in keys:
            try:
                raw_data = await cmc_redis.get(key)
                if not raw_data:
                    failed_count += 1
                    continue

                api_data = json.loads(raw_data)
                cmc_id = api_data.get('id')
                if not cmc_id:
                    logger.warning(f"Skipping key {key} due to missing 'id' field.")
                    failed_count += 1
                    continue

                # 1. 同步 CmcAsset (资产元数据)
                asset, created = await CmcAsset.objects.update_or_create_from_api_data(api_data)
                if not asset:
                    failed_count += 1
                    continue

                if created:
                    assets_created_count += 1
                else:
                    assets_updated_count += 1

                # 2. 同步 CmcMarketData (最新行情)
                await CmcMarketData.objects.update_or_create_from_api_data(asset, api_data)
                market_data_updated_count += 1

            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from key {key}.")
                failed_count += 1
            except Exception as e:
                logger.error(f"Error processing data for key {key}: {e}", exc_info=True)
                failed_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Successfully synchronized CMC data. '
            f'Total Processed: {total_count}, '
            f'Assets Created: {assets_created_count}, '
            f'Assets Updated: {assets_updated_count}, '
            f'Market Data Touched: {market_data_updated_count}, '
            f'Failed: {failed_count}'
        ))
