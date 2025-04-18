# dynamic_server.py
from flask import Flask, Response
import time

app = Flask(__name__)

@app.route("/")
def index():
    # Serve an HTML page with the current timestamp
    now = time.time()
    html = f"<html><body><h1>Dynamic time: {now}</h1></body></html>"
    return Response(html, content_type='text/html')

if __name__ == "__main__":
    # Runs on http://localhost:5000
    app.run(port=5000) 
