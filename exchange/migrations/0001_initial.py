# Generated by Django 2.2.3 on 2022-08-07 08:28

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(default='BTC', max_length=100, unique=True, verbose_name='资产名称')),
                ('unit', models.SmallIntegerField(default=8, verbose_name='资产精度')),
                ('status',
                 models.CharField(choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', max_length=100,
                                  verbose_name='状态')),
            ],
        ),
        migrations.CreateModel(
            name='Exchange',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='交易所名称')),
                ('config', models.TextField(blank=True, verbose_name='配置信息')),
                ('market_type',
                 models.CharField(choices=[('Cex', 'Cex'), ('Dex', 'Dex')], default='Cex', max_length=100,
                                  verbose_name='交易所类别')),
                ('status',
                 models.CharField(choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', max_length=100,
                                  verbose_name='状态')),
            ],
        ),
        migrations.CreateModel(
            name='ExchangeSymbolShip',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('exchange', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='exchange.Exchange')),
            ],
        ),
        migrations.CreateModel(
            name='Symbol',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(max_length=100, unique=True, verbose_name='交易对名称')),
                ('status',
                 models.CharField(choices=[('Active', 'Active'), ('Down', 'Down')], default='Active', max_length=100,
                                  verbose_name='状态')),
                ('category', models.CharField(choices=[('Spot', 'Spot'), ('Future', 'Future'), ('Option', 'Option')],
                                              default='Spot', max_length=100)),
                ('base_asset',
                 models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='base_symbols',
                                   to='exchange.Asset', verbose_name='base资产')),
                ('exchanges', models.ManyToManyField(related_name='symbols', through='exchange.ExchangeSymbolShip',
                                                     to='exchange.Exchange', verbose_name='关联交易所')),
                ('quote_asset', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE,
                                                  related_name='quote_symbols', to='exchange.Asset',
                                                  verbose_name='报价资产')),
            ],
        ),
        migrations.AddField(
            model_name='exchangesymbolship',
            name='symbol',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='exchange.Symbol'),
        ),
        migrations.CreateModel(
            name='ExchangeAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('name', models.CharField(db_index=True, default='default', max_length=100)),
                ('api_key', models.CharField(max_length=100)),
                ('encrypted_secret', models.TextField(blank=True, default='')),
                ('secret', models.CharField(blank=True, default='', max_length=100)),
                ('password', models.CharField(blank=True, default='', max_length=100, null=True)),
                ('alias', models.CharField(blank=True, default='', max_length=100, null=True)),
                ('proxy', models.TextField(blank=True, null=True)),
                ('testnet', models.BooleanField(blank=True, default=False)),
                ('status', models.CharField(default='ACTIVE', max_length=100)),
                ('enable', models.BooleanField(default=True)),
                ('info', models.TextField(blank=True, null=True)),
                ('exchange', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accounts',
                                               to='exchange.Exchange')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='exchangesymbolship',
            unique_together={('exchange', 'symbol')},
        ),
    ]
