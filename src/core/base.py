from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime
from enum import Enum
import uuid

class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class BaseEntity(ABC):
    """Abstract base class for all entities in the system"""
    
    def __init__(self, id: Optional[str] = None):
        self.id = id or str(uuid.uuid4())
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dictionary representation"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseEntity':
        """Create entity from dictionary"""
        pass
    
    def update_timestamp(self) -> None:
        """Update the last modified timestamp"""
        self.updated_at = datetime.now()

class Auditable(ABC):
    """Mixin for entities that need audit trail"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.version = 1
        self.audit_log: List[Dict[str, Any]] = []
    
    def add_audit_entry(self, action: str, user_id: str, details: Dict[str, Any] = None):
        """Add an entry to the audit log"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'user_id': user_id,
            'version': self.version,
            'details': details or {}
        }
        self.audit_log.append(entry)
        self.version += 1

