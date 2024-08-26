# api/services.py

from colorama import Fore, Style
from chatbot.workflows import *

# In-memory store for user workflow states
user_workflow_states = {}

next_call = None
ctx = None #i don't now how this should start

workflow = ConciergeWorkflow(timeout=1200, verbose=True)

async def handle_user_message(user_id, message):

    ctx = await workflow.continue_func(ctx, message) #this function is not implemented, but it receives the new message and the context where the process was left

    return 'user input needed' # this goes to the message manager api when the system needs user input

    """ if next_call is None:    
        result = await workflow.run()
    elif next_call == 'orchestator':
        result = await workflow.orchestator(user_id, message

    if result == 'finished': next_call = None """