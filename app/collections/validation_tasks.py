"""
Collection model for validation_tasks in S05 Knowledge Validator Service

Database: telcenter_core_s05
Collection: validation_tasks

Schema:
- _id (ObjectId, primary key): ID định danh tác vụ
- seaweed_file_id (string): ID file JSON trên SeaweedFS (dữ liệu đầu vào)
- partner_id (string, nullable): Partner gửi request (null nếu từ Core Portal)
- status (string): pending / approved / rejected
- validator_id (string): ID người/service thực hiện validate
- created_at (datetime): Thời gian tạo
- validated_at (datetime, nullable): Thời gian hoàn thành validate (optional)
"""

from datetime import datetime
from typing import Optional, TypedDict


class ValidationTask(TypedDict):
    """Type definition for validation_tasks document"""
    seaweed_file_id: str
    partner_id: Optional[str]
    status: str  # pending, approved, rejected
    validator_id: Optional[str]
    created_at: datetime
    validated_at: Optional[datetime]


def create_validation_task_indexes(collection):
    """Create indexes for validation_tasks collection"""
    collection.create_index("status")
    collection.create_index("partner_id")
    collection.create_index("created_at")
    collection.create_index([("created_at", -1)])
