
import requests
from typing import Dict
from typing import List
import os
from dotenv import load_dotenv
from typing import Optional, List
from colorama import Fore, Back, Style
from llama_index.core.workflow import Context, Workflow, Event, StartEvent, StopEvent

load_dotenv()

appsheet_app_id = os.getenv('APPSHEET_APP_ID')
appsheet_api_key = os.getenv('APPSHEET_API_KEY')

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
