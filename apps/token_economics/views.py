from rest_framework.views import APIView

from apps.token_economics.models import TokenAllocation
from apps.token_economics.serializers import TokenAllocationSerializer
from common.helpers import ok_json, error_json


class TokenAllocationView(APIView):
    """
    获取代币分配信息的API
    """

    def get(self, request):
        cmc_id = request.GET.get('cmc_id')
        if not cmc_id:
            return error_json("参数cmc_id是必须的", code=400, status=400)
        try:
            token_allocation = TokenAllocation.objects.get(cmc_id=cmc_id)
            serializer = TokenAllocationSerializer(token_allocation)
            return ok_json(serializer.data)
        except TokenAllocation.DoesNotExist:
            return error_json(f"未找到cmc_id为{cmc_id}的代币分配数据", code=404, status=404)
