from .ConversationService import ConversationService
from .PartnerService import PartnerService
from ..collections import conversations_collection, partners_collection

conversation_service = ConversationService(
    collection=conversations_collection,
)

# S07: Partner Management Service
partner_service = PartnerService(
    collection=partners_collection,
)
