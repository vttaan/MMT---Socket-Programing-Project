import sys
from Node import Node

def main():
    print("==========================================================")
    print("                FTP ACTIVE CLIENT NODE DEMO               ")
    print("==========================================================\n")
    
    server_ip = input("Enter server IP (default: 127.0.0.1): ").strip()
    if not server_ip:
        server_ip = "127.0.0.1"
        
    server_port_str = input("Enter server Port (default: 9000): ").strip()
    if server_port_str:
        try:
            server_port = int(server_port_str)
        except ValueError:
            server_port = 9000
    else:
        server_port = 9000
        
    client_node = Node(hostID="127.0.0.1", port=9001)
    client_node.protocol = "TCP"
    
    print(f"\n[+] Connecting to {server_ip}:{server_port}...")
    print("[*] Supported commands include: USER, PASS, PWD, CWD, CDUP, LIST, RETR, STOR, QUIT")
    
    client_node.switchToActiveMode(otherHostID=server_ip, otherPort=server_port)
    print("\n[=== CLIENT DEMO COMPLETED ===]")

if __name__ == "__main__":
    main()