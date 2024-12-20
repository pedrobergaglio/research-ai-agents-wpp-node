from chatbot.api.utils import send_message_to_user
from chatbot.custom_prompts import CustomPrompts
from llama_index.core.workflow import Workflow
from typing import List
from llama_index.core.llms import ChatMessage, MessageRole
from dotenv import load_dotenv
from llama_index.core.workflow import (
    step, 
    Context, 
    Workflow, 
    StartEvent, 
    StopEvent
)
from llama_index.core.agent import FunctionCallingAgentWorker
from colorama import Fore, Back, Style 
from llama_index.llms.openai import OpenAI as OpenAIIndex
import openai
from chatbot.events import Events
import asyncio

load_dotenv()

client = openai.OpenAI()
MODEL = 'gpt-4o-mini'

# Global queue to handle incoming user inputs asynchronously
user_input = asyncio.Queue()

class OrderWorkflow(Workflow):

    @step(pass_context=True)
    async def initialize(self, ctx: Context, ev: Events.InitializeEvent) -> Events.ConciergeEvent:

        ctx.data["user"] = {
            "username": None,
            #"session_token": None,
            #"account_id": None,
            #"account_balance": None,
        }
        ctx.data["success"] = None
        ctx.data["redirecting"] = None
        ctx.data["overall_request"] = None
        ctx.data["order"] = {}
        ctx.data["order"]["products"] = []

        if "chat_history" not in ctx.data:
            ctx.data["chat_history"] = []

        # Print the contents of ctx.data for debugging
        print("ctx.data:", ctx.data)

        ctx.data["llm"] = OpenAIIndex(model="gpt-4o-mini",temperature=0)
        return Events.ConciergeEvent()
  
    @step(pass_context=True)
    async def concierge(self, ctx: Context, ev: Events.ConciergeEvent | StartEvent) -> Events.InitializeEvent | StopEvent | Events.OrchestratorEvent:
        
        response = None
        
        # initialize user if not already done
        if ("user" not in ctx.data): 
            return Events.InitializeEvent()
        
        # initialize concierge if not already done
        if ("concierge" not in ctx.data):
            system_prompt = CustomPrompts.concierge
            agent_worker = FunctionCallingAgentWorker.from_tools(
                tools=[],
                llm=ctx.data["llm"],
                allow_parallel_tool_calls=False,
                system_prompt=system_prompt
            )
            ctx.data["concierge"] = agent_worker.as_agent()  


        concierge = ctx.data["concierge"]
        if ctx.data["overall_request"] is not None:
            print("There's an overall request in progress, it's ", ctx.data["overall_request"])
            last_request = ctx.data["overall_request"]
            ctx.data["overall_request"] = None
            return Events.OrchestratorEvent(request=last_request)
        elif (ev.just_completed is not None):
            response = concierge.chat(f"FYI, the user has just completed the task: {ev.just_completed}")
            ctx.data["chat_history"].append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
        elif (ev.need_help):
            print("The previous process needs help with ", ev.request)
            return Events.OrchestratorEvent(request=ev.request)
        elif (ev.request is not None):
            response = concierge.chat(ev.request)
            ctx.data["chat_history"].append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
        
        if response is not None: 
            print(Fore.MAGENTA + "concierge!!!!" + Style.RESET_ALL)
            print(Fore.MAGENTA + str(response) + Style.RESET_ALL)
  
            # send message to user using whatsapp api
            await send_message_to_user(message=str(response), to='5491131500591')

        #user_msg_str = input("> ").strip()
        user_msg_str = await user_input.get()
        if user_msg_str == "":
            print("User has stopped the system with ''")
            return StopEvent()
        ctx.data["chat_history"].append(ChatMessage(role=MessageRole.USER, content=user_msg_str))
        return Events.OrchestratorEvent(request=user_msg_str)
    

