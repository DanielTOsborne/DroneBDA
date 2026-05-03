import socket
import os

# Path for the Unix Domain Socket file
SOCKET_PATH = "/tmp/detection_socket"

def main():
    # Remove old socket file if it exists
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    # Create a Unix domain socket
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    try:
        server_socket.bind(SOCKET_PATH)
        server_socket.listen(1)
        print(f"Server listening on {SOCKET_PATH}")

        while True:
            conn, _ = server_socket.accept()
            with conn:
                print("Client connected.")
                while True:
                    data = conn.recv(1024)
                    if not data:
                        break
                    print(f"Received: {data.decode()}")
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        server_socket.close()
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

if __name__ == "__main__":
    main()
