# api/routes.py
from colorama import Fore, Back, Style

from flask import request, jsonify
from .services import *
import logging
import asyncio

def configure_routes(app):
    @app.before_request
    def log_request_info():
        logging.info('Headers: %s', request.headers)
        logging.info('Body: %s', request.get_data())

    @app.after_request
    def log_response_info(response):
        logging.info('Response: %s', response.get_data())
        return response

    
    @app.route('/chat', methods=['POST'])
    async def chat():
        data = request.json
        print(Fore.MAGENTA + 'routes ' + str(data) + Style.RESET_ALL)
        #response = data['event_type']#process_chat_message(data)
        response = await handle_user_message(data['from'], data['message'])
        print(Fore.MAGENTA + 'routes ' + str(response) + str(type(response)) + Style.RESET_ALL)
        return jsonify(response)
    
    @app.route('/', methods=['GET'])
    def home():
        return """
        <html>
        <head>
            <title>Flask App</title>
        </head>
        <body>
            <h1>Welcome to my Flask App!</h1>
            <p>This is the home page.</p>
        </body>
        </html>
        """
