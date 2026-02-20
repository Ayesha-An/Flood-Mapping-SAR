"""
Simple HTTP server to serve the web map locally.
Run: python serve.py
Then open: http://localhost:8000/index.html
"""
import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving at http://localhost:{PORT}/")
        print(f"Open: http://localhost:{PORT}/index.html")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
