from django.core.management.base import BaseCommand
from apps.token_unlocks.services import CMCUnlockService


class Command(BaseCommand):
    help = '从CoinMarketCap更新代币解锁数据'

    def handle(self, *args, **options):
        try:
            self.stdout.write(self.style.SUCCESS('开始更新代币解锁数据...'))
            result = CMCUnlockService.update_unlocks()
            self.stdout.write(self.style.SUCCESS(f'代币解锁数据更新成功: 新增{result["created"]}个，更新{result["updated"]}个'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'更新失败: {str(e)}'))
