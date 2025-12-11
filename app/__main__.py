"""
Entry point for Telcenter Base Service
"""

from app import app, socketio

if __name__ == '__main__':
    import os
    
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"Starting Telcenter Base Service on {host}:{port}")
    print(f"Debug mode: {debug}")
    
    socketio.run(app, host=host, port=port, debug=debug)
