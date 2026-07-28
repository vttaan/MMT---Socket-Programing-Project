import threading
import time
from Node import Node

def main():
    print("=== SERVER NODE DEMO ===")
    
    # Initialize node listening on localhost:9000
    server_node = Node(hostID="127.0.0.1", port=9000)

    # PASSIVE TCP DEMO
    print("\n[+] Starting Server Node in PASSIVE TCP Mode...")
    tcp_thread = threading.Thread(target=server_node.initPassiveTCP, daemon=True)
    tcp_thread.start()

    print("\n[*] Passive TCP Server is listening on 127.0.0.1:9000.")
    print("\n[*] Run clientNode.py to test TCP connection.")
    
    try:
        time.sleep(250)
    except KeyboardInterrupt:
        print("\n[-] Stopping TCP server...")

    server_node.stop()

    # PASSIVE UDP DEMO
    ''' print("\n[+] Starting Server Node in PASSIVE UDP Mode...")
    server_node = Node(hostID="127.0.0.1", port=9000)
    udp_thread = threading.Thread(target=server_node.initPassiveUDP, daemon=True)
    udp_thread.start()

    print("[*] Passive UDP Server is listening on 127.0.0.1:9000.")
    print("[*] Run clientNode.py to test UDP packet transmission.")

    try:
        time.sleep(20)
    except KeyboardInterrupt:
        print("\n[-] Stopping UDP server...")

    server_node.stop()'''
    print("\n[=== SERVER DEMO ENDED ===]")

if __name__ == "__main__":
    main()
