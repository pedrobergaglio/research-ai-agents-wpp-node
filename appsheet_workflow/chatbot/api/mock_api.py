
from flask import Flask, request, jsonify
from colorama import Fore, Style

app = Flask(__name__)

@app.route('/v1/messages', methods=['POST'])
def receive_message():
    data = request.get_json()
    number = data.get('number')
    message = data.get('message')
    print(Fore.MAGENTA + f"{message}" + Style.RESET_ALL)
    return jsonify({'status': 'success'}, 200)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3008, debug=True)