import requests
from colorama import Fore, Back, Style

async def send_message_to_user(message: str, to:str):
    
    #print(Fore.BLUE+'Message sent to user:'+ message+Style.RESET_ALL)

    url = "http://127.0.0.1:3008/v1/messages"
    data = {
        "number": to,
        "message": message
    }
    
    response = requests.post(url, json=data, headers={"Content-Type": "application/json"})
    print(Fore.BLUE+'Whatsapp Response Status Code:'+ str(response.status_code)+Style.RESET_ALL)
