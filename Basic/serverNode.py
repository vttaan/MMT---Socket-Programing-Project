import sys
import os
from Node import Node, setUpServer

def main():
    print("==========================================================")
    print("             FTP PASSIVE SERVER NODE DEMO                 ")
    print("==========================================================\n")
    
    # Pre-configure credentials or prompt user
    setUpServer()
    
    server_node = Node(hostID="127.0.0.1", port=9000)
    
    print("\n[+] Starting Server Node in PASSIVE TCP Mode on 127.0.0.1:9000...")
    print("[*] Logs will output lock statuses and thread details below.\n")
    
    try:
        # Run directly in main thread so it blocks and runs indefinitely
        server_node.initPassiveTCP()
    except KeyboardInterrupt:
        print("\n[-] Stopping passive server...")
    finally:
        server_node.stop()
        print("\n[=== SERVER DEMO ENDED ===]")

if __name__ == "__main__":
    main()
