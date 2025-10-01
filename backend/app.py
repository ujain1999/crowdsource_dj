from flask import Flask
from flask_socketio import SocketIO
import os

from sync import register_handlers
from models import db
from routes import routes_bp
from api import api_bp

def create_app():
    app = Flask(__name__, template_folder='../frontend/templates/', static_folder='../frontend/static/')

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(api_bp)
    app.register_blueprint(routes_bp)
    return app

app = create_app()
socketio = SocketIO(app)

register_handlers(socketio)

if __name__ == '__main__':
    socketio.run(app, debug=True)