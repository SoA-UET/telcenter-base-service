"""
S07 Partner Management Service

HTTP APIs:
- H24: Core Portal -> S07 (CRUD operations for partners)
- H11: S09 -> S07 (Verify partner connection)
"""

SERVICE_NAME = "S07 Partner Management Service"



from flask import Flask, url_for
from flask_cors import CORS
from flask_socketio import SocketIO

app = Flask(__name__)

app.url_map.strict_slashes = False

socketio = SocketIO(app, cors_allowed_origins="*")

CORS(app)  # Enable CORS for all routes

with app.app_context():
    from .controllers import register_api_controllers
    register_api_controllers(app, socketio)

    @app.get('/')
    def home():
        return f"""
        <html><head><title>{SERVICE_NAME}</title></head><body>
        <h1>Welcome to the {SERVICE_NAME}!</h1>
        <a href={url_for("get_api_versions")}>Here is the API documentation.</a>
        </body></html>
        """

print(app.url_map)
