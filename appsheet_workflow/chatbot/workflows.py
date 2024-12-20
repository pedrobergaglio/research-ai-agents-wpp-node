from chatbot.custom_prompts import CustomPrompts
import requests
from typing import List, Optional, Literal
from typing import List
from typing import List
import json
from dotenv import load_dotenv
from llama_index.core.workflow import (step, Context,StopEvent)
from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from typing import Optional, List, Tuple
from colorama import Fore, Back, Style
import asyncio
from pydantic import BaseModel, Field
import openai
from chatbot.events import Events, OrchestratorEvents
from chatbot.agent_base import ConciergeAgent
from chatbot.workflows_base import OrderWorkflow, user_input
from chatbot.data_indexing import vector_index_dict
from chatbot.utils import appsheet_add, appsheet_edit

load_dotenv()

client = openai.OpenAI()
MODEL = 'gpt-4o-mini'

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

class Client(BaseModel):
    CLIENTE: str = Field(..., strict=True, title="Nombre del cliente")
    CUIT: int = Field(..., strict=True, title="CUIT del cliente")  # Changed to int
    TELEFONO: Optional[int] = Field(None, strict=True, title="Teléfono del cliente")  # Changed to int
    DIRECCION: Optional[str] = Field(None, strict=True, title="Dirección del cliente")
    LIMITE_DE_SALDO: Optional[float] = Field(None, strict=True, title="Límite de saldo del cliente")
    LISTA_DE_PRECIOS: Optional[float] = Field(None, strict=True, title="Descuento en lista de precios")

class OrderWorkflow(OrderWorkflow):

    @step(pass_context=True)
    async def orchestrator(self, ctx: Context, ev: Events.OrchestratorEvent) -> OrchestratorEvents:

        #print(f"Orchestrator received request: {ev.request}")

        def emit_order_creation() -> bool:
            """Call this if the user wants create a new order in the system."""      
            print("__emitted: order creation")      
            ctx.session.send_event(Events.OrderCreationEvent(request=ev.request))
            return True

        def emit_client_creation() -> bool:
            """Call this if the user wants to create a new client in the system."""
            print("__emitted: client creation")
            ctx.session.send_event(Events.ClientCreationEvent(request=ev.request))
            return True

        def emit_concierge() -> bool:
            """Call this if the user wants to do something else or you can't figure out what they want to do."""
            print("__emitted: concierge (non stop)")
            #ctx.session.send_event(ConciergeEvent(request=("This is the request, the orchestator didn't know how to continue: "+ev.request)))
            #ctx.session.send_event(StopEvent())
            ctx.session.send_event(Events.ConciergeEvent(request=ev.request))
            return True

        def emit_stop() -> bool:
            """Call this if the user wants to stop or exit the system."""
            print("__emitted: stop")
            ctx.session.send_event(StopEvent())
            return True
        
        # define tool for getting customer data
        def getCustomerData(customer_name: str) -> str:
            """USE ONLY WHEN THE SPECIFIC REQUEST IS A QUESTION ABOUT AN SPECIFIC CUSTOMER
            ELSE USE THE OTHER TOOLS
            Returns the customer metadata from the customer name given by the user to send that value to the system later"""
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
            FunctionTool.from_defaults(fn=emit_client_creation),  # Added to tools
            FunctionTool.from_defaults(fn=emit_concierge),
            FunctionTool.from_defaults(fn=emit_stop),
            FunctionTool.from_defaults(fn=getCustomerData)
        ]
        
        system_prompt = CustomPrompts.orchestrator

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
        #ctx.data["chat_history"].append(ChatMessage(role=MessageRole.ASSISTANT, content=("Información del orquestador: "+str(response))))

        if "FAILED" in response:
            print(Fore.RED + response + Style.RESET_ALL)
            return StopEvent()
            #return OrchestratorEvent(request=ev.request)       
        
    @step(pass_context=True)
    async def order_creator(self, ctx: Context, ev: Events.OrderCreationEvent) -> Events.ConciergeEvent | StopEvent:

        if("order_creator_agent" not in ctx.data):

            def send_order():
                """Useful for sending the order to the system via API request, Order will be stored in the session context. 
                Make sure to call the other tools to get the IDs before, and that you have all the data needed."""

                prompt = CustomPrompts.send_order
                
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
                tools=[send_order, stop, addProductToOrder, createOrder, getCustomerCUIT],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=Events.OrderCreationEvent
            )

        return await ctx.data["create_order_agent"].handle_event(ev)
    
    @step(pass_context=True)
    async def client_creator(self, ctx: Context, ev: Events.ClientCreationEvent) -> Events.ConciergeEvent | StopEvent:
        if "client_creator_agent" not in ctx.data:

            async def sendCustomer():
                """Formats ctx.data['client'] using an LLM and the Client class, then sends the parsed data via appsheet_add."""

                print("Sending client data")

                prompt = """
                You will be provided with data about a client, and your goal is to parse the data following the schema provided.
                Here is a description of the parameters:
                - client: specifies client name, CUIT, phone number, address, credit limit, and price list discount.
                Tell the user the client ID when it's successfully created.
                If the user asks for something you can't help with, just use the tool "help" to signal the concierge agent should help.
                """

                response = client.beta.chat.completions.parse(
                    model=MODEL,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": str(ctx.data["client"])}
                    ],
                    response_format=Client
                )
                client_data = json.loads(response.choices[0].message.content)
                print("Parsed client data:", client_data)

                response = appsheet_add([client_data], "CLIENTES")
                if isinstance(response, requests.Response) and response.status_code == 200:
                    print("Client added successfully:", response.json().get('Rows'))
                    return "Cliente creado exitosamente."
                else:
                    print("Error inserting client:", response.text)
                    return "Error al crear el cliente, por favor intente nuevamente."

            def createClient(nombre: str, cuit: str, telefono: Optional[str] = None, direccion: Optional[str] = None,
                             limite_de_saldo: Optional[float] = None, descuento_en_lista_de_precios: Optional[float] = None):
                """Creates a client in the session context with provided data."""
                client = {
                    "NOMBRE": nombre,
                    "CUIT": cuit,
                }
                if telefono:
                    client["TELEFONO"] = telefono
                if direccion:
                    client["DIRECCION"] = direccion
                if limite_de_saldo is not None:
                    client["LIMITE_DE_SALDO"] = limite_de_saldo
                if descuento_en_lista_de_precios is not None:
                    client["DESCUENTO_EN_LISTA_DE_PRECIOS"] = descuento_en_lista_de_precios
                ctx.data["client"] = client
                print("Client created:", client)
                return "Cliente creado en el contexto, listo para enviar."

            def stop(stop_reason: str):
                """Stops the client creator agent."""
                print("Client creator agent is stopping, reason:", stop_reason)
                ctx.session.send_event(StopEvent())

            system_prompt = ("""
                Usa el idioma español (Argentina).
                Eres un asistente que ayuda a crear un cliente en el sistema recopilando la información necesaria.
                Necesitas solicitar al usuario los siguientes datos obligatorios: 'Nombre' y 'CUIT'.
                Los datos opcionales son: 'Teléfono', 'Dirección', 'Límite de saldo', 'Descuento en lista de precios'.
                Una vez que tengas la información, utiliza las funciones 'createClient' para almacenarla en el contexto y 'sendCustomer' para enviar al sistema.
                Si notas que falta información, solicita al usuario los datos necesarios.
                Si algo no funciona correctamente, utiliza la función 'stop' para detenerte.
                
                """)

            ctx.data["client_creator_agent"] = ConciergeAgent(
                name="Client Creator Agent",
                parent=self,
                tools=[sendCustomer, stop, createClient],
                context=ctx,
                system_prompt=system_prompt,
                trigger_event=Events.ClientCreationEvent
            )

        return await ctx.data["client_creator_agent"].handle_event(ev)

async def main():
    c = OrderWorkflow(timeout=1200, verbose=True)
    result = await c.run()
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())



