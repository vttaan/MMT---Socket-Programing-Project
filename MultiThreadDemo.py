import threading
import time
import socket
from Node import Node
import Node as NodeModule

def run_server():
    print("[SERVER] Starting Multi-threaded Passive Server Node on 127.0.0.1:9000...")
    # Pre-configure credentials for testing
    NodeModule.User = "admin"
    NodeModule.password = "1234"
    
    server_node = Node(hostID="127.0.0.1", port=9000)
    
    # Custom passive server initialization without interactive input prompt
    server_node.mode = "Passive"
    server_node.protocol = "TCP"
    server_node.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_node.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_node.server.bind(("127.0.0.1", 9000))
    server_node.server.listen(5)
    server_node.isRunning = True

    print("[SERVER] Ready! Multi-threaded connection pool active.\n")

    while server_node.isRunning:
        try:
            server_node.server.settimeout(1)
            conn, addr = server_node.server.accept()
            print(f"[SERVER] [+] Accepted new connection from {addr}")

            def tcp_client_handler(c, a):
                try:
                    data = c.recv(1024)
                    c.sendall(b"Hello from Passive TCP Server!\r\n")
                    NodeModule.runningServer(c, a)
                except Exception as e:
                    print(f"[SERVER] [-] Error handling client {a}: {e}")

            client_thread = threading.Thread(target=tcp_client_handler, args=(conn, addr), daemon=True)
            client_thread.start()
        except socket.timeout:
            continue
        except Exception as e:
            break

def run_client(client_id, delay_sec):
    time.sleep(delay_sec)
    print(f"\n[CLIENT {client_id}] Connecting to Server...")
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 9000))
        
        # Initial handshake trigger
        s.sendall(b"CONNECT\r\n")
        banner = s.recv(1024).decode("utf-8").strip()
        print(f"[CLIENT {client_id}] Received Banner: {banner}")

        # Send USER
        print(f"[CLIENT {client_id}] Sending USER admin")
        s.sendall(b"USER admin\r\n")
        resp_user = s.recv(1024).decode("utf-8").strip()
        print(f"[CLIENT {client_id}] Response: {resp_user}")

        # Simulate concurrent work delay
        time.sleep(2)

        # Send PASS
        print(f"[CLIENT {client_id}] Sending PASS 1234")
        s.sendall(b"PASS 1234\r\n")
        resp_pass = s.recv(1024).decode("utf-8").strip()
        print(f"[CLIENT {client_id}] Response: {resp_pass}")

        # Simulate session work
        time.sleep(1)

        # Send QUIT
        print(f"[CLIENT {client_id}] Sending QUIT")
        s.sendall(b"QUIT\r\n")
        resp_quit = s.recv(1024).decode("utf-8").strip()
        print(f"[CLIENT {client_id}] Response: {resp_quit}")

        s.close()
        print(f"[CLIENT {client_id}] Connection Closed Successfully.\n")
    except Exception as e:
        print(f"[CLIENT {client_id}] Error: {e}")

def main():
    print("==========================================================")
    print("      CONCURRENCY DEMONSTRATION: MULTI-THREADED SERVER    ")
    print("==========================================================\n")

    # 1. Start Server Node in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)

    # 2. Launch Client 1 and Client 2 CONCURRENTLY in separate threads
    c1_thread = threading.Thread(target=run_client, args=(1, 0), daemon=True)
    c2_thread = threading.Thread(target=run_client, args=(2, 0.5), daemon=True)

    print("[*] Spawning Client 1 and Client 2 threads simultaneously...\n")
    c1_thread.start()
    c2_thread.start()

    # Wait for both client sessions to complete
    c1_thread.join()
    c2_thread.join()

    print("\n==========================================================")
    print(" [OK] DEMO COMPLETE: Both clients handled concurrently!   ")
    print("==========================================================")

if __name__ == "__main__":
    main()
