from .ConversationService import ConversationService
from .PartnerMetricsService import PartnerMetricsService
from ..collections import conversations_collection

conversation_service = ConversationService(
    collection=conversations_collection,
)

# S14 Partner Metrics Service - singleton instance
partner_metrics_service = PartnerMetricsService()
