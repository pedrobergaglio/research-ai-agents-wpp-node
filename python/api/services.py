# api/services.py

from colorama import Fore, Style
from chatbot.workflow import ConciergeWorkflow
from chatbot.workflow import *

# In-memory store for user workflow states
user_workflow_states = {}

async def handle_user_message(user_id, message):
    # Retrieve or initialize workflow state for the user
    workflow_state = user_workflow_states.get(user_id, None)
    if workflow_state is None:
        # Create a new workflow instance if it does not exist
        workflow = ConciergeWorkflow(timeout=1200, verbose=True)
        user_workflow_states[user_id] = workflow
        # Initialize the workflow
        initial_event = InitializeEventGGG()
        await workflow.run(initial_event)
    else:
        # Use the existing workflow instance
        workflow = workflow_state
    
    # Handle the incoming message
    orchestrator_event = OrchestratorEvent(request=message)
    response_event = await workflow.run(orchestrator_event)
    
    # Process the result
    if isinstance(response_event, StopEvent):
        # Workflow completed; return the final response
        print(Fore.MAGENTA + 'services ' + 'Finished process' + Style.RESET_ALL)
        # Optionally remove user state if the process is complete
        user_workflow_states.pop(user_id, None)
        return {
            "to": user_id,
            "message": "The process has been completed."
        }
    
    # Generate a response for the user based on the result event
    response_message = ConciergeAgent.handle_event(response_event)
    
    # Update the state in the store
    user_workflow_states[user_id] = workflow

    print(Fore.MAGENTA + str({
        "to": user_id,
        "message": response_message
    }) + Style.RESET_ALL)
    
    return {
        "to": user_id,
        "message": response_message
    }
