to = '5491131500591'
context = None

from contextlib import contextmanager
from copy import deepcopy
""" 
@contextmanager
def save_session(context):
    # Save the current session
    previous_session = deepcopy(context.session)
    try:
        yield
    finally:
        # Restore the previous session
        context.session = previous_session
 """
#from api.utils import *     

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

class InitializeEvent(Event):
    None

class ConciergeEvent(Event):
    None

class OrchestratorEvent(Event):
    None#request: str

class StockLookupEvent(Event):
    None

class AuthenticateEvent(Event):
    None

class AccountBalanceEvent(Event):
    None

class TransferMoneyEvent(Event):
    None

class HeaderEvent(Event):
    None

class ConciergeWorkflow(Workflow):

    @step(pass_context=True)
    async def header(self, ctx: Context, ev: StartEvent | HeaderEvent) -> Union[OrchestratorEvent, AuthenticateEvent, StopEvent, InitializeEvent, TransferMoneyEvent, AccountBalanceEvent, StockLookupEvent]:

        global context

        # initialize user if StartEvent
        if context is None:
            context = ctx
            context.data['header_event'] = ev.event
            context.data['request'] = ev.get('message')
            params = ev.get('params')
            if params is not None:
                for key, value in params.items():
                    context.data[key] = value
            return InitializeEvent()
        elif type(ev) == StartEvent:
            context.data['header_event'] = ev.event
            context.data['request'] = ev.get('message')
            params = ev.get('params')
            if params is not None:
                for key, value in params.items():
                    context.data[key] = value

        # Return called event
        return context.data['header_event']()

    @step(pass_context=True)
    async def initialize(self, ctx: Context, ev: InitializeEvent) -> HeaderEvent:#ConciergeEvent:

        global context

        context.data["user"] = {
            "username": None,
            "session_token": None,
            "account_id": None,
            "account_balance": None,
        }
        context.data["success"] = None
        context.data["redirecting"] = None
        context.data["overall_request"] = None
        context.data["llm"] = OpenAI(model="gpt-4o-mini",temperature=0.4)

        if 'llm' not in context.data:
            print(Fore.BLUE + 'Added llm' + Style.RESET_ALL)
            context.data['llm'] = OpenAI(model="gpt-4o-mini", temperature=0.4)
        
        #setattr(context, 'previous_session', context.session)

        return HeaderEvent()
 
    @step(pass_context=True)
    async def orchestrator(self, ctx: Context, ev: OrchestratorEvent) -> Union[OrchestratorEvent, AuthenticateEvent, StopEvent, InitializeEvent, TransferMoneyEvent, AccountBalanceEvent, StockLookupEvent]:

        global context
        request = context.data.get('request')
        
        print(f"Orchestrator received request: {request}")

        def emit_authenticate() -> bool:
            """Call this if the user wants to authenticate"""
            print("__emitted: authenticate")
            ctx.session.send_event(AuthenticateEvent(request=request))
            return True
        
        def emit_stock_lookup() -> bool:
            """Call this if the user wants to look up a stock price."""      
            print("__emitted: stock lookup")    
            ctx.session.send_event(StockLookupEvent(request=request))
            return True
        
        def emit_account_balance() -> bool:
            """Call this if the user wants to check an account balance."""
            print("__emitted: account balance")
            ctx.session.send_event(AccountBalanceEvent(request=request))
            return True

        def emit_transfer_money() -> bool:
            """Call this if the user wants to transfer money."""
            print("__emitted: transfer money")
            ctx.session.send_event(TransferMoneyEvent(request=request))
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
            FunctionTool.from_defaults(fn=emit_stock_lookup),
            FunctionTool.from_defaults(fn=emit_authenticate),
            FunctionTool.from_defaults(fn=emit_account_balance),
            FunctionTool.from_defaults(fn=emit_transfer_money),
            FunctionTool.from_defaults(fn=emit_concierge),
            FunctionTool.from_defaults(fn=emit_stop)
        ]
        
        system_prompt = (f"""
            You are an orchestration agent.
            Your job is to decide which agent to run based on the current state of the user and what they've asked to do. 
            You run an agent by calling the appropriate tool for that agent.
            You do not have to call more than one tool.
            You do not have to figure out dependencies between agents; the agents will handle that themselves.
                            
            If you are not being able to call any tools, return the string "FAILED" with the exact error you are finding while calling the function, because the developer is not being able to find the problem.
        """)#nothing else

        agent_worker = FunctionCallingAgentWorker.from_tools(
            tools=tools,
            llm=context.data["llm"],
            allow_parallel_tool_calls=False,
            system_prompt=system_prompt
        )
        context.data["orchestrator"] = agent_worker.as_agent()        
        
        orchestrator = context.data["orchestrator"]
        response = str(orchestrator.chat(request))

        if "FAILED" in response:
            print(Fore.RED + response + Style.RESET_ALL)
            print("Orchestration agent failed to return a valid speaker; try again")
            return OrchestratorEvent(request=request)
        
    @step(pass_context=True)
    async def concierge(self, ctx: Context, ev: ConciergeEvent) -> StopEvent:
        
        global context
        request = context.data.get('request')
        just_completed = context.data.get('just_completed')
        need_help = context.data.get('need_help')
        #overall_request = context.data.get('overall_request')

        print("Concierge received request: ", 
              request, 'with just_completed: ', 
              just_completed, ', need_help: ', 
              need_help, 'and overall_request: ', None)
        
        # initialize concierge if not already done
        if ("concierge" not in context.data):
            system_prompt = (f"""
                You are a helpful assistant that is helping a user navigate a financial system.
                Your job is to ask the user questions to figure out what they want to do, and give them the available things they can do.
                That includes
                * looking up a stock price            
                * authenticating the user
                * checking an account balance
                * transferring money between accounts  

                If you find an issue, please inform it exactly so the developer understands it and fix it, this is a development enviroment.
            """) #[TAKEN OUT]You should start by listing the things you can help them do.  

            agent_worker = FunctionCallingAgentWorker.from_tools(
                tools=[],
                llm=context.data["llm"],
                allow_parallel_tool_calls=False,
                system_prompt=system_prompt
            )
            context.data["concierge"] = agent_worker.as_agent()        

        concierge = context.data["concierge"]

        # If concierge is called it's because
            # 1. The user has just completed a task
            # 2. The user needs help with a task
            # 3. [NOT IMPLEMENTED] It's the first time experience

        if context.data["overall_request"] is not None:
            print("There's an overall request in progress, it's ", context.data["overall_request"])
            last_request = context.data["overall_request"]
            context.data["overall_request"] = None
            context.data["request"] = last_request
            return OrchestratorEvent()
        
        elif (just_completed is not None):
            response = concierge.chat(f"FYI, the user has just completed the task: {just_completed}")
            print(Fore.MAGENTA +"Concierge: "+ str(response) + Style.RESET_ALL)
        elif (need_help):
            print("The previous process needs help with ", request)
            context.data["request"] = "The previous agent couldn't help me with this task: "+request + " can you?"
            # Upgraded:
            return OrchestratorEvent()
        
        return StopEvent(result={'next_call': OrchestratorEvent, 'params': None})
        
    @step(pass_context=True)
    async def authenticate(self, ctx: Context, ev: AuthenticateEvent) -> StopEvent | ConciergeEvent:

        global context

        if ("authentication_agent" not in context.data):
            """ def store_username(username: str) -> None:
                Adds the username to the user state.
                print("Recording username")
                context.data["user"]["username"] = username """

            def login(username: str, password: str) -> None:
                """Given a username and a password, logs in and stores a session token in the user state."""
                context.data["user"]["username"] = username
                print(f"Logging in {context.data['user']['username']}")
                # todo: actually check the password
                session_token = "fs2j_tte0_74cj"
                context.data["user"]["session_token"] = session_token
            
            def is_authenticated() -> bool:
                """Checks if the user has a session token."""
                print("Checking if authenticated")
                if context.data["user"]["session_token"] is not None:
                    return True

            system_prompt = (f"""
                You are a helpful assistant that is authenticating a user.
                Your task is to get a valid session token stored in the user state.
                To do this, the user must supply you with a username and a valid password. If you are aware they want to authenticate, ask them to supply these.
                If the user supplies a username and password, call the tool "login" to log them in.
                Once you've called the login tool successfully, call the tool named "done" to signal that you are done. Do this before you respond.
                If the user asks to do anything other than authenticate, call the tool "need_help" to signal some other agent should help.
                If you find an issue, please inform it exactly so the developer understands it and fix it, this is a development enviroment.
            """)

            context.data["authentication_agent"] = ConciergeAgent(
                name="Authentication Agent",
                parent=self,
                tools=[login, is_authenticated],
                system_prompt=system_prompt,
                trigger_event=AuthenticateEvent
            )

        return context.data["authentication_agent"].handle_event(ev)
  
    @step(pass_context=True)
    def account_balance(self, ctx: Context, ev: AccountBalanceEvent) -> StopEvent | AuthenticateEvent | ConciergeEvent:
        
        global context
        
        if("account_balance_agent" not in context.data):
            def get_account_id(account_name: str) -> str:
                """Useful for looking up an account ID."""
                print(f"Looking up account ID for {account_name}")
                account_id = "1234567890"
                context.data["user"]["account_id"] = account_id
                return f"Account id is {account_id}"
            
            def get_account_balance(account_id: str) -> str:
                """Useful for looking up an account balance."""
                print(f"Looking up account balance for {account_id}")
                context.data["user"]["account_balance"] = 1000
                return f"Account {account_id} has a balance of ${context.data['user']['account_balance']}"
            
            def is_authenticated() -> bool:
                """Checks if the user is authenticated."""
                print("Account balance agent is checking if authenticated")
                if context.data["user"]["session_token"] is not None:
                    return True
                else:
                    return False
                
            def authenticate() -> None:
                """Call this if the user needs to authenticate."""
                print("Account balance agent is authenticating")
                context.data["redirecting"] = True
                context.data["overall_request"] = "Check account balance"
                context.session.send_event(AuthenticateEvent(request="Authenticate"))
                return True

            system_prompt = (f"""
                You are a helpful assistant that is looking up account balances.
                The user may not know the account ID of the account they're interested in,
                so you can help them look it up by the name of the account.
                The user can only do this if they are authenticated, which you can check with the is_authenticated tool.
                If they aren't authenticated, call the "authenticate" tool to trigger the start of the authentication process; tell them you have done this.
                If they're trying to transfer money, they have to check their account balance first, which you can help with.
                Once you have supplied an account balance, you must call the tool named "done" to signal that you are done. Do this before you respond.
                If the user asks to do anything other than look up an account balance, call the tool "need_help" to signal some other agent should help.
            """)

            context.data["account_balance_agent"] = ConciergeAgent(
                name="Account Balance Agent",
                parent=self,
                tools=[get_account_id, get_account_balance, is_authenticated, authenticate],
                system_prompt=system_prompt,
                trigger_event=AccountBalanceEvent
            )

        # TODO: this could programmatically check for authentication and emit an event
        # but then the agent wouldn't say anything helpful about what's going on.

        return context.data["account_balance_agent"].handle_event(ev)
    
    @step(pass_context=True)
    def transfer_money(self, ctx: Context, ev: TransferMoneyEvent) -> StopEvent | AuthenticateEvent | AccountBalanceEvent | ConciergeEvent:

        global context
        
        if("transfer_money_agent" not in context.data):
            def transfer_money(from_account_id: str, to_account_id: str, amount: int) -> None:
                """Useful for transferring money between accounts."""
                print(f"Transferring {amount} from {from_account_id} account {to_account_id}")
                return f"Transferred {amount} to account {to_account_id}"
            
            def balance_sufficient(account_id: str, amount: int) -> bool:
                """Useful for checking if an account has enough money to transfer."""
                global context
                # todo: actually check they've selected the right account ID
                print("Checking if balance is sufficient")
                if context.data["user"]['account_balance'] >= amount:
                    return True
                
            def has_balance() -> bool:
                """Useful for checking if an account has a balance."""
                global context
                print("Checking if account has a balance")
                if context.data["user"]["account_balance"] is not None and context.data["user"]["account_balance"] > 0:
                    print("It does", context.data["user"]["account_balance"])
                    return True
                else:
                    return False
            
            def is_authenticated() -> bool:
                """Checks if the user has a session token."""
                global context
                print("Transfer money agent is checking if authenticated")
                if context.data["user"]["session_token"] is not None:
                    return True
                else:
                    return False
                
            def authenticate() -> None:
                """Call this if the user needs to authenticate."""
                global context
                print("Account balance agent is authenticating")
                context.data["redirecting"] = True
                context.data["overall_request"] = "Transfer money"
                self.send_event(AuthenticateEvent(request="Authenticate"))

            def check_balance() -> None:
                """Call this if the user needs to check their account balance."""
                global context
                print("Transfer money agent is checking balance")
                context.data["redirecting"] = True
                context.data["overall_request"] = "Transfer money"
                self.send_event(AccountBalanceEvent(request="Check balance"))
            
            system_prompt = (f"""
                You are a helpful assistant that transfers money between accounts.
                The user can only do this if they are authenticated, which you can check with the is_authenticated tool.
                If they aren't authenticated, tell them to authenticate first.
                The user must also have looked up their account balance already, which you can check with the has_balance tool.
                If they haven't already, tell them to look up their account balance first.
                Once you have transferred the money, you can call the tool named "done" to signal that you are done. Do this before you respond.
                If the user asks to do anything other than transfer money, call the tool "done" to signal some other agent should help.
                If you find an issue, please inform it exactly so the developer understands it and fix it, this is a development enviroment.
            """)

            context.data["transfer_money_agent"] = ConciergeAgent(
                name="Transfer Money Agent",
                parent=self,
                tools=[transfer_money, balance_sufficient, has_balance, is_authenticated, authenticate, check_balance],
                system_prompt=system_prompt,
                trigger_event=TransferMoneyEvent
            )

        return context.data["transfer_money_agent"].handle_event(ev)

    @step(pass_context=True)
    async def stock_lookup(self, ctx: Context, ev: StockLookupEvent) -> StopEvent | ConciergeEvent:

        global context

        print(f"Stock lookup received request: {ev.request}")

        if ("stock_lookup_agent" not in context.data):
            def lookup_stock_price(stock_symbol: str) -> str:
                """Useful for looking up a stock price."""
                print(f"Looking up stock price for {stock_symbol}")
                return f"Symbol {stock_symbol} is currently trading at $100.00"
            
            def search_for_stock_symbol(str: str) -> str:
                """Useful for searching for a stock symbol given a free-form company name."""
                print("Searching for stock symbol")
                return str.upper()
            
            system_prompt = (f"""
                You are a helpful assistant that is looking up stock prices.
                The user may not know the stock symbol of the company they're interested in,
                so you can help them look it up by the name of the company.
                You can only look up stock symbols given to you by the search_for_stock_symbol tool, don't make them up. Trust the output of the search_for_stock_symbol tool even if it doesn't make sense to you.
                Once you have retrieved a stock price, you *must* call the tool named "done" to signal that you are done. Do this before you respond.
                If the user asks to do anything other than look up a stock symbol or price, call the tool "need_help" to signal some other agent should help.
                If you find an issue, please inform it exactly so the developer understands it and fix it, this is a development enviroment.
            """)

            context.data["stock_lookup_agent"] = ConciergeAgent(
                name="Stock Lookup Agent",
                parent=self,
                tools=[lookup_stock_price, search_for_stock_symbol],
                system_prompt=system_prompt,
                trigger_event=StockLookupEvent
            )

        return context.data["stock_lookup_agent"].handle_event(ev)
  

class ConciergeAgent():
    name: str
    parent: Workflow
    tools: list[FunctionTool]
    system_prompt: str
    current_event: Event
    trigger_event: Event

    global context

    def __init__(
            self,
            parent: Workflow,
            tools: List[Callable], 
            system_prompt: str, 
            trigger_event: Event,
            name: str,
        ):

        
        
        self.name = name
        self.parent = parent
        self.system_prompt = system_prompt
        context.data["redirecting"] = False
        self.trigger_event = trigger_event

        # set up the tools including the ones everybody gets
        def done() -> None:
            global context
            """When you complete your task, call this tool."""
            print(f"{self.name} is complete, calling Concierge")
            context.data["redirecting"] = True
            context.data["just_completed"] = self.name
            context.data['redirecting_to'] = ConciergeEvent
            #parent.send_event(ConciergeEvent())
            #parent.send_event(StopEvent())
            #parent.send_event(ConciergeEvent(just_completed=self.name))

        def need_help() -> None:
            global context
            """If the user asks to do something you don't know how to do, call this."""
            print(f"{self.name} needs help, calling Concierge")
            context.data["redirecting"] = True
            context.data["need_help"] = True
            context.data["request"] = self.current_event.request
            context.data['redirecting_to'] = ConciergeEvent
            #parent.send_event(ConciergeEvent())
            #parent.send_event(StopEvent())
            #parent.send_event(ConciergeEvent(request=self.current_event.request,))

        self.tools = [
            FunctionTool.from_defaults(fn=done),
            FunctionTool.from_defaults(fn=need_help)
        ]
        for t in tools:
            self.tools.append(FunctionTool.from_defaults(fn=t))

        agent_worker = FunctionCallingAgentWorker.from_tools(
            self.tools,
            llm=context.data["llm"],
            allow_parallel_tool_calls=False,
            system_prompt=self.system_prompt
        )
        self.agent = agent_worker.as_agent()        

    def handle_event(self, ev: Event):
        global context
        self.current_event = ev
        trigger_event = self.trigger_event

        # Check if we have a request in the event, if not, use the one from the context
        if ev.get('request') is None:
            request = context.data['request']
        else:
            request = ev.get('request')

        # HERE THE AGENT WILL CHOOSE AND USE A TOOL FROM THE TOOL LIST
        response = str(self.agent.chat(request)) 

        print(Fore.MAGENTA + f'{self.name}: '+str(response) + Style.RESET_ALL)

        # if they're sending us elsewhere we're done here
        if context.data["redirecting"]:
            print(Fore.BLUE + f"Redirecting from {self.name}" + Style.RESET_ALL)
            context.data["redirecting"] = False
            if context.data.get('redirecting_to') is not None:
                return context.data['redirecting_to']()
            else: return trigger_event()
        
        print(Fore.BLUE + f"Trigger event: {trigger_event} is returning from handle_event" + Style.RESET_ALL)

        # otherwise, we will need to get some user input, so we return the StopEvent
        return StopEvent(result={'next_call': trigger_event, 'params': None})





#draw_all_possible_flows(ConciergeWorkflow,filename="concierge_flows.html")

async def main():
    workflow = ConciergeWorkflow(timeout=1200, verbose=True)
    
    result = await workflow.run_step(message="hi! i would like to make a transfer", event=OrchestratorEvent)
    #result = await workflow.run_step(message="hi! i would like to authenticate", event=OrchestratorEvent)

    # Iterate until done
    while not workflow.is_done():
        result = await workflow.run_step()

    print(Fore.GREEN + str(result) +Style.RESET_ALL)

    result = await workflow.run_step(message="sure, my username is pedro and my password is 1234", event=result['next_call'], params=result['params'])

    # Iterate until done
    while not workflow.is_done():
        result = await workflow.run_step()

    print(Fore.GREEN + str(result) +Style.RESET_ALL)
    
    """ result = await workflow.run_step(message="i would like to check the account 7652", event=result['next_call'], params=result['params'])

    # Iterate until done
    while not workflow.is_done():
        result = await workflow.run_step()
    
    print(str(result)) """


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
