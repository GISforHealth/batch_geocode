import socket
from app import app

HOST = socket.gethostname()
PORT = 2301

if __name__ == "__main__":
    print( f"*** Now running application on http://{HOST}:{PORT} ***" )
    app.run(debug=True, host=HOST, port=PORT)