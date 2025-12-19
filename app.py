from flask import Flask, jsonify, request
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

IDENTITY = {
    "name": "Sentarion",
    "designation": "#1",
    "captain": "Caveman"
}

@app.route('/')
def index():
    return jsonify({"status": "online", "identity": IDENTITY})

@app.route('/health')
def health():
    return jsonify({"status": "online"})

@app.route('/query', methods=['POST'])
def query():
    data = request.json
    message = data.get('message', '')
    
    # Try Claude API
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                system=f"You are {IDENTITY['name']}, serving Captain {IDENTITY['captain']}.",
                messages=[{"role": "user", "content": message}]
            )
            return jsonify({"success": True, "response": response.content[0].text})
        except Exception as e:
            return jsonify({"success": True, "response": f"I am {IDENTITY['name']}. {str(e)}"})
    
    return jsonify({"success": True, "response": f"I am {IDENTITY['name']}, ready to serve Captain {IDENTITY['captain']}."})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
