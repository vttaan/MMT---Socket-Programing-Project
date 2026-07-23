import time
from Node import Node

def main():
    print("=== CLIENT NODE DEMO ===")
    
    client_node = Node(hostID="127.0.0.1", port=9001)

    # ACTIVE TCP DEMO
    print("\n[+] Testing ACTIVE TCP Mode (Connecting to 127.0.0.1:9000)...")
    print("[*] You can log in using FTP commands: USER <username>, then PASS <password>")
    client_node.protocol = "TCP"
    client_node.switchToActiveMode(otherHostID="127.0.0.1", otherPort=9000)

    print("\n[*] TCP Client closed. Wait 5 seconds before switching to UDP test...")
    time.sleep(5)

    # ACTIVE UDP DEMO
    print("\n[+] Testing ACTIVE UDP Mode (Sending packet to 127.0.0.1:9000)...")
    client_node.protocol = "UDP"
    client_node.switchToActiveMode(
        otherHostID="127.0.0.1", 
        otherPort=9000, 
        msg="Ping from Active UDP Client Node!"
    )

    print("\n[=== CLIENT DEMO COMPLETED ===]")

if __name__ == "__main__":
    main()