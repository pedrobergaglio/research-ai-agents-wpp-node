to = '5491131500591'
global_context = None

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
    pass

class ConciergeEvent(Event):
    pass
    """  request: Optional[str]
    just_completed: Optional[str]
    need_help: Optional[bool] """

class OrchestratorEvent(Event):
    pass#request: str

class StockLookupEvent(Event):
    pass#request: str

class AuthenticateEvent(Event):
    pass#request: str

class AccountBalanceEvent(Event):
    pass#request: str

class TransferMoneyEvent(Event):
    pass#request: str

class HeaderEvent(Event):
    pass#request: str

class ConciergeWorkflow(Workflow):

    @step(pass_context=True)
    async def header(self, ctx: Context, ev: StartEvent | HeaderEvent) -> Union[
            ConciergeEvent, StockLookupEvent, AuthenticateEvent, AccountBalanceEvent, TransferMoneyEvent, StopEvent]:

        global global_context

        # initialize user if not already done
        if ("user" not in ctx.data):
            if global_context is not None:
                print(Fore.MAGENTA + 'Previous context loaded' + Style.RESET_ALL)
                ctx = global_context

        if 'llm' not in ctx.data:
            print(Fore.MAGENTA + 'Added llm' + Style.RESET_ALL)
            ctx.data['llm'] = OpenAI(model="gpt-4o-mini", temperature=0.4)

        if type(ev) == StartEvent:
            ctx.data['header_event'] = ev.event
            ctx.data['request'] = ev.get('message')
            ctx.data['params'] = ev.get('params')
        
        if ("user" not in ctx.data):
            return InitializeEvent()
        
        """ if not ev.get('event'):
            # throw error or use hello event
            return StopEvent(result={'next_call': OrchestratorEvent})
         """
        global_context = ctx
        return ctx.data['header_event']()

    @step(pass_context=True)
    async def initialize(self, ctx: Context, ev: InitializeEvent) -> HeaderEvent:#ConciergeEvent:

        global global_context

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

        if 'llm' not in ctx.data:
            print(Fore.MAGENTA + 'added llm' + Style.RESET_ALL)
            ctx.data['llm'] = OpenAI(model="gpt-4o-mini", temperature=0.4)

        #return ConciergeEvent(request=None, just_completed=None, need_help=None)
        global_context = ctx
        return HeaderEvent()#StopEvent(result={'next_call': OrchestratorEvent})
  
    @step(pass_context=True)
    async def concierge(self, ctx: Context, ev: ConciergeEvent) -> InitializeEvent | StopEvent | OrchestratorEvent:
        global global_context
        ctx = global_context

        request = ctx.data.get('request')

        # initialize concierge if not already done
        if ("concierge" not in ctx.data):
            system_prompt = (f"""
                You are a helpful assistant that is helping a user navigate a financial system.
                Your job is to ask the user questions to figure out what they want to do, and give them the available things they can do.
                That includes
                * looking up a stock price            
                * authenticating the user
                * checking an account balance
                * transferring money between accounts
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
        if ctx.data["overall_request"] is not None:
            print("There's an overall request in progress, it's ", ctx.data["overall_request"])
            last_request = ctx.data["overall_request"]
            ctx.data["overall_request"] = None
            return OrchestratorEvent(request=last_request)
        elif (ctx.data['params']['just_completed'] is not None):
            response = concierge.chat(f"FYI, the user has just completed the task: {ctx.data['params']['just_completed']}")
        elif (ctx.data['params']['need_help']):
            print("The previous process needs help with ", request)
            global_context = ctx
            return OrchestratorEvent(request=request)
        else:
            # first time experience
            #response = concierge.chat("Hello!")
            #ctx.data['awaiting_user_input'] = False
            #await send_message_to_user(str(response), to)
            global_context = ctx
            return StopEvent(result={'next_call': OrchestratorEvent})

        send_message_to_user(str(response), to)
        global_context = ctx
        return StopEvent(result={'next_call': OrchestratorEvent})
        
        #user_msg_str = input("> ").strip()
        #return OrchestratorEvent(request='i would like to authenticate my account.')#(request=user_msg_str)
        """ return StopEvent(result={
            'next_call': OrchestratorEvent,
        }) """
    
    @step(pass_context=True)
    async def orchestrator(self, ctx: Context, ev: OrchestratorEvent) -> ConciergeEvent | StockLookupEvent | AuthenticateEvent | AccountBalanceEvent | TransferMoneyEvent | StopEvent:
        global global_context
        ctx = global_context
        request = ctx.data.get('request')

        # Ensure LLM is in context
        if 'llm' not in ctx.data:
            return StopEvent(result={'next_call': InitializeEvent})
            raise KeyError("LLM not found in context. Ensure that 'header' step has initialized it properly.")
        

        print(f"Orchestrator received request: {request}")

        def emit_stock_lookup() -> bool:
            """Call this if the user wants to look up a stock price."""      
            print("__emitted: stock lookup")      
            self.send_event(StockLookupEvent(request=request))
            global global_context
            global_context = ctx
            return True

        def emit_authenticate() -> bool:
            """Call this if the user wants to authenticate"""
            print("__emitted: authenticate")
            self.send_event(AuthenticateEvent(request=request))
            return True

        def emit_account_balance() -> bool:
            """Call this if the user wants to check an account balance."""
            print("__emitted: account balance")
            self.send_event(AccountBalanceEvent(request=request))
            global global_context
            global_context = ctx
            return True

        def emit_transfer_money() -> bool:
            """Call this if the user wants to transfer money."""
            print("__emitted: transfer money")
            self.send_event(TransferMoneyEvent(request=request))
            global global_context
            global_context = ctx
            return True

        def emit_concierge() -> bool:
            """Call this if the user wants to do something else or you can't figure out what they want to do."""
            print("__emitted: concierge")
            self.send_event(ConciergeEvent(request=request))
            global global_context
            global_context = ctx
            return True

        def emit_stop() -> bool:
            """Call this if the user wants to stop or exit the system."""
            print("__emitted: stop")
            self.send_event(StopEvent())
            global global_context
            global_context = ctx
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
            global_context = ctx
            return OrchestratorEvent(request=request)

    @step(pass_context=True)
    async def authenticate(self, ctx: Context, ev: AuthenticateEvent) -> StopEvent:
        global global_context
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
                If the user asks to do anything other than authenticate, call the tool "need_help" to signal some other agent should help.
            """)

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
        global_context = ctx; global_context = ctx
        return StopEvent(result={'next_call': ConciergeEvent})
            
    @step(pass_context=True)
    async def stock_lookup(self, ctx: Context, ev: StockLookupEvent) -> ConciergeEvent:
        global global_context
        print(f"Stock lookup received request: {ev.request}")

        if ("stock_lookup_agent" not in ctx.data):
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
            """)

            ctx.data["stock_lookup_agent"] = ConciergeAgent(
                name="Stock Lookup Agent",
                parent=self,
                tools=[lookup_stock_price, search_for_stock_symbol],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=StockLookupEvent
            )
        global_context = ctx; global_context = ctx
        return ctx.data["stock_lookup_agent"].handle_event(ev)
  
    @step(pass_context=True)
    def account_balance(self, ctx: Context, ev: AccountBalanceEvent) -> AuthenticateEvent | ConciergeEvent:
        global global_context
        if("account_balance_agent" not in ctx.data):
            def get_account_id(account_name: str) -> str:
                """Useful for looking up an account ID."""
                print(f"Looking up account ID for {account_name}")
                account_id = "1234567890"
                ctx.data["user"]["account_id"] = account_id
                return f"Account id is {account_id}"
            
            def get_account_balance(account_id: str) -> str:
                """Useful for looking up an account balance."""
                print(f"Looking up account balance for {account_id}")
                ctx.data["user"]["account_balance"] = 1000
                return f"Account {account_id} has a balance of ${ctx.data['user']['account_balance']}"
            
            def is_authenticated() -> bool:
                """Checks if the user is authenticated."""
                print("Account balance agent is checking if authenticated")
                if ctx.data["user"]["session_token"] is not None:
                    return True
                else:
                    return False
                
            def authenticate() -> None:
                """Call this if the user needs to authenticate."""
                print("Account balance agent is authenticating")
                ctx.data["redirecting"] = True
                ctx.data["overall_request"] = "Check account balance"
                self.send_event(AuthenticateEvent(request="Authenticate"))

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

            ctx.data["account_balance_agent"] = ConciergeAgent(
                name="Account Balance Agent",
                parent=self,
                tools=[get_account_id, get_account_balance, is_authenticated, authenticate],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=AccountBalanceEvent
            )

        # TODO: this could programmatically check for authentication and emit an event
        # but then the agent wouldn't say anything helpful about what's going on.
        global_context = ctx; global_context = ctx
        return ctx.data["account_balance_agent"].handle_event(ev)
    
    @step(pass_context=True)
    def transfer_money(self, ctx: Context, ev: TransferMoneyEvent) -> AuthenticateEvent | AccountBalanceEvent | ConciergeEvent:
        global global_context
        if("transfer_money_agent" not in ctx.data):
            def transfer_money(from_account_id: str, to_account_id: str, amount: int) -> None:
                """Useful for transferring money between accounts."""
                print(f"Transferring {amount} from {from_account_id} account {to_account_id}")
                return f"Transferred {amount} to account {to_account_id}"
            
            def balance_sufficient(account_id: str, amount: int) -> bool:
                """Useful for checking if an account has enough money to transfer."""
                # todo: actually check they've selected the right account ID
                print("Checking if balance is sufficient")
                if ctx.data["user"]['account_balance'] >= amount:
                    return True
                
            def has_balance() -> bool:
                """Useful for checking if an account has a balance."""
                print("Checking if account has a balance")
                if ctx.data["user"]["account_balance"] is not None and ctx.data["user"]["account_balance"] > 0:
                    print("It does", ctx.data["user"]["account_balance"])
                    return True
                else:
                    return False
            
            def is_authenticated() -> bool:
                """Checks if the user has a session token."""
                print("Transfer money agent is checking if authenticated")
                if ctx.data["user"]["session_token"] is not None:
                    return True
                else:
                    return False
                
            def authenticate() -> None:
                """Call this if the user needs to authenticate."""
                print("Account balance agent is authenticating")
                ctx.data["redirecting"] = True
                ctx.data["overall_request"] = "Transfer money"
                self.send_event(AuthenticateEvent(request="Authenticate"))

            def check_balance() -> None:
                """Call this if the user needs to check their account balance."""
                print("Transfer money agent is checking balance")
                ctx.data["redirecting"] = True
                ctx.data["overall_request"] = "Transfer money"
                self.send_event(AccountBalanceEvent(request="Check balance"))
            
            system_prompt = (f"""
                You are a helpful assistant that transfers money between accounts.
                The user can only do this if they are authenticated, which you can check with the is_authenticated tool.
                If they aren't authenticated, tell them to authenticate first.
                The user must also have looked up their account balance already, which you can check with the has_balance tool.
                If they haven't already, tell them to look up their account balance first.
                Once you have transferred the money, you can call the tool named "done" to signal that you are done. Do this before you respond.
                If the user asks to do anything other than transfer money, call the tool "done" to signal some other agent should help.
            """)

            ctx.data["transfer_money_agent"] = ConciergeAgent(
                name="Transfer Money Agent",
                parent=self,
                tools=[transfer_money, balance_sufficient, has_balance, is_authenticated, authenticate, check_balance],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=TransferMoneyEvent
            )
        global_context = ctx; global_context = ctx
        return ctx.data["transfer_money_agent"].handle_event(ev)
    

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

        def need_help() -> None:
            """If the user asks to do something you don't know how to do, call this."""
            print(f"{self.name} needs help")
            self.context.data["redirecting"] = True
            parent.send_event(ConciergeEvent(request=self.current_event.request,need_help=True))

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
        global global_context
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
        global_context = self.context
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
