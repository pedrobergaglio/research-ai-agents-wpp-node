from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv
import os
from typing import List, Optional, Literal
import json

load_dotenv()

client = OpenAI()
MODEL = 'gpt-4o-2024-08-06'

# define the data structure

class Order(BaseModel):
    customer: str = Field(..., strict=True,title="Customer Complete Name")
    deliver_type: Literal['CLIENTE', 'RETIRA EN FÁBRICA', 'OTRO']
    delivery_address: Optional[str] = Field(...,strict=True, title="Delivery Address, if deliver_type is CLIENTE or RETIRA EN FABRICA is not required, else it is")
    payment_method: Literal["EFECTIVO", 'DÓLARES', 'MERCADO PAGO', 'CHEQUE', 'TRANSFERENCIA BANCARIA']
    nota: Optional[str] = Field(None, strict=True,title="Note only used if explicitly specified")

    class Product(BaseModel):
        product_name: str = Field(..., strict=True,title="Product Name")
        product_type: Literal['ESTANDAR', 'INTENSO', 'PIEDRA GRANITO']
        color: Literal['FRESIA', 'EUCALIPTO', 'ARTICO', 'NEGRO', 'AZUCENA', 'Gris claro']
        quantity: int = Field(..., strict=True,title="Quantity")

    products: List[Product]

def insert_order(request):

    prompt = """
    You will be provided with data about an order to insert in a database.
    Your goal will be to parse the data following the schema provided.
    Here is a description of the parameters:
    - order: general data about the order, and it has a list of products that the user will list
    - product: specifies product_id, product type, color, and quantity
    """

    response = client.beta.chat.completions.parse(
        model=MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": request}
        ],
        response_format=Order
    )

    return json.loads(response.choices[0].message.content)

print(insert_order("hola, quisiera agregar un pedido de 12 'RM X 30 KG LINEA NORT PREMIUM' color eucalipto estandar para Martin García que va a retirar en fábrica (rodriguez 3589) y  pagar en efectivo"))

