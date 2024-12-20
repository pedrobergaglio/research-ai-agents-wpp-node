from llama_index.core.workflow import (
    step, 
    Context, 
    Workflow, 
    Event, 
    StartEvent, 
    StopEvent
)
from typing import Optional, Union

class Events:

    class InitializeEvent(Event):
        pass

    class ConciergeEvent(Event):
        request: Optional[str] = None
        just_completed: Optional[str] = None
        need_help: Optional[bool] = None

    class OrchestratorEvent(Event):
        request: str

    class OrderCreationEvent(Event):
        request: str
    
    class ClientCreationEvent(Event):
        request: str

OrchestratorEvents = Union[
     Events.ConciergeEvent,
     Events.OrderCreationEvent,
     StopEvent,
     Events.ClientCreationEvent
 ]