from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Election Monitor")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
      <head><title>Election Monitor</title></head>
      <body>
        <h1>Election Monitor</h1>
        <p>Scaffold is ready.</p>
      </body>
    </html>
    """
