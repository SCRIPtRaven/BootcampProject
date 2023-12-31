import subprocess
import threading


def start_flask_api():
    subprocess.run(["python", "api.py"], check=True)


def start_local_server():
    subprocess.run(["python", "-m", "http.server"], check=True)


if __name__ == "__main__":
    print("Interactive dashboard can be found on this address: http://127.0.0.1:8000/index.html")
    flask_api_thread = threading.Thread(target=start_flask_api)
    local_server_thread = threading.Thread(target=start_local_server)

    flask_api_thread.start()
    local_server_thread.start()

    flask_api_thread.join()
    local_server_thread.join()
