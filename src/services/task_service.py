# src/services/task_service.py
from typing import List, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from functools import wraps
from datetime import datetime, timedelta
import threading
import time

from ..models.task import Task, Priority, TaskStatus
from ..patterns.factory import TaskFactoryRegistry, SimpleTaskFactory, UrgentTaskFactory
from ..patterns.strategy import TaskQueryProcessor, PrioritySortStrategy, OverdueFilterStrategy
from ..patterns.observer import NotificationCenter
from ..core.exceptions import TaskNotFoundException, PermissionDeniedException, ValidationException

# Repository Pattern
class TaskRepository(ABC):
    """Abstract repository for task data access"""
    
    @abstractmethod
    def save(self, task: Task) -> Task:
        """Save a task"""
        pass
    
    @abstractmethod
    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        pass
    
    @abstractmethod
    def get_all(self) -> List[Task]:
        """Get all tasks"""
        pass
    
    @abstractmethod
    def delete(self, task_id: str) -> bool:
        """Delete a task"""
        pass
    
    @abstractmethod
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Task]:
        """Find tasks matching criteria"""
        pass

class InMemoryTaskRepository(TaskRepository):
    """In-memory implementation of task repository"""
    
    def __init__(self):
        self._tasks: Dict[str, Task] = {}
        self._lock = threading.RLock()  # Thread-safe operations
    
    def save(self, task: Task) -> Task:
        """Save a task to memory"""
        with self._lock:
            self._tasks[task.id] = task
            return task
    
    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all(self) -> List[Task]:
        """Get all tasks"""
        with self._lock:
            return list(self._tasks.values())
    
    def delete(self, task_id: str) -> bool:
        """Delete a task"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False
    
    def find_by_criteria(self, criteria: Dict[str, Any]) -> List[Task]:
        """Find tasks matching criteria"""
        with self._lock:
            return [task for task in self._tasks.values() 
                   if task.matches_criteria(criteria)]
    
    def get_tasks_by_assignee(self, assignee_id: str) -> List[Task]:
        """Get tasks assigned to a specific user"""
        return self.find_by_criteria({"assignee_id": assignee_id})
    
    def get_tasks_by_project(self, project_id: str) -> List[Task]:
        """Get tasks for a specific project"""
        return self.find_by_criteria({"project_id": project_id})

# Decorator for method timing
def measure_execution_time(func):
    """Decorator to measure method execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"⏱️ {func.__name__} executed in {end_time - start_time:.4f} seconds")
        return result
    return wrapper

# Decorator for permission checking
def require_permission(permission: str):
    """Decorator to check user permissions"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # First argument should be user_id for permission checking
            if args and hasattr(self, '_check_permission'):
                user_id = args[0] if isinstance(args[0], str) else kwargs.get('user_id')
                if user_id and not self._check_permission(user_id, permission):
                    raise PermissionDeniedException(f"User {user_id} lacks {permission} permission")
            return func(self, *args, **kwargs)
        return wrapper
    return decorator

# Service Layer
class TaskService:
    """Service class handling business logic for tasks"""
    
    def __init__(self, task_repository: TaskRepository):
        self.repository = task_repository
        self.factory_registry = TaskFactoryRegistry()
        self.query_processor = TaskQueryProcessor()
        self.notification_center = NotificationCenter()
        
        # Register default factories
        self._setup_factories()
        
        # User permissions (simplified for demo)
        self.user_permissions: Dict[str, set] = {}
    
    def _setup_factories(self):
        """Setup default task factories"""
        self.factory_registry.register_factory("simple", SimpleTaskFactory())
        self.factory_registry.register_factory("urgent", UrgentTaskFactory())
    
    def _check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has required permission"""
        user_perms = self.user_permissions.get(user_id, set())
        return permission in user_perms or "admin" in user_perms
    
    def grant_permission(self, user_id: str, permission: str):
        """Grant permission to user"""
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = set()
        self.user_permissions[user_id].add(permission)
    
    @measure_execution_time
    @require_permission("create_task")
    def create_task(
        self, 
        user_id: str, 
        title: str, 
        description: str = "", 
        priority: Priority = Priority.MEDIUM,
        factory_type: str = "simple",
        **kwargs
    ) -> Task:
        """Create a new task using specified factory"""
        try:
            task = self.factory_registry.create_task(
                factory_type,
                title=title,
                description=description,
                priority=priority,
                **kwargs
            )
            
            # Add audit entry
            task.add_audit_entry("created", user_id)
            
            # Save to repository
            saved_task = self.repository.save(task)
            
            # Notify observers
            self.notification_center.notify_all(
                "task_created",
                f"New task created: {title}",
                {"task_id": saved_task.id, "creator_id": user_id}
            )
            
            return saved_task
            
        except Exception as e:
            print(f"❌ Error creating task: {e}")
            raise
    
    @require_permission("view_task")
    def get_task(self, user_id: str, task_id: str) -> Optional[Task]:
        """Get a task by ID"""
        task = self.repository.get_by_id(task_id)
        
        # Additional business logic: users can only see their own tasks
        # unless they have admin permission
        if task and not self._check_permission(user_id, "admin"):
            if task.assignee_id != user_id:
                raise PermissionDeniedException("Cannot view task assigned to another user")
        
        return task
    
    @require_permission("update_task")
    def update_task(
        self, 
        user_id: str, 
        task_id: str, 
        updates: Dict[str, Any]
    ) -> Optional[Task]:
        """Update a task"""
        task = self.repository.get_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task {task_id} not found")
        
        # Business rule: only assignee or admin can update
        if not self._check_permission(user_id, "admin") and task.assignee_id != user_id:
            raise PermissionDeniedException("Can only update own tasks")
        
        # Apply updates
        old_values = {}
        for key, value in updates.items():
            if hasattr(task, key):
                old_values[key] = getattr(task, key)
                setattr(task, key, value)
        
        task.update_timestamp()
        task.add_audit_entry("updated", user_id, {"changes": updates, "old_values": old_values})
        
        updated_task = self.repository.save(task)
        
        # Notify observers
        self.notification_center.notify_all(
            "task_updated",
            f"Task updated: {task.title}",
            {"task_id": task.id, "updater_id": user_id, "changes": updates}
        )
        
        return updated_task
    
    @require_permission("delete_task")
    def delete_task(self, user_id: str, task_id: str) -> bool:
        """Delete a task"""
        task = self.repository.get_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task {task_id} not found")
        
        # Business rule: can't delete tasks with incomplete subtasks
        if task.subtasks and any(st.status != TaskStatus.COMPLETED for st in task.subtasks):
            raise ValidationException("Cannot delete task with incomplete subtasks")
        
        success = self.repository.delete(task_id)
        
        if success:
            self.notification_center.notify_all(
                "task_deleted",
                f"Task deleted: {task.title}",
                {"task_id": task_id, "deleter_id": user_id}
            )
        
        return success
    
    def assign_task(self, user_id: str, task_id: str, assignee_id: str) -> Optional[Task]:
        """Assign a task to a user"""
        task = self.repository.get_by_id(task_id)
        if not task:
            raise TaskNotFoundException(f"Task {task_id} not found")
        
        old_assignee = task.assignee_id
        task.assignee_id = assignee_id
        task.update_timestamp()
        task.add_audit_entry("assigned", user_id, {
            "old_assignee": old_assignee,
            "new_assignee": assignee_id
        })
        
        updated_task = self.repository.save(task)
        
        # Notify both old and new assignee
        self.notification_center.notify_all(
            "task_assigned",
            f"Task assigned: {task.title}",
            {"task_id": task.id, "assignee_id": assignee_id, "assigner_id": user_id}
        )
        
        return updated_task
    
    @measure_execution_time
    def search_tasks(
        self, 
        user_id: str, 
        criteria: Dict[str, Any],
        sort_by: str = "priority",
        filters: List[str] = None
    ) -> List[Task]:
        """Advanced task search with sorting and filtering"""
        
        # Base search
        tasks = self.repository.find_by_criteria(criteria)
        
        # Filter by user permissions
        if not self._check_permission(user_id, "admin"):
            tasks = [t for t in tasks if t.assignee_id == user_id]
        
        # Apply additional filters using strategy pattern
        self.query_processor.clear_filters()
        
        if filters:
            for filter_type in filters:
                if filter_type == "overdue":
                    self.query_processor.add_filter_strategy(OverdueFilterStrategy())
        
        # Set sorting strategy
        if sort_by == "priority":
            self.query_processor.set_sort_strategy(PrioritySortStrategy())
        elif sort_by == "due_date":
            from ..patterns.strategy import DueDateSortStrategy
            self.query_processor.set_sort_strategy(DueDateSortStrategy())
        elif sort_by == "status":
            from ..patterns.strategy import StatusSortStrategy
            self.query_processor.set_sort_strategy(StatusSortStrategy())
        
        return self.query_processor.process(tasks)
    
    def get_user_dashboard(self, user_id: str) -> Dict[str, Any]:
        """Get dashboard data for a user"""
        user_tasks = self.repository.get_tasks_by_assignee(user_id)
        
        dashboard = {
            "total_tasks": len(user_tasks),
            "pending_tasks": len([t for t in user_tasks if t.status == TaskStatus.PENDING]),
            "in_progress_tasks": len([t for t in user_tasks if t.status == TaskStatus.IN_PROGRESS]),
            "completed_tasks": len([t for t in user_tasks if t.status == TaskStatus.COMPLETED]),
            "overdue_tasks": len([t for t in user_tasks if t.is_overdue()]),
            "high_priority_tasks": len([t for t in user_tasks if t.priority == Priority.HIGH]),
            "tasks_due_today": len([
                t for t in user_tasks 
                if t.due_date and t.due_date.date() == datetime.now().date()
            ]),
            "recent_tasks": sorted(
                user_tasks, 
                key=lambda t: t.updated_at, 
                reverse=True
            )[:5]
        }
        
        return dashboard
    
    def get_project_summary(self, user_id: str, project_id: str) -> Dict[str, Any]:
        """Get summary for a project"""
        if not self._check_permission(user_id, "view_project"):
            raise PermissionDeniedException("Cannot view project summary")
        
        project_tasks = self.repository.get_tasks_by_project(project_id)
        
        if not project_tasks:
            return {"message": "No tasks found for this project"}
        
        total_tasks = len(project_tasks)
        completed_tasks = len([t for t in project_tasks if t.status == TaskStatus.COMPLETED])
        
        return {
            "project_id": project_id,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "completion_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            "overdue_tasks": len([t for t in project_tasks if t.is_overdue()]),
            "tasks_by_status": {
                status.value: len([t for t in project_tasks if t.status == status])
                for status in TaskStatus
            },
            "tasks_by_priority": {
                priority.name: len([t for t in project_tasks if t.priority == priority])
                for priority in Priority
            }
        }
    
    def bulk_update_tasks(
        self, 
        user_id: str, 
        task_ids: List[str], 
        updates: Dict[str, Any]
    ) -> List[Task]:
        """Bulk update multiple tasks"""
        if not self._check_permission(user_id, "bulk_update"):
            raise PermissionDeniedException("Bulk update permission required")
        
        updated_tasks = []
        
        for task_id in task_ids:
            try:
                task = self.update_task(user_id, task_id, updates)
                if task:
                    updated_tasks.append(task)
            except Exception as e:
                print(f"❌ Failed to update task {task_id}: {e}")
        
        self.notification_center.notify_all(
            "bulk_update",
            f"Bulk updated {len(updated_tasks)} tasks",
            {"updated_task_ids": [t.id for t in updated_tasks], "updater_id": user_id}
        )
        
        return updated_tasks
    
    def get_task_analytics(self, user_id: str, date_range: int = 30) -> Dict[str, Any]:
        """Get task analytics for the specified date range"""
        if not self._check_permission(user_id, "view_analytics"):
            raise PermissionDeniedException("Analytics permission required")
        
        cutoff_date = datetime.now() - timedelta(days=date_range)
        all_tasks = self.repository.get_all()
        recent_tasks = [t for t in all_tasks if t.created_at >= cutoff_date]
        
        return {
            "date_range_days": date_range,
            "total_tasks_created": len(recent_tasks),
            "tasks_completed": len([t for t in recent_tasks if t.status == TaskStatus.COMPLETED]),
            "average_completion_time": self._calculate_average_completion_time(recent_tasks),
            "most_active_users": self._get_most_active_users(recent_tasks),
            "priority_distribution": {
                priority.name: len([t for t in recent_tasks if t.priority == priority])
                for priority in Priority
            },
            "completion_rate": len([t for t in recent_tasks if t.status == TaskStatus.COMPLETED]) / len(recent_tasks) * 100 if recent_tasks else 0
        }
    
    def _calculate_average_completion_time(self, tasks: List[Task]) -> Optional[float]:
        """Calculate average time to complete tasks"""
        completed_tasks = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        if not completed_tasks:
            return None
        
        total_time = sum(
            (t.updated_at - t.created_at).total_seconds() 
            for t in completed_tasks
        )
        
        return total_time / len(completed_tasks) / 3600  # Convert to hours
    
    def _get_most_active_users(self, tasks: List[Task], limit: int = 5) -> List[Dict[str, Any]]:
        """Get most active users by task count"""
        user_counts = {}
        
        for task in tasks:
            if task.assignee_id:
                user_counts[task.assignee_id] = user_counts.get(task.assignee_id, 0) + 1
        
        sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [
            {"user_id": user_id, "task_count": count}
            for user_id, count in sorted_users[:limit]
        ]