# src/patterns/factory.py - Factory Pattern Implementation
from abc import ABC, abstractmethod
from typing import Dict, Any, Type
from datetime import datetime, timedelta

from ..models.task import Task, Priority, TaskStatus
from ..core.exceptions import ValidationException

class TaskFactory(ABC):
    """Abstract factory for creating tasks"""
    
    @abstractmethod
    def create_task(self, **kwargs) -> Task:
        pass

class SimpleTaskFactory(TaskFactory):
    """Factory for creating simple tasks"""
    
    def create_task(self, title: str, description: str = "", **kwargs) -> Task:
        return Task(
            title=title,
            description=description,
            priority=kwargs.get('priority', Priority.MEDIUM),
            **kwargs
        )

class UrgentTaskFactory(TaskFactory):
    """Factory for creating urgent tasks with specific defaults"""
    
    def create_task(self, title: str, **kwargs) -> Task:
        # Urgent tasks have high priority and short deadline
        due_date = kwargs.get('due_date') or datetime.now() + timedelta(days=1)
        
        task = Task(
            title=f"[URGENT] {title}",
            priority=Priority.HIGH,
            due_date=due_date,
            **kwargs
        )
        
        # Add urgent tag
        task.metadata.add_tag("urgent")
        return task

class ProjectTaskFactory(TaskFactory):
    """Factory for creating project-related tasks"""
    
    def __init__(self, project_id: str, default_assignee: str = None):
        self.project_id = project_id
        self.default_assignee = default_assignee
    
    def create_task(self, title: str, **kwargs) -> Task:
        return Task(
            title=title,
            project_id=self.project_id,
            assignee_id=kwargs.get('assignee_id') or self.default_assignee,
            **kwargs
        )

class TaskFactoryRegistry:
    """Registry pattern for managing task factories"""
    
    def __init__(self):
        self._factories: Dict[str, TaskFactory] = {}
    
    def register_factory(self, name: str, factory: TaskFactory) -> None:
        """Register a task factory"""
        self._factories[name] = factory
    
    def create_task(self, factory_name: str, **kwargs) -> Task:
        """Create a task using specified factory"""
        if factory_name not in self._factories:
            raise ValidationException(f"Unknown factory: {factory_name}")
        
        factory = self._factories[factory_name]
        return factory.create_task(**kwargs)
    
    def get_available_factories(self) -> list:
        """Get list of available factory names"""
        return list(self._factories.keys())

# src/patterns/strategy.py - Strategy Pattern Implementation
class TaskSortingStrategy(ABC):
    """Abstract strategy for sorting tasks"""
    
    @abstractmethod
    def sort(self, tasks: list) -> list:
        pass

class PrioritySortStrategy(TaskSortingStrategy):
    """Sort tasks by priority (highest first)"""
    
    def sort(self, tasks: list) -> list:
        return sorted(tasks, key=lambda t: t.priority.value, reverse=True)

class DueDateSortStrategy(TaskSortingStrategy):
    """Sort tasks by due date (earliest first)"""
    
    def sort(self, tasks: list) -> list:
        # Tasks without due date go to the end
        return sorted(
            tasks, 
            key=lambda t: t.due_date if t.due_date else datetime.max
        )

class StatusSortStrategy(TaskSortingStrategy):
    """Sort tasks by status (in-progress, pending, completed, cancelled)"""
    
    STATUS_ORDER = {
        TaskStatus.IN_PROGRESS: 1,
        TaskStatus.PENDING: 2,
        TaskStatus.COMPLETED: 3,
        TaskStatus.CANCELLED: 4
    }
    
    def sort(self, tasks: list) -> list:
        return sorted(tasks, key=lambda t: self.STATUS_ORDER.get(t.status, 5))

class TaskFilterStrategy(ABC):
    """Abstract strategy for filtering tasks"""
    
    @abstractmethod
    def filter(self, tasks: list) -> list:
        pass

class OverdueFilterStrategy(TaskFilterStrategy):
    """Filter for overdue tasks"""
    
    def filter(self, tasks: list) -> list:
        return [task for task in tasks if task.is_overdue()]

class AssigneeFilterStrategy(TaskFilterStrategy):
    """Filter tasks by assignee"""
    
    def __init__(self, assignee_id: str):
        self.assignee_id = assignee_id
    
    def filter(self, tasks: list) -> list:
        return [task for task in tasks if task.assignee_id == self.assignee_id]

class PriorityFilterStrategy(TaskFilterStrategy):
    """Filter tasks by minimum priority level"""
    
    def __init__(self, min_priority: Priority):
        self.min_priority = min_priority
    
    def filter(self, tasks: list) -> list:
        return [task for task in tasks if task.priority.value >= self.min_priority.value]

class TaskQueryProcessor:
    """Context class for using sorting and filtering strategies"""
    
    def __init__(self):
        self.sort_strategy: TaskSortingStrategy = PrioritySortStrategy()
        self.filter_strategies: list = []
    
    def set_sort_strategy(self, strategy: TaskSortingStrategy) -> None:
        """Set the sorting strategy"""
        self.sort_strategy = strategy
    
    def add_filter_strategy(self, strategy: TaskFilterStrategy) -> None:
        """Add a filter strategy"""
        self.filter_strategies.append(strategy)
    
    def clear_filters(self) -> None:
        """Clear all filter strategies"""
        self.filter_strategies.clear()
    
    def process(self, tasks: list) -> list:
        """Apply filters and sorting to tasks"""
        filtered_tasks = tasks
        
        # Apply all filters
        for filter_strategy in self.filter_strategies:
            filtered_tasks = filter_strategy.filter(filtered_tasks)
        
        # Apply sorting
        return self.sort_strategy.sort(filtered_tasks)

# src/patterns/observer.py - Observer Pattern Implementation
from typing import List, Dict, Any
from ..core.interfaces import Notifiable

class TaskNotificationManager:
    """Concrete observer for task notifications"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.notifications: List[Dict[str, Any]] = []
    
    def notify(self, message: str, data: Dict[str, Any] = None) -> None:
        """Receive and store notification"""
        notification = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'data': data or {},
            'user_id': self.user_id,
            'read': False
        }
        self.notifications.append(notification)
        self._send_notification(notification)
    
    def _send_notification(self, notification: Dict[str, Any]) -> None:
        """Send notification (could be email, push, etc.)"""
        # In a real system, this would send actual notifications
        print(f"📧 Notification for {self.user_id}: {notification['message']}")
    
    def get_unread_notifications(self) -> List[Dict[str, Any]]:
        """Get all unread notifications"""
        return [n for n in self.notifications if not n['read']]
    
    def mark_as_read(self, notification_index: int) -> None:
        """Mark a notification as read"""
        if 0 <= notification_index < len(self.notifications):
            self.notifications[notification_index]['read'] = True

class EmailNotifier(Notifiable):
    """Email notification observer"""
    
    def __init__(self, email_service):
        self.email_service = email_service
    
    def notify(self, message: str, data: Dict[str, Any] = None) -> None:
        """Send email notification"""
        # In real implementation, would send actual email
        print(f"📨 Email: {message}")

class SlackNotifier(Notifiable):
    """Slack notification observer"""
    
    def __init__(self, slack_channel: str):
        self.slack_channel = slack_channel
    
    def notify(self, message: str, data: Dict[str, Any] = None) -> None:
        """Send Slack notification"""
        print(f"💬 Slack #{self.slack_channel}: {message}")

class DatabaseAuditObserver(Notifiable):
    """Observer that logs changes to database"""
    
    def __init__(self, audit_repository):
        self.audit_repository = audit_repository
    
    def notify(self, message: str, data: Dict[str, Any] = None) -> None:
        """Log change to audit database"""
        audit_entry = {
            'timestamp': datetime.now(),
            'event': message,
            'data': data or {}
        }
        # self.audit_repository.save(audit_entry)
        print(f"🗄️ Audit log: {message}")

# Singleton pattern for notification manager
class NotificationCenter:
    """Singleton notification center"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NotificationCenter, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not NotificationCenter._initialized:
            self.observers: Dict[str, List[Notifiable]] = {}
            NotificationCenter._initialized = True
    
    def subscribe(self, event_type: str, observer: Notifiable) -> None:
        """Subscribe observer to event type"""
        if event_type not in self.observers:
            self.observers[event_type] = []
        if observer not in self.observers[event_type]:
            self.observers[event_type].append(observer)
    
    def unsubscribe(self, event_type: str, observer: Notifiable) -> None:
        """Unsubscribe observer from event type"""
        if event_type in self.observers and observer in self.observers[event_type]:
            self.observers[event_type].remove(observer)
    
    def notify_all(self, event_type: str, message: str, data: Dict[str, Any] = None) -> None:
        """Notify all observers of an event type"""
        if event_type in self.observers:
            for observer in self.observers[event_type]:
                observer.notify(message, data)

# Command pattern for task operations
class Command(ABC):
    """Abstract command interface"""
    
    @abstractmethod
    def execute(self) -> Any:
        pass
    
    @abstractmethod
    def undo(self) -> Any:
        pass

class CreateTaskCommand(Command):
    """Command to create a task"""
    
    def __init__(self, task_repository, task_data: Dict[str, Any]):
        self.task_repository = task_repository
        self.task_data = task_data
        self.created_task = None
    
    def execute(self) -> Task:
        """Execute task creation"""
        factory = SimpleTaskFactory()
        self.created_task = factory.create_task(**self.task_data)
        self.task_repository.save(self.created_task)
        return self.created_task
    
    def undo(self) -> None:
        """Undo task creation"""
        if self.created_task:
            self.task_repository.delete(self.created_task.id)

class UpdateTaskCommand(Command):
    """Command to update a task"""
    
    def __init__(self, task_repository, task_id: str, updates: Dict[str, Any]):
        self.task_repository = task_repository
        self.task_id = task_id
        self.updates = updates
        self.original_state = None
    
    def execute(self) -> Task:
        """Execute task update"""
        task = self.task_repository.get_by_id(self.task_id)
        if not task:
            raise TaskNotFoundException(f"Task {self.task_id} not found")
        
        # Store original state for undo
        self.original_state = task.to_dict()
        
        # Apply updates
        for key, value in self.updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        task.update_timestamp()
        self.task_repository.save(task)
        return task
    
    def undo(self) -> None:
        """Undo task update"""
        if self.original_state:
            task = Task.from_dict(self.original_state)
            self.task_repository.save(task)

class DeleteTaskCommand(Command):
    """Command to delete a task"""
    
    def __init__(self, task_repository, task_id: str):
        self.task_repository = task_repository
        self.task_id = task_id
        self.deleted_task = None
    
    def execute(self) -> bool:
        """Execute task deletion"""
        self.deleted_task = self.task_repository.get_by_id(self.task_id)
        if not self.deleted_task:
            raise TaskNotFoundException(f"Task {self.task_id} not found")
        
        return self.task_repository.delete(self.task_id)
    
    def undo(self) -> None:
        """Undo task deletion"""
        if self.deleted_task:
            self.task_repository.save(self.deleted_task)

class CommandInvoker:
    """Command invoker with undo/redo functionality"""
    
    def __init__(self):
        self.history: List[Command] = []
        self.current_position = -1
    
    def execute_command(self, command: Command) -> Any:
        """Execute a command and add to history"""
        result = command.execute()
        
        # Remove any commands after current position (for redo after undo)
        self.history = self.history[:self.current_position + 1]
        
        # Add new command
        self.history.append(command)
        self.current_position += 1
        
        return result
    
    def undo(self) -> bool:
        """Undo the last command"""
        if self.current_position >= 0:
            command = self.history[self.current_position]
            command.undo()
            self.current_position -= 1
            return True
        return False
    
    def redo(self) -> bool:
        """Redo the next command"""
        if self.current_position < len(self.history) - 1:
            self.current_position += 1
            command = self.history[self.current_position]
            command.execute()
            return True
        return False
    
    def can_undo(self) -> bool:
        """Check if undo is possible"""
        return self.current_position >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible"""
        return self.current_position < len(self.history) - 1