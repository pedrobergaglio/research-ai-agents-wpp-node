
from datetime import datetime
from llama_index.core import VectorStoreIndex, load_index_from_storage
from sqlalchemy import text
from llama_index.core.schema import TextNode
from llama_index.core.storage import StorageContext
from pathlib import Path
from typing import Dict
from llama_index.core.retrievers import SQLRetriever
from llama_index.core.retrievers import SQLRetriever
import os
# put data into sqlite db
from sqlalchemy import (
    create_engine,
    MetaData
)
import re
from llama_index.core.objects import (
    SQLTableNodeMapping
)
from llama_index.core import SQLDatabase, VectorStoreIndex
from dotenv import load_dotenv
import asyncio

load_dotenv()
# Get the environment variables
host = os.getenv('MYSQL_DB_HOST')
user = os.getenv('MYSQL_DB_USER')
password = os.getenv('MYSQL_DB_PASSWORD')
database = os.getenv('MYSQL_SALES_DB_NAME')

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