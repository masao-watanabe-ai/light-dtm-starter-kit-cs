from abc import ABC, abstractmethod
from app.models.trace import Trace


class BaseTraceStore(ABC):
    @abstractmethod
    def save(self, trace: Trace) -> None: ...

    @abstractmethod
    def list_all(self) -> list[Trace]: ...
