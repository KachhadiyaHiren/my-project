class Notifiable(Protocol):
    """Protocol for objects that can receive notifications"""
    
    def notify(self, message: str, data: Dict[str, Any] = None) -> None:
        """Receive a notification"""
        ...

class Searchable(Protocol):
    """Protocol for searchable entities"""
    
    def matches_criteria(self, criteria: Dict[str, Any]) -> bool:
        """Check if entity matches search criteria"""
        ...

class Serializable(Protocol):
    """Protocol for serializable objects"""
    
    def serialize(self) -> str:
        """Serialize object to string"""
        ...
    
    @classmethod
    def deserialize(cls, data: str) -> 'Serializable':
        """Deserialize string to object"""
        ...