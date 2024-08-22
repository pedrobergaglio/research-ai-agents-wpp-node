from flask import Flask, request, jsonify

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

if __name__ == '__main__':
    app.run(port=5000, debug=True)
