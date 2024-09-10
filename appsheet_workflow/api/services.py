# api/services.py

from chatbot.workflows import *
import json
from llama_index.core.workflow import Workflow
#from llama_index.core.workflow.session import WorkflowSession

# Initialize the workflow
workflow = ConciergeWorkflow(timeout=1200, verbose=True)

# In-memory store for user workflow states
user_workflow_states = {}

next_call = OrchestratorEvent

events = [AuthenticateEvent, StopEvent, OrchestratorEvent]

async def handle_user_message(user_id, message):

    global next_call
    
    await workflow.run_step(message=message, event=next_call)   

    # Iterate until done
    while not workflow.is_done():
        result = await workflow.run_step()

    print(Fore.GREEN + 'Result: ' +str(result) + Style.RESET_ALL)

    next_call = result['next_call']

    return 'success'


