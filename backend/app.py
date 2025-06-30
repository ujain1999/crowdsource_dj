from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import json
from yt_dlp import YoutubeDL

app = Flask(__name__, template_folder='../frontend/templates/', static_folder='../frontend/static/')

CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

queue = []

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    data = request.json 
    if data['type'] == 'url':
        print("Url")
    elif data['type'] == 'query':
        print('query')
    return data

if __name__ == '__main__':
    app.run(debug=True)