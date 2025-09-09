class TaskManagementException(Exception):
    """Base exception for task management system"""
    pass

class TaskNotFoundException(TaskManagementException):
    """Raised when a task is not found"""
    pass

class InvalidTaskStateException(TaskManagementException):
    """Raised when attempting invalid state transition"""
    pass

class PermissionDeniedException(TaskManagementException):
    """Raised when user lacks required permissions"""
    pass

class ValidationException(TaskManagementException):
    """Raised when validation fails"""
    pass