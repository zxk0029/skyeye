from django.views.decorators.http import require_http_methods

from apps.token_holdings.services import TokenHoldingsService
from common.helpers import ok_json, error_json, getLogger

logger = getLogger(__name__)


@require_http_methods(["GET"])
async def token_holdings_api(request):
    cmc_id = None
    try:
        cmc_id = request.GET.get('cmc_id')
        if not cmc_id:
            return error_json('cmc_id parameter is required', code=400, status=400)
        
        try:
            cmc_id = int(cmc_id)
        except ValueError:
            return error_json('cmc_id must be a valid integer', code=400, status=400)
        
        async with TokenHoldingsService() as service:
            holdings_data = await service.get_token_holdings_summary(cmc_id)
            
            if not holdings_data:
                return error_json(f'No holdings data found for CMC ID {cmc_id}', code=404, status=404)
            
            return ok_json(holdings_data)
            
    except Exception as e:
        logger.error(f"Error in token_holdings_api for CMC ID {cmc_id}: {str(e)}")
        return error_json('Internal server error', code=500, status=500)