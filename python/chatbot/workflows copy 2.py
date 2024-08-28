to = '5491131500591'

from typing import Union
from dotenv import load_dotenv
load_dotenv()

import requests

from llama_index.core.workflow import (
    step, 
    Context, 
    Workflow, 
    Event, 
    StartEvent, 
    StopEvent
)
from llama_index.llms.openai import OpenAI
#from llama_index.llms.anthropic import Anthropic
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from enum import Enum
from typing import Optional, List, Callable
from llama_index.utils.workflow import draw_all_possible_flows
from colorama import Fore, Back, Style

global_context: Context = None

class InitializeEvent(Event):
    pass

class ConciergeEvent(Event):
    request: Optional[str]
    just_completed: Optional[str]
    #need_help: Optional[bool]

class OrchestratorEvent(Event):
    pass#request: str


class AuthenticateEvent(Event):
    pass#request: str


class ConciergeWorkflow(Workflow):

    @step(pass_context=True)
    async def header(self, ctx: Context, ev: StartEvent) -> Union[
            ConciergeEvent, AuthenticateEvent, OrchestratorEvent, StopEvent]:

        ctx.data['request'] = ev.get('message')

        # initialize user if not already done
        if ("user" not in ctx.data):
            return InitializeEvent()
        
        if not ev.get('event'):
            # throw error or use hello event
            return StopEvent(result={'next_call': OrchestratorEvent})
        if 'llm' not in ctx.data:
            print(Fore.MAGENTA + 'added llm' + Style.RESET_ALL)
            ctx.data['llm'] = OpenAI(model="gpt-4o-mini", temperature=0.4)
        
        return ev.event()

    @step(pass_context=True)
    async def initialize(self, ctx: Context, ev: InitializeEvent) -> StopEvent:#ConciergeEvent:
        ctx.data["user"] = {
            "username": None,
            "session_token": None,
            "account_id": None,
            "account_balance": None,
        }
        ctx.data["success"] = None
        ctx.data["redirecting"] = None
        ctx.data["overall_request"] = None

        ctx.data["llm"] = OpenAI(model="gpt-4o-mini",temperature=0.4)
        #ctx.data["llm"] = Anthropic(model="claude-3-5-sonnet-20240620",temperature=0.4)
        #ctx.data["llm"] = Anthropic(model="claude-3-opus-20240229",temperature=0.4)

        global global_context
        global_context = ctx

        #return ConciergeEvent(request=None, just_completed=None, need_help=None)
        #return StopEvent(result={'next_call': ConciergeEvent})
        return StopEvent(result={'next_call': OrchestratorEvent})
  
    @step(pass_context=True)
    async def concierge(self, ctx: Context, ev: ConciergeEvent) -> InitializeEvent | StopEvent | OrchestratorEvent:
          
        # initialize concierge if not already done
        if ("concierge" not in ctx.data):
            system_prompt = (f"""
                You are a helpful assistant that is helping a user navigate a financial system.
                Your job is to ask the user questions to figure out what they want to do, and give them the available things they can do.
                That includes           
                * authenticating the user
                You should start by listing the things you can help them do.            
            """)

            agent_worker = FunctionCallingAgentWorker.from_tools(
                tools=[],
                llm=ctx.data["llm"],
                allow_parallel_tool_calls=False,
                system_prompt=system_prompt
            )
            ctx.data["concierge"] = agent_worker.as_agent()        

        concierge = ctx.data["concierge"]
        """ if ctx.data["overall_request"] is not None:
            print("There's an overall request in progress, it's ", ctx.data["overall_request"])
            last_request = ctx.data["overall_request"]
            ctx.data["overall_request"] = None
            return OrchestratorEvent(request=last_request) """
        if (ev.just_completed is not None):
            response = concierge.chat(f"FYI, the user has just completed the task: {ev.just_completed}")
        """ elif (ev.need_help):
            print("The previous process needs help with ", ev.request)
            return OrchestratorEvent(request=ev.request) """
        #else:
            #return StopEvent(result={'next_call': OrchestratorEvent})   
            # first time experience
            #response = concierge.chat("Hello!")
            #ctx.data['awaiting_user_input'] = False
            #await send_message_to_user(str(response), to)
            

        send_message_to_user(str(response), to)

        return StopEvent(result={'next_call': OrchestratorEvent})
        
        #user_msg_str = input("> ").strip()
        #return OrchestratorEvent(request='i would like to authenticate my account.')#(request=user_msg_str)
        """ return StopEvent(result={
            'next_call': OrchestratorEvent,
        }) """
    
    @step(pass_context=True)
    async def orchestrator(self, ctx: Context, ev: OrchestratorEvent) -> ConciergeEvent | AuthenticateEvent | StopEvent:

        request = ctx.data.get('request')

        print(f"Orchestrator received request: {request}")

        def emit_authenticate() -> bool:
            """Call this if the user wants to authenticate"""
            print("__emitted: authenticate")
            ctx.session.send_event(AuthenticateEvent(request=request))
            return True

        def emit_concierge() -> bool:
            """Call this if the user wants to do something else or you can't figure out what they want to do."""
            print("__emitted: concierge")
            ctx.session.send_event(ConciergeEvent(request=request))
            return True

        def emit_stop() -> bool:
            """Call this if the user wants to stop or exit the system."""
            print("__emitted: stop")
            ctx.session.send_event(StopEvent())
            return True

        tools = [
            FunctionTool.from_defaults(fn=emit_authenticate),
            FunctionTool.from_defaults(fn=emit_concierge),
            FunctionTool.from_defaults(fn=emit_stop)
        ]
        
        system_prompt = (f"""
            You are on orchestration agent.
            Your job is to decide which agent to run based on the current state of the user and what they've asked to do. 
            You run an agent by calling the appropriate tool for that agent.
            You do not need to call more than one tool.
            You do not need to figure out dependencies between agents; the agents will handle that themselves.
                            
            If you did not call any tools, return the string "FAILED" without quotes and nothing else.
        """)

        agent_worker = FunctionCallingAgentWorker.from_tools(
            tools=tools,
            llm=ctx.data["llm"],
            allow_parallel_tool_calls=False,
            system_prompt=system_prompt
        )
        ctx.data["orchestrator"] = agent_worker.as_agent()        
        
        orchestrator = ctx.data["orchestrator"]
        response = str(orchestrator.chat(request)) # here we're passing the user's request to the orchestrator so it can decide what to do

        if response == "FAILED":
            print("Orchestration agent failed to return a valid speaker; try again")
            return OrchestratorEvent(request=ev.request)

    @step(pass_context=True)
    async def authenticate(self, ctx: Context, ev: AuthenticateEvent) -> StopEvent:

        if ("authentication_agent" not in ctx.data):
            def store_username(username: str) -> None:
                """Adds the username to the user state."""
                print("Recording username")
                ctx.data["user"]["username"] = username

            def login(password: str) -> None:
                """Given a password, logs in and stores a session token in the user state."""
                print(f"Logging in {ctx.data['user']['username']}")
                # todo: actually check the password
                session_token = "output_of_login_function_goes_here"
                ctx.data["user"]["session_token"] = session_token
            
            def is_authenticated() -> bool:
                """Checks if the user has a session token."""
                print("Checking if authenticated")
                if ctx.data["user"]["session_token"] is not None:
                    return True

            system_prompt = (f"""
                You are a helpful assistant that is authenticating a user.
                Your task is to get a valid session token stored in the user state.
                To do this, the user must supply you with a username and a valid password. You can ask them to supply these.
                If the user supplies a username and password, call the tool "login" to log them in.
                Once you've called the login tool successfully, call the tool named "done" to signal that you are done. Do this before you respond.
                
            """)#If the user asks to do anything other than authenticate, call the tool "need_help" to signal some other agent should help.

            ctx.data["authentication_agent"] = ConciergeAgent(
                name="Authentication Agent",
                parent=self,
                tools=[store_username, login, is_authenticated],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=AuthenticateEvent
            )
        
        print(Fore.BLUE +'await ctx.data["authentication_agent"] ' +'Event received: '+str(ev.request)+ str(ev)+ Style.RESET_ALL)
        returning = await ctx.data["authentication_agent"].handle_event(ev)
        print(Fore.BLUE + 'Event handled: '+str(returning) + Style.RESET_ALL)
        #return returning
        return StopEvent(result={'next_call': ConciergeEvent})
   
class ConciergeAgent():
    name: str
    parent: Workflow
    tools: list[FunctionTool]
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

        # set up the tools including the ones everybody gets
        def done() -> None:
            """When you complete your task, call this tool."""
            print(f"{self.name} is complete")
            self.context.data["redirecting"] = True
            parent.send_event(ConciergeEvent(just_completed=self.name))

        #def need_help() -> None:
            """If the user asks to do something you don't know how to do, call this."""
            """ print(f"{self.name} needs help")
            self.context.data["redirecting"] = True
            parent.send_event(ConciergeEvent(request=self.current_event.request,need_help=True))
 """
        self.tools = [
            FunctionTool.from_defaults(fn=done),
            #FunctionTool.from_defaults(fn=need_help)
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

        trigger_event = self.trigger_event

        print(Fore.RED + str(trigger_event) +Style.RESET_ALL)

        self.current_event = ev

        # Process the event with the agent
        response = self.agent.chat(ev.request)
        await send_message_to_user(str(response), to)

        # Handle redirecting
        if self.context.data.get("redirecting", False):
            print("Redirecting")
            self.context.data["redirecting"] = False
            return None
        
        print(Fore.RED + 'Event handled: ' + str(response) + Style.RESET_ALL)
        return StopEvent(result={'next_call': trigger_event})

        """ # Process next event or end
        if user_msg_str:
            return await self.trigger_event(request=user_msg_str)
        else:
            return await self.trigger_event(request='thank you for the help, we are done.') """

#draw_all_possible_flows(ConciergeWorkflow,filename="concierge_flows.html")

async def send_message_to_user(message: str, to:str):
    
    print(Fore.MAGENTA+'Response sent to user:'+ message+Style.RESET_ALL)

    url = "http://127.0.0.1:3008/v1/messages"
    data = {
        "number": to,
        "message": message
    }
    
    response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
    print(Fore.MAGENTA+'Request Status Code:'+ str(response.status_code)+Style.RESET_ALL)


async def main():
    c = ConciergeWorkflow(timeout=1200, verbose=True)
    result = await c.run()
    #print(result)
    return 'finished'

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
