from flask import Flask, send_file
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    try:
        return send_file('index.html')
    except:
        return "<h1>🎰 Minions Casino</h1><p>✅ Сервер работает! Но файл index.html не найден</p>"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
