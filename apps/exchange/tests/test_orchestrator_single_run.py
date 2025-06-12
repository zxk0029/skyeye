from django.test import TestCase


from apps.exchange.services.stablecoin_price_service_orchestrator import StablecoinPriceServiceOrchestrator


class TestOrchestratorSingleRun(TestCase):

    def setUp(self):
        self.orchestrator = StablecoinPriceServiceOrchestrator(
            exclude_exchanges_cli=[],
            only_exchanges_cli=[]
        )

    async def test_single_run_fetch_all_available_true(self):
        pass
