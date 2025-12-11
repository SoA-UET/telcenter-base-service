from .CustomerIdentityService import CustomerIdentityService
from .AuditLoggerService import AuditLogger
from ..collections import customers_collection

# Initialize audit logger
audit_logger = AuditLogger("CustomerIdentityService")

customer_identity_service = CustomerIdentityService(
    collection=customers_collection,
    logger=audit_logger,
)
