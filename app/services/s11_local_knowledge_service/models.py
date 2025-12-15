"""
Data models for S11 Local Knowledge Service
"""
from typing import Optional, Any
from dataclasses import dataclass, asdict
import json


@dataclass
class Package:
    """Package (Gói cước) model"""
    partner_id: int
    code: str
    meta_data: dict
    id: Optional[int] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "partner_id": self.partner_id,
            "code": self.code,
            "meta_data": json.dumps(self.meta_data, ensure_ascii=False) if isinstance(self.meta_data, dict) else self.meta_data
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        meta_data = data.get("meta_data", "{}")
        if isinstance(meta_data, str):
            meta_data = json.loads(meta_data)
        return cls(
            id=data.get("id"),
            partner_id=data.get("partner_id"),
            code=data.get("code"),
            meta_data=meta_data
        )


@dataclass
class FAQ:
    """FAQ (Câu hỏi thường gặp) model"""
    partner_id: int
    question: str
    answer: str
    category: Optional[str] = None
    id: Optional[int] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "partner_id": self.partner_id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data.get("id"),
            partner_id=data.get("partner_id"),
            question=data.get("question"),
            answer=data.get("answer"),
            category=data.get("category")
        )
