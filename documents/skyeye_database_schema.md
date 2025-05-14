# SkyEye 系统数据库表结构文档

## 目录
- [1. 通用模型 (`common.models`)](#1-通用模型-commonmodels)
- [2. `backoffice` 应用模型](#2-backoffice-应用模型)
  - [2.1. MgObPersistence](#21-mgobpersistence)
  - [2.2. OtcAssetPrice](#22-otcassetprice)
  - [2.3. ExchangeRate](#23-exchangerate)
- [3. `exchange` 应用模型](#3-exchange-应用模型)
  - [3.1. Asset](#31-asset)
  - [3.2. Exchange](#32-exchange)
  - [3.3. ExchangeAccount](#33-exchangeaccount)
  - [3.4. Symbol](#34-symbol)
  - [3.5. ExchangeSymbolShip](#35-exchangesymbolship)
- [4. 其他应用](#4-其他应用)
- [Django 内置数据表说明](#django-内置数据表说明)
- [附注](#附注)
- [附录：详细表结构定义 (PostgreSQL 视图)](#附录详细表结构定义-postgresql-视图)
  - [`backoffice.MgObPersistence`](#backofficemgobpersistence)
  - [`backoffice.OtcAssetPrice`](#backofficeotcassetprice)
  - [`backoffice.ExchangeRate`](#backofficeexchangerate)
  - [`exchange.Asset`](#exchangeasset)
  - [`exchange.Exchange`](#exchangeexchange)
  - [`exchange.ExchangeAccount`](#exchangeexchangeaccount)
  - [`exchange.Symbol`](#exchangesymbol)
  - [`exchange.ExchangeSymbolShip` (中间表)](#exchangeexchangesymbolship-中间表)

本文档旨在清晰阐述 SkyEye 项目的数据库表结构。其内容按应用模块介绍各自定义业务模型（基于 Django 模型定义），随后说明 Django 框架的内置数据表，并通过附注提供补充信息。文末附录汇总了核心数据表的详细 PostgreSQL 视图（含字段类型、可空性及参考示例），以供查阅。

## 1. 通用模型 (`common.models`)

### 1.1. BaseModel (抽象基类)
该模型为项目中的其他模型提供基础字段。
- `created_at`: DateTimeField (创建时间, auto_now_add=True, db_index=True)
- `updated_at`: DateTimeField (更新时间, auto_now=True, db_index=True)
*注意: 此模型为抽象模型，不会在数据库中直接创建表。*

## 2. `backoffice` 应用模型

### 2.1. MgObPersistence
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `symbol`: ForeignKey (关联到 `exchange.Symbol`, on_delete=models.CASCADE, null=True, blank=True)
- `exchange`: ForeignKey (关联到 `exchange.Exchange`, on_delete=models.CASCADE, null=True, blank=True)
- `base_asset`: ForeignKey (关联到 `exchange.Asset`, on_delete=models.CASCADE, null=True, blank=True)
- `quote_asset`: ForeignKey (关联到 `exchange.Asset`, on_delete=models.CASCADE, null=True, blank=True)
- `sell_price`: DecField (default=0)
- `buy_price`: DecField (default=0)
- `usd_price`: DecField (default=0)
- `cny_price`: DecField (default=0)
- `avg_price`: DecField (default=0)
- `margin`: DecField (default=0)
- `ratio`: DecField (default=0)

### 2.2. OtcAssetPrice
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `asset`: ForeignKey (关联到 `exchange.Asset`, on_delete=models.CASCADE, null=True, blank=True)
- `usd_price`: DecField (default=0)
- `cny_price`: DecField (default=0)
- `margin`: DecField (default=0)

### 2.3. ExchangeRate
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `base_currency`: CharField (max_length=10, db_index=True, help_text="例如：USD")
- `quote_currency`: CharField (max_length=10, db_index=True, help_text="例如：CNY")
- `rate`: DecField (default=0, help_text="汇率 (1 单位基准货币 = rate * 单位报价货币)")
- `last_updated`: DateTimeField (auto_now=True, help_text="汇率最后更新时间")
- **Meta**:
    - `unique_together`: ('base_currency', 'quote_currency')
    - `verbose_name`: "Exchange Rate"
    - `verbose_name_plural`: "Exchange Rates"

## 3. `exchange` 应用模型

### 3.1. Asset
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `name`: CharField (max_length=100, unique=True, default='BTC', verbose_name='资产名称')
- `unit`: SmallIntegerField (default=8, verbose_name='资产精度')
- `is_stable`: CharField (max_length=100, choices=[('Yes', 'Yes'), ('No', 'No')], default='No', verbose_name='是否为稳定币')
- `status`: CharField (max_length=100, choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', verbose_name='状态')

### 3.2. Exchange
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `name`: CharField (max_length=100, unique=True, verbose_name='交易所名称')
- `config`: TextField (blank=True, verbose_name='配置信息')
- `market_type`: CharField (max_length=100, choices=[('Cex', 'Cex'), ('Dex', 'Dex')], default="Cex", verbose_name='交易所类别')
- `status`: CharField (max_length=100, choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', verbose_name='状态')

### 3.3. ExchangeAccount
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `exchange`: ForeignKey (关联到 `Exchange`, related_name='accounts', on_delete=models.CASCADE)
- `name`: CharField (max_length=100, default='default', db_index=True)
- `api_key`: CharField (max_length=100, null=False)
- `encrypted_secret`: TextField (null=False, blank=True, default='')
- `secret`: CharField (max_length=100, null=False, blank=True, default='', help_text='API Secret Key。重要：实际存储时应采用强加密措施或通过安全配置服务管理，避免直接硬编码或明文存储。')
- `password`: CharField (max_length=100, null=True, default='', blank=True)
- `alias`: CharField (max_length=100, null=True, default='', blank=True)
- `proxy`: TextField (blank=True, null=True)
- `testnet`: BooleanField (default=False, blank=True)
- `status`: CharField (max_length=100, default='ACTIVE')
- `enable`: BooleanField (default=True)
- `info`: TextField (blank=True, null=True)

### 3.4. Symbol
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `name`: CharField (max_length=100, unique=True, verbose_name='交易对名称')
- `base_asset`: ForeignKey (关联到 `Asset`, related_name='base_symbols', null=False, blank=True, on_delete=models.CASCADE, verbose_name='base资产')
- `quote_asset`: ForeignKey (关联到 `Asset`, related_name='quote_symbols', null=False, blank=True, on_delete=models.CASCADE, verbose_name='报价资产')
- `exchanges`: ManyToManyField (关联到 `Exchange`, related_name='symbols', through='ExchangeSymbolShip', verbose_name='关联交易所')
- `status`: CharField (max_length=100, choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', verbose_name='状态')
- `category`: CharField (max_length=100, choices=[('Spot', 'Spot'), ('Future', 'Future'), ('Option', 'Option')], default="Spot")

### 3.5. ExchangeSymbolShip
继承自 `common.BaseModel`。
- `id`: BIGINT (由Django自动生成的自增主键)
- `symbol`: ForeignKey (关联到 `Symbol`, db_index=True, on_delete=models.CASCADE)
- `exchange`: ForeignKey (关联到 `Exchange`, db_index=True, on_delete=models.CASCADE)
- **Meta**:
    - `unique_together`: [("exchange", "symbol")]

## 4. 其他应用
- `dex/models.py`: 无自定义模型
- `frontend/models.py`: 无自定义模型
- `services/models.py`: 无自定义模型

## Django 内置数据表说明

首次运行 `python manage.py migrate` 命令初始化或更新项目数据库时，除了本项目 `backoffice` 和 `exchange` 应用中定义的业务模型所对应的表之外，
Django 框架还会自动创建并管理一系列内置的数据表。这些表是 Django 核心功能（如用户认证、会话管理、后台管理等）所必需的。

以下是这些常见内置表系列的简要说明：

*   **`auth_*` 系列表**：
    *   由 Django 的认证系统 (`django.contrib.auth`) 创建，用于管理用户 (`auth_user`)、用户组 (`auth_group`) 以及它们之间的权限关系 (`auth_permission`, `auth_group_permissions`, `auth_user_groups`, `auth_user_user_permissions`)。
    *   更多详情请参阅: [Django Authentication System Documentation](https://docs.djangoproject.com/en/stable/topics/auth/default/)

*   **`django_*` 系列表**：
    *   `django_admin_log`: 记录 Django Admin 后台管理界面的操作日志 (由 `django.contrib.admin` 使用)。
    *   `django_content_type`: 存储项目中所有模型的元信息，被 Django 的 ContentTypes 框架 (`django.contrib.contenttypes`) 用于通用关系等高级功能。
    *   `django_migrations`: 追踪数据库迁移（migrations）的应用状态。
    *   `django_session`: 当启用会话功能 (`django.contrib.sessions`) 时，用于存储用户会话数据。
    *   更多关于 Django 内置应用和核心功能的详细信息，可以从 Django 官方文档的相应章节找到，例如：
        *   [ContentTypes framework](https://docs.djangoproject.com/en/stable/ref/contrib/contenttypes/)
        *   [Migrations](https://docs.djangoproject.com/en/stable/topics/migrations/)
        *   [Sessions](https://docs.djangoproject.com/en/stable/topics/http/sessions/)
        *   [Admin site](https://docs.djangoproject.com/en/stable/ref/contrib/admin/)

理解这些内置表的存在和作用，有助于全面了解 Django 项目的数据库结构。

## 附注
- 项目中曾评估使用 `CacheManager` (定义于 `common.models` 和 `exchange.models`) 来为部分模型查询提供 Redis 缓存功能，但目前该功能未激活。未来可能根据性能优化需求重新引入。

## 附录：详细表结构定义 (PostgreSQL 视图)

本章节提供了主要数据模型在 PostgreSQL 数据库中的详细表结构信息，包括字段类型、可空性及示例数据。
所有继承自 `common.BaseModel` 的表都包含以下基础字段：
- `id`: `BIGINT PRIMARY KEY` (由Django自动生成的自增主键)
- `created_at`: `TIMESTAMPTZ NOT NULL` (记录创建时间)
- `updated_at`: `TIMESTAMPTZ NOT NULL` (记录最后更新时间)

---

### `backoffice.MgObPersistence`
存储聚合后的市场价格数据。

| 字段名             | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                                                |
|:-------------------|:----------------------|:----------|:----------------------------------------------------------------------------------------------------------|
| `id`               | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                                                           |
| `created_at`       | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-05-20 10:00:00+00`                                                                    |
| `updated_at`       | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-05-20 10:05:00+00`                                                                    |
| `symbol_id`        | `BIGINT`              | NULL      | 关联到 `exchange_symbol` 表 (交易对)。示例: `1` (代表 "BTC/USDT")                                              |
| `exchange_id`      | `BIGINT`              | NULL      | 关联到 `exchange_exchange` 表 (交易所)。示例: `1` (代表 "Binance")                                           |
| `base_asset_id`    | `BIGINT`              | NULL      | 关联到 `exchange_asset` 表 (基础资产)。示例: `1` (代表 "BTC")                                                |
| `quote_asset_id`   | `BIGINT`              | NULL      | 关联到 `exchange_asset` 表 (报价资产)。示例: `2` (代表 "USDT")                                               |
| `sell_price`       | `DECIMAL(38, 4)`      | NOT NULL  | 卖出价。示例: `88095.5000`                                                                                   |
| `buy_price`        | `DECIMAL(38, 4)`      | NOT NULL  | 买入价。示例: `88095.5100`                                                                                   |
| `usd_price`        | `DECIMAL(38, 4)`      | NOT NULL  | 美元计价。示例: `88095.5050`                                                                                 |
| `cny_price`        | `DECIMAL(38, 4)`      | NOT NULL  | 人民币计价。示例: `614906.6249`                                                                               |
| `avg_price`        | `DECIMAL(38, 4)`      | NOT NULL  | 平均价。示例: `88095.5050`                                                                                   |
| `margin`           | `DECIMAL(38, 2)`      | NOT NULL  | 利润率/差价。示例: `0.23`                                                                                    |
| `ratio`            | `DECIMAL(38, 4)`      | NOT NULL  | 比率。示例: `0.0015`                                                                                       |

---

### `backoffice.OtcAssetPrice`
存储资产的场外交易(OTC)价格。

| 字段名          | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                              |
|:----------------|:----------------------|:----------|:------------------------------------------------------------------------|
| `id`            | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                           |
| `created_at`    | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-05-20 11:00:00+00`                                  |
| `updated_at`    | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-05-20 11:05:00+00`                                  |
| `asset_id`      | `BIGINT`              | NULL      | 关联到 `exchange_asset` 表。示例: `1` (代表 "BTC")                         |
| `usd_price`     | `DECIMAL(38, 4)`      | NOT NULL  | 美元计价。示例: `88132.0750`                                              |
| `cny_price`     | `DECIMAL(38, 4)`      | NOT NULL  | 人民币计价。示例: `643143.8173`                                            |
| `margin`        | `DECIMAL(38, 4)`      | NOT NULL  | 利润率/差价。示例: `0.0000`                                                 |

---

### `backoffice.ExchangeRate`
存储货币间的汇率。

| 字段名             | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                                                |
|:-------------------|:----------------------|:----------|:----------------------------------------------------------------------------------------------------------|
| `id`               | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                                                           |
| `created_at`       | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-05-19 00:00:00+00`                                                                    |
| `updated_at`       | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-05-20 08:00:00+00`                                                                    |
| `base_currency`    | `VARCHAR(10)`         | NOT NULL  | 基准货币 (有索引, `help_text="例如：USD"`)。示例: `"USD"`                                                    |
| `quote_currency`   | `VARCHAR(10)`         | NOT NULL  | 报价货币 (有索引, `help_text="例如：CNY"`)。示例: `"CNY"`                                                    |
| `rate`             | `DECIMAL(38, 6)`      | NOT NULL  | 汇率 (1 基准货币 = rate * 报价货币, `help_text="1 单位基准货币 = rate * 单位报价货币"`)。示例: `7.251234`                                      |
| `last_updated`     | `TIMESTAMPTZ`         | NOT NULL  | 汇率最后更新时间 (auto_now=True, `help_text="汇率记录的最后更新时间"`)。示例: `2024-05-20 08:00:00+00`                            |
_Meta: (`base_currency`, `quote_currency`) 组合唯一。 `verbose_name="Exchange Rate"`_

---

### `exchange.Asset`
存储资产（如加密货币）信息。

| 字段名          | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                |
|:----------------|:----------------------|:----------|:--------------------------------------------------------------------------|
| `id`            | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                             |
| `created_at`    | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-01-01 00:00:00+00`                                    |
| `updated_at`    | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-01-01 00:00:00+00`                                    |
| `name`          | `VARCHAR(100)`        | NOT NULL  | 资产名称 (唯一, `verbose_name='资产名称'`)。示例: `"BTC"`                       |
| `unit`          | `SMALLINT`            | NOT NULL  | 资产精度 (默认 8, `verbose_name='资产精度'`)。示例: `8`                         |
| `is_stable`     | `VARCHAR(100)`        | NOT NULL  | 是否为稳定币 (choices, 默认 'No', `verbose_name='是否为稳定币'`)。示例: `"No"` |
| `status`        | `VARCHAR(100)`        | NOT NULL  | 状态 (choices, 默认 'Active', `verbose_name='状态'`)。示例: `"Active"`        |

---

### `exchange.Exchange`
存储交易所信息。

| 字段名             | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                    |
|:-------------------|:----------------------|:----------|:------------------------------------------------------------------------------|
| `id`               | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                                 |
| `created_at`       | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-01-01 00:00:00+00`                                        |
| `updated_at`       | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-01-01 00:00:00+00`                                        |
| `name`             | `VARCHAR(100)`        | NOT NULL  | 交易所名称 (唯一, `verbose_name='交易所名称'`)。示例: `"Binance"`                 |
| `config`           | `TEXT`                | NULL      | 配置信息 (可空, `verbose_name='配置信息'`)。示例: `"{ \"rate_limit\": 1200 }"` | 
| `market_type`      | `VARCHAR(100)`        | NOT NULL  | 交易所类别 (choices, 默认 "Cex", `verbose_name='交易所类别'`)。示例: `"Cex"`    |
| `status`           | `VARCHAR(100)`        | NOT NULL  | 状态 (choices, 默认 'Active', `verbose_name='状态'`)。示例: `"Active"`          |

---

### `exchange.ExchangeAccount`
存储交易所账户凭证和配置。

| 字段名                | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                      |
|:----------------------|:----------------------|:----------|:--------------------------------------------------------------------------------|
| `id`                  | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                                   |
| `created_at`          | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-01-10 09:00:00+00`                                          |
| `updated_at`          | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-03-15 14:30:00+00`                                          |
| `exchange_id`         | `BIGINT`              | NOT NULL  | 关联到 `exchange_exchange` 表。示例: `1` (Binance)                                |
| `name`                | `VARCHAR(100)`        | NOT NULL  | 账户名称 (默认 'default', 有索引)。示例: `"user_main_cex_account"`                   |
| `api_key`             | `VARCHAR(100)`        | NOT NULL  | API Key。示例: `"abcdef12345..."`                                                 |
| `encrypted_secret`    | `TEXT`                | NOT NULL  | 加密后的 Secret Key (默认空字符串)。示例: `"encrypted:gAAAAAB..."`                 |
| `secret`              | `VARCHAR(100)`        | NOT NULL  | API Secret Key。重要：实际存储时应通过如环境变量、Vault、或项目内建加密服务等安全机制进行管理，避免直接硬编码或以明文形式存储在数据库或代码中。模型定义中的 `default=''` 主要用于 ORM 层面，不代表推荐的生产环境存储方式。示例：(生产环境中不应直接存储明文) |
| `password`            | `VARCHAR(100)`        | NULL      | 账户密码 (可选)。示例: `"**********"`                                             |
| `alias`               | `VARCHAR(100)`        | NULL      | 别名 (可选)。示例: `"My Primary Binance Account"`                                  |
| `proxy`               | `TEXT`                | NULL      | 代理配置 (可选)。示例: `"http://user:pass@proxyserver:port"`                        |
| `testnet`             | `BOOLEAN`             | NOT NULL  | 是否为测试网账户 (默认 False)。示例: `false`                                        |
| `status`              | `VARCHAR(100)`        | NOT NULL  | 账户状态 (默认 'ACTIVE')。示例: `"ACTIVE"`                                        |
| `enable`              | `BOOLEAN`             | NOT NULL  | 是否启用该账户 (默认 True)。示例: `true`                                          |
| `info`                | `TEXT`                | NULL      | 其他信息 (可选)。示例: `"{ \"subaccount_id\": \"sub123\" }"`                        |

---

### `exchange.Symbol`
存储交易对信息。

| 字段名             | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                                            |
|:-------------------|:----------------------|:----------|:--------------------------------------------------------------------------------------|
| `id`               | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                                         |
| `created_at`       | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-01-05 12:00:00+00`                                                |
| `updated_at`       | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-01-05 12:00:00+00`                                                |
| `name`             | `VARCHAR(100)`        | NOT NULL  | 交易对名称 (唯一, `verbose_name='交易对名称'`)。示例: `"BTC/USDT"`                         |
| `base_asset_id`    | `BIGINT`              | NOT NULL  | 关联到 `exchange_asset` 表 (基础资产, `verbose_name='base资产'`)。示例: `1` (BTC)         |
| `quote_asset_id`   | `BIGINT`              | NOT NULL  | 关联到 `exchange_asset` 表 (报价资产, `verbose_name='报价资产'`)。示例: `2` (USDT)        |
| `status`           | `VARCHAR(100)`        | NOT NULL  | 状态 (choices, 默认 'Active', `verbose_name='状态'`)。示例: `"Active"`                  |
| `category`         | `VARCHAR(100)`        | NOT NULL  | 交易对类别 (choices, 默认 "Spot")。示例: `"Spot"`                                       |
_Note: `exchanges` ManyToManyField 关联通过 `ExchangeSymbolShip` 表实现。_

---

### `exchange.ExchangeSymbolShip` (中间表)
交易所和交易对的多对多关联表。

| 字段名          | 数据类型 (PostgreSQL) | 可空性    | 描述与示例                                                              |
|:----------------|:----------------------|:----------|:------------------------------------------------------------------------|
| `id`            | `BIGINT`              | NOT NULL  | 主键。示例: `1`                                                           |
| `created_at`    | `TIMESTAMPTZ`         | NOT NULL  | 创建时间。示例: `2024-01-05 12:00:00+00`                                  |
| `updated_at`    | `TIMESTAMPTZ`         | NOT NULL  | 更新时间。示例: `2024-01-05 12:00:00+00`                                  |
| `symbol_id`     | `BIGINT`              | NOT NULL  | 关联到 `exchange_symbol` 表 (有索引)。示例: `1` (BTC/USDT)                 |
| `exchange_id`   | `BIGINT`              | NOT NULL  | 关联到 `exchange_exchange` 表。示例: `1` (Binance)