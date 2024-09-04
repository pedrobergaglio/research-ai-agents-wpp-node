from flask import Flask, request, jsonify
from colorama import Fore, Style
from llama_index.core.workflow import (
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.openai import OpenAI
import asyncio
import threading
import logging

# Initialize Flask app
app = Flask(__name__)

# Global queue to handle incoming user inputs asynchronously
user_input = asyncio.Queue()

# Dedicated event loop for asyncio tasks
loop = asyncio.new_event_loop()

# Define the joke events and workflow
class JokeEvent(Event):
    joke: str

class JokeFlow(Workflow):
    llm = OpenAI(model="gpt-4o-mini", temperature=0.4)

    @step()
    async def generate_joke(self, ev: StartEvent) -> JokeEvent:
        print(Fore.MAGENTA + 'Waiting for user input...' + Style.RESET_ALL)

        # Wait for user input from the API request
        user_msg_str = await user_input.get()

        prompt = f"Write your best joke about {user_msg_str}."
        response = await self.llm.acomplete(prompt)

        print(Fore.MAGENTA + str(response) + Style.RESET_ALL)

        return JokeEvent(joke=str(response))

    @step()
    async def critique_joke(self, ev: JokeEvent) -> StopEvent:
        joke = ev.joke

        question = await user_input.get()

        prompt = f"Answer the following question: '{question}' shortly, about the following joke: {joke}"
        response = await self.llm.acomplete(prompt)
        return StopEvent(result=str(response))

async def handle_user_message(user_id, message):
    # Put user input into the queue for the workflow to process
    await user_input.put(message)

    # Initialize and run the joke workflow
    workflow = JokeFlow(timeout=1200, verbose=True)
    result = await workflow.run()
    
    print(Fore.GREEN + 'Workflow result: ' + str(result) + Style.RESET_ALL)
    return result

# Configure routes for the Flask app
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
        print(Fore.BLUE + 'Received data: ' + str(data) + Style.RESET_ALL)

        # Call handle_user_message with the incoming data
        response = await handle_user_message(data['from'], data['message'])
        print(Fore.BLUE + 'Response: ' + str(response) + str(type(response)) + Style.RESET_ALL)
        return jsonify({'response': str(response)})

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

# Apply the route configurations to the app
configure_routes(app)

if __name__ == "__main__":
    # Run the event loop in a separate thread
    threading.Thread(target=lambda: loop.run_forever()).start()

    # Start the Flask server
    app.run(port=5000, debug=True)
