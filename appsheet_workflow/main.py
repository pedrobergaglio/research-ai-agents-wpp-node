from flask import Flask, request, jsonify
from colorama import Fore, Style
from chatbot.workflows import OrderWorkflow, user_input
import asyncio
import threading
import logging

# Set up basic logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)

# Dedicated event loop for asyncio tasks
loop = asyncio.new_event_loop()

# Suppress detailed debug logs from the openai, httpcore, and other related libraries
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

async def run_workflow():
    try:
        # Create and run the workflow instance
        workflow = OrderWorkflow(timeout=600, verbose=True)
        logging.debug('Workflow instance created.')

        while True:  # Run continuously to handle multiple inputs
            result = await workflow.run()
            logging.info('Workflow result: %s', result)
    except Exception as e:
        logging.error('Error in workflow execution: %s', e)

# Flask endpoint to receive user input
@app.route('/chat', methods=['POST'])
def handle_user_input():
    data = request.json
    input_value = data.get('message', '')

    logging.debug('Received input: %s', input_value)

    if input_value:
        try:
            # Put the input into the queue for the workflow to process using the dedicated event loop
            asyncio.run_coroutine_threadsafe(user_input.put(input_value), loop)
            logging.debug('Input enqueued: %s', input_value)
            return jsonify({'status': 'received', 'input': input_value})
        except Exception as e:
            logging.error('Error enqueueing input: %s', e)
            return jsonify({'status': 'error', 'message': 'Failed to enqueue input'}), 500
    else:
        logging.warning('No input provided.')
        return jsonify({'status': 'error', 'message': 'No input provided'}), 400

if __name__ == "__main__":
    # Run the event loop in a separate thread
    threading.Thread(target=lambda: loop.run_forever(), daemon=True).start()

    # Run the workflow in the event loop
    asyncio.run_coroutine_threadsafe(run_workflow(), loop)

    # Start the Flask server
    app.run(port=5000, debug=True)  # Use debug=True for development environment
