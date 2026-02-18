from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

BACKEND_URL = "http://localhost:8000"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    if os.path.exists(path):
        return send_from_directory('.', path)
    return "Not Found", 404

@app.route('/suma', methods=['POST', 'OPTIONS'])
def suma():
    if request.method == 'OPTIONS':
        response = make_response('', 200)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    try:
        # Reenviar la petición al backend
        backend_response = requests.post(
            f"{BACKEND_URL}/suma",
            json=request.json,
            headers={'Content-Type': 'application/json'}
        )
        
        response = make_response(jsonify(backend_response.json()), backend_response.status_code)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        print(f"Error: {e}")
        response = make_response(jsonify({"error": str(e)}), 500)
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
