# Create your tests here.

import logging
import time

from django.db import connections, DEFAULT_DB_ALIAS, transaction
from django.test import TransactionTestCase

from apps.exchange.models import Asset, Market, Exchange, TradingPair  # Added Exchange, TradingPair

logger = logging.getLogger(__name__)


class DatabaseSetupTests(TransactionTestCase):
    databases = {'default', 'slave_replica'}
    # Define constants for test data identifiers
    DEBUG_EXCHANGE_SLUG = "debug_exchange_kline_test"
    DEBUG_BASE_SYMBOL = "DBG_BTC"
    DEBUG_QUOTE_SYMBOL = "DBG_USDT"
    DEBUG_MARKET_IDENTIFIER = f"{DEBUG_EXCHANGE_SLUG}_spot_{DEBUG_BASE_SYMBOL.lower()}_{DEBUG_QUOTE_SYMBOL.lower()}"
    DEBUG_KLINE_INTERVAL = "1m"

    @classmethod
    def setUpTestData(cls):
        logger.info("--- DatabaseSetupTests.setUpTestData START ---")
        # 0. Set a very simple class attribute for testing persistence
        cls.some_simple_value = "hello_from_setUpTestData"
        logger.info(f"In setUpTestData: Set cls.some_simple_value = '{cls.some_simple_value}'")
        assert hasattr(cls, 'some_simple_value'), "cls.some_simple_value was NOT set in setUpTestData!"
        assert cls.some_simple_value == "hello_from_setUpTestData", "cls.some_simple_value has incorrect value!"

        # 1. Setup Exchange
        exchange, ex_created = Exchange.objects.get_or_create(
            slug=cls.DEBUG_EXCHANGE_SLUG,
            defaults={'name': "Debug Exchange for Kline", 'type': 'CEX', 'status': 'Active'}
        )
        logger.info(f"Exchange {'created' if ex_created else 'retrieved'}: slug='{exchange.slug}', id={exchange.id}")

        # 2. Setup Base Asset
        base_asset, ba_created = Asset.objects.get_or_create(
            symbol=cls.DEBUG_BASE_SYMBOL,
            defaults={'name': "Debug Base Bitcoin", 'asset_type': 'Crypto', 'uint': 8, 'is_stablecoin': False}
        )
        logger.info(
            f"Base Asset {'created' if ba_created else 'retrieved'}: symbol='{base_asset.symbol}', id={base_asset.id}")

        # 3. Setup Quote Asset
        quote_asset, qa_created = Asset.objects.get_or_create(
            symbol=cls.DEBUG_QUOTE_SYMBOL,
            defaults={'name': "Debug Quote USDT", 'asset_type': 'Crypto', 'uint': 6, 'is_stablecoin': True}
        )
        logger.info(
            f"Quote Asset {'created' if qa_created else 'retrieved'}: symbol='{quote_asset.symbol}', id={quote_asset.id}")

        # 4. Setup Trading Pair
        trading_pair, tp_created = TradingPair.objects.get_or_create(
            base_asset=base_asset,
            quote_asset=quote_asset,
            exchange=exchange,
            defaults={'symbol': f"{base_asset.symbol}/{quote_asset.symbol}", 'status': 'Active'}
        )
        logger.info(
            f"TradingPair {'created' if tp_created else 'retrieved'}: symbol='{trading_pair.symbol}', id={trading_pair.id}, base_id={trading_pair.base_asset_id}, quote_id={trading_pair.quote_asset_id}, exchange_id={trading_pair.exchange_id}")

        # 5. Setup Market
        market, mkt_created = Market.objects.get_or_create(
            trading_pair=trading_pair,
            market_identifier=cls.DEBUG_MARKET_IDENTIFIER,  # Use the constant
            defaults={
                'market_symbol': f"{base_asset.symbol}{quote_asset.symbol}",
                'status': 'Active'
            }
        )
        logger.info(
            f"Market {'created' if mkt_created else 'retrieved'}: market_identifier='{market.market_identifier}', id={market.id if market else 'None'}, trading_pair_id={market.trading_pair_id if market else 'None'}")

        # Immediate verification query
        if market:
            try:
                verified_market = Market.objects.using(DEFAULT_DB_ALIAS).get(
                    market_identifier=cls.DEBUG_MARKET_IDENTIFIER)
                logger.info(
                    f"IMMEDIATE CHECK: Market found by identifier '{verified_market.market_identifier}', id={verified_market.id} on DB '{verified_market._state.db}'")
            except Market.DoesNotExist:
                logger.error(
                    f"IMMEDIATE CHECK FAILED: Market with identifier '{cls.DEBUG_MARKET_IDENTIFIER}' NOT found on default DB right after creation/retrieval.")
            except Exception as e:
                logger.error(f"IMMEDIATE CHECK ERROR: Error fetching market right after creation/retrieval: {e}")
        else:
            logger.error("Market object is None after get_or_create, cannot perform immediate check.")

        logger.info("--- DatabaseSetupTests.setUpTestData END ---")

    def test_database_connections_and_settings(self):
        """测试数据库连接和配置是否正确加载。"""
        logger.info("--- Verifying Database Connections and Settings ---")

        default_db_alias = DEFAULT_DB_ALIAS
        self.assertTrue(default_db_alias in connections.databases,
                        f"Default database alias '{default_db_alias}' not found in connections.")
        default_conn = connections[default_db_alias]
        self.assertIsNotNone(default_conn, "Default database connection is None.")
        logger.info(
            f"Default DB ('{default_conn.alias}') host: {default_conn.settings_dict.get('HOST')}:{default_conn.settings_dict.get('PORT')}, name: {default_conn.settings_dict.get('NAME')}")

        reader_alias = 'slave_replica'
        self.assertTrue(reader_alias in connections.databases,
                        f"Reader database alias '{reader_alias}' not found in connections.")
        reader_conn = connections[reader_alias]
        self.assertIsNotNone(reader_conn, "Reader database connection is None.")
        logger.info(
            f"Reader DB ('{reader_conn.alias}') host: {reader_conn.settings_dict.get('HOST')}:{reader_conn.settings_dict.get('PORT')}, name: {reader_conn.settings_dict.get('NAME')}")

        # 简单连接测试
        try:
            with default_conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                self.assertEqual(cursor.fetchone()[0], 1, "Default DB connection test failed.")
            logger.info(f"Successfully connected to default DB ('{default_conn.alias}').")

            with reader_conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                self.assertEqual(cursor.fetchone()[0], 1, "Reader DB connection test failed.")
            logger.info(f"Successfully connected to reader DB ('{reader_conn.alias}').")
        except Exception as e:
            self.fail(f"Database connection check failed: {e}")

    def test_read_write_splitting(self):
        """测试数据库读写分离是否按预期工作。"""
        logger.info("--- Testing Read-Write Splitting ---")

        # 确保我们有一个干净的测试对象，避免与其他测试冲突
        asset_symbol = "RW_SPLIT_TEST"
        Asset.objects.filter(symbol=asset_symbol).delete()

        try:
            # 1. 写操作
            logger.info(f"Attempting to create asset: {asset_symbol}")
            # 使用事务确保在多数据库测试中的一致性
            with transaction.atomic(using=DEFAULT_DB_ALIAS):
                new_asset = Asset.objects.create(
                    symbol=asset_symbol,
                    name='Read-Write Split Test Coin',
                    uint=8,
                    is_stablecoin=False,
                    status='Active',
                    chain_name='TestChainRW'
                    # 您可能需要根据Asset模型的实际必填字段添加更多默认值
                )
            # Django的create操作后，对象的_state.db可能不会立即反映路由器的选择，
            # 而是可能显示执行创建的数据库（通常是default）。
            # 关键在于验证数据是否真的写入了主库，并且后续读操作是否从从库读取。
            logger.info(
                f"Asset '{new_asset.symbol}' created with ID {new_asset.id}. Object's _state.db: {new_asset._state.db}")

            # 2. 验证数据在主库 (default)
            try:
                # 使用 .using('default') 显式从主库查询
                asset_on_default = Asset.objects.using(DEFAULT_DB_ALIAS).get(symbol=asset_symbol)
                self.assertEqual(asset_on_default.id, new_asset.id)
                logger.info(
                    f"Asset '{asset_on_default.symbol}' confirmed to exist on default DB ('{DEFAULT_DB_ALIAS}').")
            except Asset.DoesNotExist:
                self.fail(f"Asset '{asset_symbol}' was not found on the default DB after creation.")

            # 3. 读操作 (应路由到读副本)
            # 注意：这里有复制延迟的可能性。在自动化测试中，这可能导致间歇性失败。
            read_asset = None
            max_retries = 10
            retry_delay = 1.0

            for attempt in range(max_retries):
                try:
                    # 正常的 .get() 操作应该由路由器导向 'reader'
                    read_asset = Asset.objects.get(symbol=asset_symbol)
                    # 检查返回对象的 _state.db 属性以确认它来自哪个数据库。
                    # 路由器的 db_for_read 应该将此查询路由到 'reader'
                    if read_asset._state.db == 'slave_replica':
                        logger.info(
                            f"Asset '{read_asset.symbol}' successfully read from 'slave_replica' on attempt {attempt + 1}.")
                        break
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1}: Asset '{read_asset.symbol}' read, but from '{read_asset._state.db}' instead of 'slave_replica'. Retrying...")
                except Asset.DoesNotExist:
                    logger.warning(
                        f"Attempt {attempt + 1}: Asset '{asset_symbol}' not found on reader DB. Retrying after {retry_delay}s...")

                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    # 最后一次尝试后，如果仍然失败或来源不对，则执行最终的断言失败
                    if read_asset:
                        self.assertEqual(read_asset._state.db, 'slave_replica',
                                         f"Asset '{read_asset.symbol}' was read from '{read_asset._state.db}' not 'slave_replica' after {max_retries} attempts.")
                    else:
                        # 如果因 Asset.DoesNotExist 退出循环，主动检查一次主库，给出更明确的错误信息
                        try:
                            Asset.objects.using(DEFAULT_DB_ALIAS).get(symbol=asset_symbol)
                            logger.warning(
                                f"Asset '{asset_symbol}' found on default DB but not on reader DB after retries.")
                        except Asset.DoesNotExist:
                            logger.error(
                                f"Asset '{asset_symbol}' does not exist even on default DB after supposed creation.")
                        self.fail(
                            f"Asset '{asset_symbol}' not found on reader DB after {max_retries} attempts. Possible replication lag or other issue.")

            self.assertIsNotNone(read_asset, "read_asset should not be None after successful read.")
            self.assertEqual(read_asset.id, new_asset.id)  # 确保读取到的是同一个对象
            logger.info(f"Asset '{read_asset.symbol}' successfully read and confirmed from: '{read_asset._state.db}'.")

        finally:
            # 清理测试数据
            Asset.objects.filter(symbol=asset_symbol).delete()
            logger.info(f"Cleaned up asset: {asset_symbol}")
