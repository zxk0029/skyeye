from rest_framework.views import APIView
from django.utils import timezone

from apps.token_unlocks.models import TokenUnlock
from apps.token_unlocks.serializers import TokenUnlockDetailSerializer
from common.helpers import ok_json, paged_items, parse_int, PAGE_SIZE


class TokenUnlockView(APIView):
    """
    获取代币解锁信息的API
    """
    def get(self, request):
        page_size = parse_int(request.GET.get('page_size', PAGE_SIZE), PAGE_SIZE)
        if page_size < 1:
            page_size = PAGE_SIZE
        # 只查未来有解锁事件的代币
        qs = TokenUnlock.objects.filter(next_unlock_date__gte=timezone.now()).order_by('id')
        items = paged_items(request, qs, pagesize=page_size)
        # 序列化页面对象列表
        serializer = TokenUnlockDetailSerializer(items.object_list, many=True)
        return ok_json({
            "page": items.number,
            "pages": items.paginator.num_pages,
            "total": items.paginator.count,
            "results": serializer.data,
        })
