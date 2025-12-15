from .ConversationService import ConversationService
from .MetricsService import MetricsService
from ..collections import conversations_collection

conversation_service = ConversationService(
    collection=conversations_collection,
)

# MetricsService instance - will be created in __main__.py
# and set via set_metrics_service() in controllers
metrics_service: MetricsService | None = None
