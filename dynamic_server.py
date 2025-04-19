# dynamic_server.py
from flask import Flask, Response
import os
import time

app = Flask(__name__)

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/<path:path>', methods=['GET', 'POST'])
def index(path):
    # Serve an HTML page with the current timestamp for any path
    now = time.time()
    html = f"<html><body><h1>Dynamic time: {now}</h1><p>Requested path: /{path}</p></body></html>"
    return Response(html, content_type='text/html')

if __name__ == "__main__":
    # Allow overriding the port via DYNAMIC_PORT env var (default 5000)
    port = int(os.getenv("DYNAMIC_PORT", "5000"))
    print(f"Starting dynamic server on port {port}")
    app.run(port=port) 
