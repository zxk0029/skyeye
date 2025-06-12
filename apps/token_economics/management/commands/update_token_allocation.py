from django.core.management.base import BaseCommand

from apps.token_economics.services import CMCAllocationService
from apps.token_unlocks.models import TokenUnlock


class Command(BaseCommand):
    help = '从CoinMarketCap更新代币分配数据'

    def add_arguments(self, parser):
        parser.add_argument('cmc_id', type=int, nargs='?', default=None, help='代币的CMC ID，若不提供则更新所有TokenUnlock记录')

    def handle(self, *args, **options):
        cmc_id = options.get('cmc_id')
        if cmc_id:
            # 单个代币更新
            try:
                self.stdout.write(self.style.SUCCESS(f'开始更新代币(CMC ID:{cmc_id})的分配数据...'))
                result = CMCAllocationService.update_allocation(cmc_id)
                self.stdout.write(self.style.SUCCESS(f'代币分配数据更新成功: {result["token"]}代币，{result["categories_created"]}个分配类别'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'更新失败: {str(e)}'))
        else:
            # 批量更新所有 TokenUnlock 中的代币
            total = TokenUnlock.objects.count()
            success = 0
            fail = 0
            for token in TokenUnlock.objects.all():
                try:
                    self.stdout.write(self.style.SUCCESS(f'开始更新代币(CMC ID:{token.cmc_id})的分配数据...'))
                    CMCAllocationService.update_allocation(token.cmc_id)
                    success += 1
                except Exception as e:
                    fail += 1
                    self.stdout.write(self.style.ERROR(f'更新代币ID {token.cmc_id} 失败: {str(e)}'))
            self.stdout.write(self.style.SUCCESS(f'批量更新完成: 总共{total}个，成功{success}个，失败{fail}个'))
