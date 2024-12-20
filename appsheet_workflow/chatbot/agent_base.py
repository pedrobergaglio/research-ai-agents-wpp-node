from chatbot.api.utils import send_message_to_user
from chatbot.workflows_base import user_input
from typing import List
from llama_index.core.workflow import Workflow
from typing import List
from llama_index.core.llms import ChatMessage, MessageRole
from dotenv import load_dotenv
from llama_index.core.workflow import (
    Context, 
    Workflow, 
    Event
)
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from colorama import Fore, Back, Style
from chatbot.events import Events
from typing import Optional, List, Callable, Tuple

load_dotenv()

class ConciergeAgent():
    name: str
    parent: Workflow
    tools: List[FunctionTool]
    system_prompt: str
    context: Context
    current_event: Event
    trigger_event: Event

    def __init__(
            self,
            parent: Workflow,
            tools: List[Callable],
            system_prompt: str,
            trigger_event: Event,
            context: Context,
            name: str,
        ):
        self.name = name
        self.parent = parent
        self.context = context
        self.system_prompt = system_prompt
        self.context.data["redirecting"] = False
        self.trigger_event = trigger_event

        # Set up the tools including the ones everybody gets
        def done(explain: str) -> None:
            """When you complete your task, call this tool."""
            print(f"{self.name} is complete:", explain)
            self.context.data["redirecting"] = True
            self.context.session.send_event(Events.ConciergeEvent(just_completed=self.name))

        def need_help(help_on: str) -> None:
            """If you need assistance, call this tool."""
            print(f"{self.name} needs help on:", help_on)
            self.context.data["redirecting"] = True
            self.context.session.send_event(
                Events.ConciergeEvent(request=self.current_event.request, need_help=True)
            )

        self.tools = [
            FunctionTool.from_defaults(fn=done),
            FunctionTool.from_defaults(fn=need_help)
        ]
        for t in tools:
            self.tools.append(FunctionTool.from_defaults(fn=t))

        agent_worker = FunctionCallingAgentWorker.from_tools(
            self.tools,
            llm=self.context.data["llm"],
            allow_parallel_tool_calls=False,
            system_prompt=self.system_prompt
        )
        self.agent = agent_worker.as_agent()        

    async def handle_event(self, ev: Event):
        self.current_event = ev

        response = str(self.agent.chat(ev.request, chat_history=self.context.data["chat_history"]))
        self.context.data["chat_history"].append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
        print(Fore.MAGENTA+"AGENT: " +str(response) + Style.RESET_ALL)

        # send message to user using whatsapp api
        await send_message_to_user(message=str(response), to='5491131500591')

        # if they're sending us elsewhere we're done here
        if self.context.data["redirecting"]:
            self.context.data["redirecting"] = False
            return None

        # otherwise, get some user input and then loop
        #user_msg_str = input("> ").strip()
        user_msg_str = await user_input.get()
        return self.trigger_event(request=user_msg_str)
