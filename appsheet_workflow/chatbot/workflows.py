from api.utils import send_message_to_user
from prompts import Prompts

import requests
from typing import List, Optional, Literal
from datetime import datetime
from llama_index.core.query_pipeline import QueryPipeline as QP
from llama_index.legacy.service_context import ServiceContext
from llama_index.core import VectorStoreIndex, load_index_from_storage
from sqlalchemy import text
from llama_index.core.schema import TextNode
from llama_index.core.storage import StorageContext
from pathlib import Path
from typing import Dict
from llama_index.core.retrievers import SQLRetriever
from typing import List
from llama_index.core.query_pipeline import FnComponent

from llama_index.core.query_pipeline import (
    QueryPipeline as QP,
    Link,
    InputComponent,
    CustomQueryComponent,
)
from llama_index.core.workflow import Workflow
from pyvis.network import Network
from llama_index.core.retrievers import SQLRetriever
from typing import List
from llama_index.core.query_pipeline import FnComponent

from llama_index.core.prompts.default_prompts import DEFAULT_TEXT_TO_SQL_PROMPT
from llama_index.core.prompts import PromptTemplate
from llama_index.core.query_pipeline import FnComponent
from llama_index.core.llms import ChatResponse
from llama_index.core.llms import ChatMessage, MessageRole
import pandas as pd

import json
import os

# put data into sqlite db
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
)
import re
from llama_index.core.objects import (
    SQLTableNodeMapping,
    ObjectIndex,
    SQLTableSchema,
)
from llama_index.core import SQLDatabase, VectorStoreIndex

from llama_index.core.query_pipeline import (
    QueryPipeline as QP,
    Link,
    InputComponent,
    CustomQueryComponent,
)
from dotenv import load_dotenv

from llama_index.core.workflow import (
    step, 
    Context, 
    Workflow, 
    Event, 
    StartEvent, 
    StopEvent
)
#from llama_index.llms.anthropic import Anthropic
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from enum import Enum
from typing import Optional, List, Callable, Tuple
from llama_index.utils.workflow import draw_all_possible_flows
from colorama import Fore, Back, Style
import asyncio
import nest_asyncio
from pydantic import BaseModel, Field
from llama_index.llms.openai import OpenAI as OpenAIIndex
import openai

load_dotenv()

client = openai.OpenAI()
MODEL = 'gpt-4o-2024-08-06'

# Get the environment variables
host = os.getenv('MYSQL_DB_HOST')
user = os.getenv('MYSQL_DB_USER')
password = os.getenv('MYSQL_DB_PASSWORD')
database = os.getenv('MYSQL_SALES_DB_NAME')

appsheet_app_id = os.getenv('APPSHEET_APP_ID')
appsheet_api_key = os.getenv('APPSHEET_API_KEY')

# Construct the connection string
connection_string = f"mysql+pymysql://{user}:{password}@{host}/{database}"

# Create the engine
engine = create_engine(connection_string)

metadata_obj = MetaData()
sql_database = SQLDatabase(engine)
table_node_mapping = SQLTableNodeMapping(sql_database)
sql_retriever = SQLRetriever(sql_database)

# Global queue to handle incoming user inputs asynchronously
user_input = asyncio.Queue()

def index_all_tables(
    sql_database: SQLDatabase, table_index_dir: str = "./table_indices"
) -> Dict[str, VectorStoreIndex]:
    """Index all tables."""

    table_names = ['CATEGORÍAS CAJA', 'CATEGORÍAS PRODUCTOS', 'CLIENTES', 'COLORES', 'ESTADOS', 'IVA', 'MÉTODOS DE PAGO', 'PERSONAL', 'PRODUCTOS', 'PROVEEDORES']
    # no indexd: CAJA, CHEQUES, PRODUCTOS PEDIDOS, STOCK, CUENTAS CORRIENTES, PEDIDOS, CONTROL DE PRECIOS

    if not Path(table_index_dir).exists():
        os.makedirs(table_index_dir)

    vector_index_dict = {}
    engine = sql_database.engine
    for table_name in table_names: #sql_database.get_usable_table_names():
        print(f"Indexing rows in table: {table_name}")

        if not os.path.exists(f"{table_index_dir}/{table_name}"):
            # get all rows from table
            with engine.connect() as conn:

                columns_query=(
                    f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table_name}'"
                    f"AND TABLE_SCHEMA = '{database}'"
                )

                cursor = conn.execute(text(columns_query))
                result = cursor.fetchall()
                columns = []
                for column in result:
                    columns.append(column[0]) # get the first and only element of the tuple (the name)

                cursor = conn.execute(text(f'SELECT * FROM `{table_name}`'))
                result = cursor.fetchall()
                row_tups = []
                for row in result:
                    row_tups.append(tuple(row))
                    #print(dict(zip(columns, row)))

            # index each row, put into vector store index
            # TODO: CHECK THIS LINE: metadata
            nodes = [
                TextNode(text=str(t), 
                         metadata=dict(zip(columns, 
                                           #check rows types
                                           [str(value) if isinstance(value, datetime) else value 
                                            for value in t]
                                           ))) 
                for t in row_tups]

            # put into vector store index (use OpenAIEmbeddings by default)
            index = VectorStoreIndex(nodes) #service_context=service_context

            # save index
            index.set_index_id("vector_index")
            index.storage_context.persist(f"{table_index_dir}/{table_name}")
        else:
            print('index already exists')
            # rebuild storage context
            storage_context = StorageContext.from_defaults(
                persist_dir=f"{table_index_dir}/{table_name}"
            )
            # load index
            index = load_index_from_storage(
                storage_context, index_id="vector_index") #service_context=service_context
            
        vector_index_dict[table_name] = index

    return vector_index_dict

vector_index_dict = index_all_tables(sql_database)

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

chat_history = []

class Product(BaseModel):
    ID_PRODUCTO: int = Field(..., strict=True, title="Product ID found in the database")
    TIPO: Literal['ESTANDAR', 'INTENSO', 'PIEDRA GRANITO'] = Field(..., title="Type of the color, each color has a corresponding type in the database")
    COLOR: str = Field(..., strict=True, title="Color of the product (TYPE GOES IN THE OTHER FIELD), in the database it is a foreign key")
    CANTIDAD: int = Field(..., strict=True, title="Quantity")

class Order(BaseModel):
    ID_CLIENTE: int = Field(..., strict=True, title="Customer ID found in the database")
    TIPO_DE_ENTREGA: Literal['CLIENTE', 'RETIRA EN FÁBRICA', 'OTRO']
    DIRECCION: Optional[str] = Field(..., strict=True, title="Delivery Address, if deliver_type is CLIENTE or RETIRA EN FABRICA is not required, else it is")
    METODO_DE_PAGO: Literal["EFECTIVO", 'DÓLARES', 'MERCADO PAGO', 'CHEQUE', 'TRANSFERENCIA BANCARIA']
    NOTA: Optional[str] = Field(None, strict=True, title="Note only used if explicitly specified")
    # products: List[Product]

class OrderAndProductList(BaseModel):
    order: Order
    product_list: List[Product]

def appsheet_add(rows: List[Dict] | Dict, table_name: str):
    print(Fore.RED + "[appsheet_add] is being executed" + Style.RESET_ALL)

    if isinstance(rows, dict):
        rows = [rows]

    products_url = f"https://api.appsheet.com/api/v2/apps/{appsheet_app_id}/tables/{table_name}/Action"

    headers = {
        "Content-Type": "application/json",
        "ApplicationAccessKey": appsheet_api_key
    }

    request = {
        "Action": "Add",
        "Properties": {"Locale": "en-US"},
        "Rows": rows
    }

    response = requests.post(products_url, headers=headers, json=request)
    return response

def appsheet_edit(rows: List[Dict] | Dict, table_name: str):
    print(Fore.RED + "[appsheet_edit] is being executed" + Style.RESET_ALL)

    if isinstance(rows, dict):
        rows = [rows]

    products_url = f"https://api.appsheet.com/api/v2/apps/{appsheet_app_id}/tables/{table_name}/Action"

    headers = {
        "Content-Type": "application/json",
        "ApplicationAccessKey": appsheet_api_key
    }

    request = {
        "Action": "Edit",
        "Properties": {"Locale": "en-US"},
        "Rows": rows
    }

    print(request)

    response = requests.post(products_url, headers=headers, json=request)
    return response


class OrderWorkflow(Workflow):

    @step(pass_context=True)
    async def initialize(self, ctx: Context, ev: InitializeEvent) -> ConciergeEvent:

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

        # Print the contents of ctx.data for debugging
        print("ctx.data:", ctx.data)

        ctx.data["llm"] = OpenAIIndex(model="gpt-4o-mini",temperature=0)
        return ConciergeEvent()
  
    @step(pass_context=True)
    async def concierge(self, ctx: Context, ev: ConciergeEvent | StartEvent) -> InitializeEvent | StopEvent | OrchestratorEvent:
        
        response = None
        
        # initialize user if not already done
        if ("user" not in ctx.data):
            return InitializeEvent()
        
        # initialize concierge if not already done
        if ("concierge" not in ctx.data):
            system_prompt = Prompts.concierge
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
        elif (ev.just_completed is not None):
            response = concierge.chat(f"FYI, the user has just completed the task: {ev.just_completed}")
            chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
        elif (ev.need_help):
            print("The previous process needs help with ", ev.request)
            return OrchestratorEvent(request=ev.request)
        elif (ev.request is not None):
            response = concierge.chat(ev.request)
            chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
        
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
        chat_history.append(ChatMessage(role=MessageRole.USER, content=user_msg_str))
        return OrchestratorEvent(request=user_msg_str)
    
    @step(pass_context=True)
    async def orchestrator(self, ctx: Context, ev: OrchestratorEvent) -> ConciergeEvent | OrderCreationEvent | StopEvent:

        #print(f"Orchestrator received request: {ev.request}")

        def emit_order_creation() -> bool:
            """Call this if the user wants create a new order in the system."""      
            print("__emitted: order creation")      
            ctx.session.send_event(OrderCreationEvent(request=ev.request))
            return True

        def emit_concierge() -> bool:
            """Call this if the user wants to do something else or you can't figure out what they want to do."""
            print("__emitted: concierge (non stop)")
            #ctx.session.send_event(ConciergeEvent(request=("This is the request, the orchestator didn't know how to continue: "+ev.request)))
            #ctx.session.send_event(StopEvent())
            self.send_event(ConciergeEvent(request=ev.request))
            return True

        def emit_stop() -> bool:
            """Call this if the user wants to stop or exit the system."""
            print("__emitted: stop")
            ctx.session.send_event(StopEvent())
            return True
        
        # define tool for getting customer data
        def getCustomerData(customer_name: str) -> str:
            """Returns the customer metadata from the customer name given by the user to send that value to the system later"""
            print("__emitted: getCustomerData")
            test_retriever = vector_index_dict["CLIENTES"].as_retriever(similarity_top_k=1)
            nodes =  test_retriever.retrieve(customer_name)
            if nodes[0].metadata is None:
                print("No customer found")
                ctx.session.send_event(StopEvent())
            print(f"For customer {customer_name} found:", 
                  nodes[0].metadata["CLIENTE"], nodes[0].metadata["ID"])
            return str(nodes[0].metadata)

        tools = [
            FunctionTool.from_defaults(fn=emit_order_creation),
            FunctionTool.from_defaults(fn=emit_concierge),
            FunctionTool.from_defaults(fn=emit_stop),
            FunctionTool.from_defaults(fn=getCustomerData)
        ]
        
        system_prompt = Prompts.orchestrator

        """when you call the concierge, also send information to help the concierge answer the user request, as you have more information than him 
                         (your reply will directly sent to the concierge, the user won't read it)."""
        
        agent_worker = FunctionCallingAgentWorker.from_tools(
            tools=tools,
            llm=ctx.data["llm"],
            allow_parallel_tool_calls=False,
            system_prompt=system_prompt,
            verbose=True
        )
        ctx.data["orchestrator"] = agent_worker.as_agent()

        orchestrator = ctx.data["orchestrator"]
        response = str(orchestrator.chat(ev.request))
        print(Fore.MAGENTA + "Orchestrator: " +response + Style.RESET_ALL)
        #chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=("Información del orquestador: "+str(response))))

        if "FAILED" in response:
            print(Fore.RED + response + Style.RESET_ALL)
            return StopEvent()
            #return OrchestratorEvent(request=ev.request)       
        
    @step(pass_context=True)
    async def order_creator(self, ctx: Context, ev: OrderCreationEvent) -> ConciergeEvent | StopEvent:

        if("order_creator_agent" not in ctx.data):

            def send_order():
                """Useful for sending the order to the system via API request, Order will be stored in the session context. 
                Make sure to call the other tools to get the IDs before, and that you have all the data needed."""

                prompt = Prompts.send_order
                
                response = client.beta.chat.completions.parse(
                    model=MODEL,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": str(ctx.data["order"])}
                    ],
                    response_format=OrderAndProductList
                )
                print(json.loads(response.choices[0].message.content))

                products = json.loads(response.choices[0].message.content)["product_list"]
                order = json.loads(response.choices[0].message.content)["order"]

                response = appsheet_add([order], "PEDIDOS")

                if isinstance(response, requests.Response) and response.status_code != 200:
                    print(f"Error inserting order: {response.text}")
                    return f"Error inserting order, stop the system"
                elif response.status_code == 200 and response.json().get('Rows'):

                    print(f"Order inserted successfully, inserting products now", response.json().get('Rows'))

                    order = response.json().get('Rows')[0]

                    for product in products:
                        product["ID_PEDIDO"] = order["ID_KEY"]

                    response = appsheet_add(products, "PRODUCTOS PEDIDOS")

                    if isinstance(response, requests.Response) and response.status_code != 200:
                        print(f"Error inserting order: {response.text}")
                        return f"Error inserting products, stop the system"
                    elif response.status_code == 200 and response.json().get('Rows'):

                        response = appsheet_edit({"ID_KEY": order["ID_KEY"], "GUARDADO": 1}, "PEDIDOS")
                        if isinstance(response, requests.Response) and response.status_code == 200:
                            print(f"Products. Order inserted successfully , Order ID: {order['ID_KEY']}", response.json().get('Rows'))
                            return f"Order and products created successfully, Order ID: {order['ID_KEY']}"
                        
                        else:
                            print(f"Products. Error in the request body or url, check the settings")
                            return f"Error in the request body or url, check the settings, stop the system"
                    else:
                        print(f"Products. Error in the request body or url, check the settings")
                        return f"Error in the request body or url, check the settings, stop the system"
      
                else:
                    print(f"Order. Error in the request body or url, check the settings")
                    return f"Error in the request body or url, check the settings, stop the system"

            def createOrder(customer_name:str, payment_method:str, shipment_type_and_info:str, shipment_adress:Optional[str] = "", nota:Optional[str] = "") -> str:
                """Creates an order in the session, it will be used to store the order data before sending it to the system. 
                Don't use it before having the needed data"""

                ctx.data["order"]["ID_CLIENTE"] = getCustomerID(customer_name)
                ctx.data["order"]["TIPO_DE_ENTREGA"] = shipment_type_and_info
                ctx.data["order"]["DIRECCION"] = shipment_adress
                ctx.data["order"]["METODO_DE_PAGO"] = payment_method
                ctx.data["order"]["NOTA"] = nota
                print("Order created:",  str(ctx.data["order"]))

                return "Order created successfully, make sure to add products before sending it to the system"
            
            def getCustomerID(customer_name: str) -> str:
                """Returns the customer ID from the customer name given by the user to send that value to the system later"""
                test_retriever = vector_index_dict["CLIENTES"].as_retriever(similarity_top_k=1)
                nodes =  test_retriever.retrieve(customer_name)
                print(f"For customer {customer_name} found:", 
                      nodes[0].metadata["CLIENTE"]), nodes[0].metadata["ID"]
                if nodes[0].metadata is None:
                    print("No customer found")
                    ctx.session.send_event(StopEvent())
                return nodes[0].metadata["ID"]
            
            #DNI/CUIT
            def getCustomerCUIT(customer_name: str) -> str:
                """Returns the CUIT of the customer from the customer name given by the user to send that value to the system later"""
                test_retriever = vector_index_dict["CLIENTES"].as_retriever(similarity_top_k=1)
                nodes =  test_retriever.retrieve(customer_name)
                print(f"For customer {customer_name} found:", 
                      nodes[0].metadata["CLIENTE"]), nodes[0].metadata["DNI/CUIT"]
                if nodes[0].metadata is None:
                    print("No customer found")
                    ctx.session.send_event(StopEvent())
                return nodes[0].metadata["DNI/CUIT"]
            
            def addProductSToOrder(products:List[Tuple[str, str, int]]) -> str:
                """Adds a list of products to the order in the session, each tuple in the list has three values:
                product_name is the name of the product (not the color), color description (with its type if the user provided it), and quantity.
                Make sure to add all the products."""
                for product in products:
                    addProductToOrder(product[0], product[1], product[2])
                return "Products added to the order, make sure that all the products where added, and to add other order info. Don't forget to send it to the system when all the data is loaded"
            
            def addProductToOrder(product_name:str, color_description:str, quantity:int):
                """Adds a product to the order in the current session, product_name is the name of the product (not the color), color description (with its type if the user provided it), and quantity.
                Make sure to add all the products using this tool."""
                
                color_tuple = getColorName(color_description)
                product = {
                    "CANTIDAD": quantity, 
                    "ID_PRODUCTO": getProductID(product_name), 
                    "COLOR": color_tuple[0], 
                    "TIPO": color_tuple[1]
                    }
                ctx.data["order"]["products"].append(product)
                print(f"Product added to the order: {product}")

                return "Product added to the order, make sure that all the products are added, and to load other order info too. Don't forget to send it to the system when all the data is loaded"
            
            def getProductID(product_description_name: str) -> str:
                """Returns the product ID from the product name given by the user to send that value to the system later"""
                test_retriever = vector_index_dict["PRODUCTOS"].as_retriever(similarity_top_k=1)
                nodes = test_retriever.retrieve(product_description_name)
                """ result = []

                if nodes[0].get_score() > 0.5:
                    result.append(nodes[0].metadata)
                if nodes[1].get_score() > 0.5:
                    result.append(nodes[1].metadata)
                if nodes[2].get_score() > 0.5:
                    result.append(nodes[2].metadata)
                if len(result) == 0:
                    print("No product found")
                    #ctx.session.send_event(StopEvent())
                    return "No product found, ask the user for more details about the product"
                
                for node in nodes:
                    print(node.metadata["PRODUCTO"], node.get_score()) """

                print(f"For product {product_description_name} found:", nodes[0].metadata["PRODUCTO"], nodes[0].metadata["ID"])
                if nodes[0].metadata is None:
                    print("No product found")
                    ctx.session.send_event(StopEvent())
                return nodes[0].metadata["ID"]
            
            def getColorName(color_description: str) -> Tuple[str, str]:
                """Returns the Color exact name with its corresponding type from the color given by the user to send that value to the system later"""
                test_retriever = vector_index_dict["COLORES"].as_retriever(similarity_top_k=1)
                nodes = test_retriever.retrieve(color_description)
                """ result = []

                if nodes[0].get_score() > 0.5:
                    result.append(nodes[0].metadata)
                if nodes[1].get_score() > 0.5:
                    result.append(nodes[1].metadata)
                if nodes[2].get_score() > 0.5:
                    result.append(nodes[2].metadata)
                if len(result) == 0:
                    print("No product found")
                    #ctx.session.send_event(StopEvent())
                    return "No product found, ask the user for more details about the product"
                
                for node in nodes:
                    print(node.metadata["PRODUCTO"], node.get_score()) """

                print(f"For color {color_description} found:", nodes[0].metadata["COLOR"], nodes[0].metadata["TIPO"])
                if nodes[0].metadata is None:
                    print("No color found")
                    ctx.session.send_event(StopEvent())
                return nodes[0].metadata["COLOR"], nodes[0].metadata["TIPO"]
            
            def stop() -> None:
                """Call this if you notice that something is not working propperly."""
                print("Order creator agent is stopping")
                ctx.session.send_event(StopEvent())
            
            system_prompt = (f"""
                
                Usa el idioma español (argentina).
                You are a helpful assistant that recollects data to create an order correctly in the system by sending an API request.
                This is the ORDER structure:
                            {str(Product)}
                            {str(Order)}
                
                You should use the "createOrder" and "addProductToOrder" for all the products to correctly create the order. 
                    
                Once you have loaded all the data, call the "send_order" tool and it will send the order to the system taken the data you have just loaded.
                if you don't send the order, you'll break the system
                """)

            """Once you have both IDs, use the "send_order" tool.
            If you can see that some data is not provided, ask the user for that particular info.
            Once you have all the data, you can call the tool named "send_order" to send the order to the system.
            If you send the info and it fails, check if you still need more data for the user, or if you can figure out what was wrong in the previous request.
            Once you have created the order succesfully, you can call the tool named "done" to signal that you are done, don't respond before doing this.
            If the user asks to do anything other than creating an order, call the tool "help" to signal some other agent should help.
            IMPORTANT: If you notice that something is not working properly, call the tool "stop" to stop the agent.
            FIRST USE THE TOOL "explain_steps" TO EXPLAIN THE STEPS YOU'LL TAKE TO CREATE THE ORDER, 
                LISTING ALL THE STEPS EACH ONE IN A SHORT SENTENCE. DO NOT CALL ANY OTHER TOOL BEFORE THIS ONE."""
            """If any of those tools return more than one item, ask the user to select which is the right one by showing him the retrieved names
                        once you confirm the data, finish by sending the order
                    If no items are returned, ask the user for more information about the product or the customer"""
            #{json.dumps(Order.model_json_schema(), indent=2)}
                
            ctx.data["create_order_agent"] = ConciergeAgent(
                name="Create Order Agent",
                parent=self,
                tools=[send_order, stop, addProductToOrder, createOrder, getCustomerCUIT, emit_concierge],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=OrderCreationEvent
            )

        return await ctx.data["create_order_agent"].handle_event(ev)

class ConciergeAgent():
    name: str
    parent: Workflow
    tools: List[FunctionTool]
    system_prompt: str
    context: Context
    current_event: Event
    trigger_event: Event
    chat_history: List[ChatMessage]

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
        self.chat_history = []

        # Set up the tools including the ones everybody gets
        def done() -> None:
            """When you complete your task, call this tool."""
            print(f"{self.name} is complete")
            self.context.data["redirecting"] = True
            self.context.session.send_event(ConciergeEvent(just_completed=self.name))

        def need_help() -> None:
            """If you need assistance, call this tool."""
            print(f"{self.name} needs help")
            self.context.data["redirecting"] = True
            self.context.session.send_event(
                ConciergeEvent(request=self.current_event.request, need_help=True)
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

        response = str(self.agent.chat(ev.request, chat_history=chat_history))
        chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))
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

#draw_all_possible_flows(ConciergeWorkflow,filename="concierge_flows.html")

async def main():
    c = OrderWorkflow(timeout=1200, verbose=True)
    result = await c.run()
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
