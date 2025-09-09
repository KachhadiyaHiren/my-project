# src/models/task.py
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from functools import wraps
import json

from ..core.base import BaseEntity, Auditable, Priority, TaskStatus
from ..core.interfaces import Notifiable, Searchable, Serializable
from ..core.exceptions import InvalidTaskStateException, ValidationException

# Decorator for state validation
def validate_state_transition(func):
    """Decorator to validate task state transitions"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        old_status = self.status
        result = func(self, *args, **kwargs)
        new_status = self.status
        
        if not self._is_valid_transition(old_status, new_status):
            self.status = old_status  # Revert
            raise InvalidTaskStateException(
                f"Invalid transition from {old_status.value} to {new_status.value}"
            )
        return result
    return wrapper

@dataclass
class TaskMetadata:
    """Value object for task metadata"""
    tags: Set[str] = field(default_factory=set)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    
    def add_tag(self, tag: str) -> None:
        self.tags.add(tag.lower().strip())
    
    def remove_tag(self, tag: str) -> None:
        self.tags.discard(tag.lower().strip())

class TaskDependency:
    """Represents a dependency relationship between tasks"""
    
    def __init__(self, dependent_task_id: str, dependency_type: str = "finish_to_start"):
        self.dependent_task_id = dependent_task_id
        self.dependency_type = dependency_type
        self.created_at = datetime.now()

class Task(BaseEntity, Auditable, Searchable, Serializable):
    """
    Advanced Task class demonstrating multiple inheritance,
    composition, and advanced OOP concepts
    """
    
    # Class variable for valid state transitions
    VALID_TRANSITIONS = {
        TaskStatus.PENDING: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
        TaskStatus.IN_PROGRESS: [TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.CANCELLED],
        TaskStatus.COMPLETED: [TaskStatus.IN_PROGRESS],  # Reopening
        TaskStatus.CANCELLED: [TaskStatus.PENDING]  # Reactivating
    }
    
    def __init__(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        assignee_id: Optional[str] = None,
        due_date: Optional[datetime] = None,
        project_id: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)  # Initialize BaseEntity and Auditable
        
        self.title = self._validate_title(title)
        self.description = description
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.assignee_id = assignee_id
        self.due_date = due_date
        self.project_id = project_id
        
        # Composition - Task has metadata
        self.metadata = TaskMetadata()
        
        # Dependencies and relationships
        self.dependencies: List[TaskDependency] = []
        self.subtasks: List['Task'] = []
        self.parent_task_id: Optional[str] = None
        
        # Observers (for notifications)
        self._observers: List[Notifiable] = []
        
        # State pattern implementation
        self._state_handlers = {
            TaskStatus.PENDING: self._handle_pending_state,
            TaskStatus.IN_PROGRESS: self._handle_in_progress_state,
            TaskStatus.COMPLETED: self._handle_completed_state,
            TaskStatus.CANCELLED: self._handle_cancelled_state
        }
    
    @staticmethod
    def _validate_title(title: str) -> str:
        """Validate task title"""
        if not title or len(title.strip()) < 3:
            raise ValidationException("Task title must be at least 3 characters long")
        return title.strip()
    
    def _is_valid_transition(self, from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check if state transition is valid"""
        return to_status in self.VALID_TRANSITIONS.get(from_status, [])
    
    # Observer pattern implementation
    def add_observer(self, observer: Notifiable) -> None:
        """Add an observer to be notified of task changes"""
        if observer not in self._observers:
            self._observers.append(observer)
    
    def remove_observer(self, observer: Notifiable) -> None:
        """Remove an observer"""
        if observer in self._observers:
            self._observers.remove(observer)
    
    def _notify_observers(self, message: str, data: Dict[str, Any] = None) -> None:
        """Notify all observers of changes"""
        for observer in self._observers:
            observer.notify(message, data or {})
    
    # State management with validation
    @validate_state_transition
    def start_work(self, user_id: str) -> None:
        """Start working on the task"""
        self.status = TaskStatus.IN_PROGRESS
        self.assignee_id = user_id
        self.update_timestamp()
        self.add_audit_entry("start_work", user_id)
        self._notify_observers(f"Task '{self.title}' started", {"task_id": self.id})
    
    @validate_state_transition
    def complete_task(self, user_id: str) -> None:
        """Mark task as completed"""
        if self.subtasks and not all(task.status == TaskStatus.COMPLETED for task in self.subtasks):
            raise InvalidTaskStateException("Cannot complete task with incomplete subtasks")
        
        self.status = TaskStatus.COMPLETED
        self.update_timestamp()
        self.add_audit_entry("complete", user_id)
        self._notify_observers(f"Task '{self.title}' completed", {"task_id": self.id})
    
    @validate_state_transition
    def cancel_task(self, user_id: str, reason: str = "") -> None:
        """Cancel the task"""
        self.status = TaskStatus.CANCELLED
        self.update_timestamp()
        self.add_audit_entry("cancel", user_id, {"reason": reason})
        self._notify_observers(f"Task '{self.title}' cancelled", {"task_id": self.id, "reason": reason})
    
    # State pattern handlers
    def _handle_pending_state(self) -> Dict[str, Any]:
        return {
            "can_start": True,
            "can_edit": True,
            "can_delete": True,
            "progress_percentage": 0
        }
    
    def _handle_in_progress_state(self) -> Dict[str, Any]:
        return {
            "can_start": False,
            "can_edit": True,
            "can_delete": False,
            "progress_percentage": 50  # Could be more sophisticated
        }
    
    def _handle_completed_state(self) -> Dict[str, Any]:
        return {
            "can_start": False,
            "can_edit": False,
            "can_delete": False,
            "progress_percentage": 100
        }
    
    def _handle_cancelled_state(self) -> Dict[str, Any]:
        return {
            "can_start": False,
            "can_edit": False,
            "can_delete": True,
            "progress_percentage": 0
        }
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get information about current state capabilities"""
        handler = self._state_handlers.get(self.status)
        return handler() if handler else {}
    
    # Dependency management
    def add_dependency(self, task_id: str, dependency_type: str = "finish_to_start") -> None:
        """Add a dependency on another task"""
        dependency = TaskDependency(task_id, dependency_type)
        self.dependencies.append(dependency)
        self.update_timestamp()
    
    def remove_dependency(self, task_id: str) -> None:
        """Remove a dependency"""
        self.dependencies = [d for d in self.dependencies if d.dependent_task_id != task_id]
        self.update_timestamp()
    
    def can_start(self, task_repository) -> bool:
        """Check if task can start based on dependencies"""
        for dependency in self.dependencies:
            dependent_task = task_repository.get_by_id(dependency.dependent_task_id)
            if dependent_task and dependent_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    # Subtask management (Composite pattern)
    def add_subtask(self, subtask: 'Task') -> None:
        """Add a subtask"""
        subtask.parent_task_id = self.id
        self.subtasks.append(subtask)
        self.update_timestamp()
    
    def remove_subtask(self, subtask_id: str) -> None:
        """Remove a subtask"""
        self.subtasks = [task for task in self.subtasks if task.id != subtask_id]
        self.update_timestamp()
    
    def get_completion_percentage(self) -> float:
        """Calculate completion percentage including subtasks"""
        if not self.subtasks:
            return 100.0 if self.status == TaskStatus.COMPLETED else 0.0
        
        completed_subtasks = sum(1 for task in self.subtasks if task.status == TaskStatus.COMPLETED)
        return (completed_subtasks / len(self.subtasks)) * 100
    
    # Priority management with business logic
    def escalate_priority(self, user_id: str) -> None:
        """Escalate task priority"""
        old_priority = self.priority
        if self.priority.value < Priority.CRITICAL.value:
            self.priority = Priority(self.priority.value + 1)
            self.update_timestamp()
            self.add_audit_entry("escalate_priority", user_id, {
                "from": old_priority.name,
                "to": self.priority.name
            })
            self._notify_observers(f"Task '{self.title}' priority escalated to {self.priority.name}")
    
    def is_overdue(self) -> bool:
        """Check if task is overdue"""
        return (self.due_date is not None and 
                self.due_date < datetime.now() and 
                self.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED])
    
    def days_until_due(self) -> Optional[int]:
        """Get days until due date"""
        if not self.due_date:
            return None
        delta = self.due_date - datetime.now()
        return delta.days
    
    # Searchable protocol implementation
    def matches_criteria(self, criteria: Dict[str, Any]) -> bool:
        """Check if task matches search criteria"""
        for key, value in criteria.items():
            if key == "title" and value.lower() not in self.title.lower():
                return False
            elif key == "status" and self.status != value:
                return False
            elif key == "priority" and self.priority != value:
                return False
            elif key == "assignee_id" and self.assignee_id != value:
                return False
            elif key == "tags" and not self.metadata.tags.intersection(set(value)):
                return False
            elif key == "overdue" and value and not self.is_overdue():
                return False
        return True
    
    # Serializable protocol implementation
    def serialize(self) -> str:
        """Serialize task to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Task':
        """Deserialize JSON string to Task object"""
        task_data = json.loads(data)
        return cls.from_dict(task_data)
    
    # BaseEntity implementation
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "status": self.status.value,
            "assignee_id": self.assignee_id,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": {
                "tags": list(self.metadata.tags),
                "custom_fields": self.metadata.custom_fields,
                "estimated_hours": self.metadata.estimated_hours,
                "actual_hours": self.metadata.actual_hours
            },
            "dependencies": [
                {"task_id": d.dependent_task_id, "type": d.dependency_type}
                for d in self.dependencies
            ],
            "subtask_ids": [task.id for task in self.subtasks],
            "parent_task_id": self.parent_task_id,
            "version": self.version,
            "audit_log": self.audit_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Create task from dictionary"""
        task = cls(
            title=data["title"],
            description=data.get("description", ""),
            priority=Priority[data.get("priority", "MEDIUM")],
            assignee_id=data.get("assignee_id"),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            project_id=data.get("project_id"),
            id=data.get("id")
        )
        
        task.status = TaskStatus(data.get("status", "pending"))
        
        # Restore metadata
        if "metadata" in data:
            meta = data["metadata"]
            task.metadata.tags = set(meta.get("tags", []))
            task.metadata.custom_fields = meta.get("custom_fields", {})
            task.metadata.estimated_hours = meta.get("estimated_hours")
            task.metadata.actual_hours = meta.get("actual_hours")
        
        # Restore audit info
        task.version = data.get("version", 1)
        task.audit_log = data.get("audit_log", [])
        
        return task
    
    def __str__(self) -> str:
        return f"Task(id={self.id[:8]}, title='{self.title}', status={self.status.value})"
    
    def __repr__(self) -> str:
        return (f"Task(id='{self.id}', title='{self.title}', "
                f"status={self.status.value}, priority={self.priority.name})")