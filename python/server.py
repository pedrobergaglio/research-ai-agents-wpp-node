# server.py
from colorama import Fore, Back, Style
from flask import Flask
from api.routes import configure_routes
from chatbot.workflows import *
import asyncio
from api.services import workflow
#import werkzeug.serving

app = Flask(__name__)
configure_routes(app)

async def run_workflow():
    await workflow.run(event=InitializeEvent)

if __name__ == '__main__':

    """ if not werkzeug.serving.is_running_from_reloader():
        # Run the asynchronous workflow only if not running from the reloader
        asyncio.run(run_workflow()) """

    app.run(port=5000, debug=True)


""" from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def execute_python_code():
    data = request.json  # This should correctly parse the JSON array

    try:
        print(data)  # Should print out the array
        result = data[-1]  # Accessing the last element in the array
    except Exception as e:
        return jsonify({"error": str(e)})
    
    return jsonify(result)

@app.route('/', methods=['GET'])
def show_html():
    html_content = 
     <html>
    <head>
        <title>Flask App</title>
    </head>
    <body>
        <h1>Welcome to my Flask App!</h1>
        <p>This is the home page.</p>
    </body>
    </html> 

return html_content

if __name__ == '__main__':
    app.run(port=5000, debug=True)
 """