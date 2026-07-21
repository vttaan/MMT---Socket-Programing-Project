import socket
import threading
import time

TCP_PORT = 1234
UDP_PORT = 5000

class Node:
    def __init__(self, hostID = "172.0.0.1", port = TCP_PORT, protocol = "TCP", mode = "Active"):
        self.hostID = hostID
        self.port = port
        self.protocol = protocol
        self.mode = mode
        self.server = None
        self.isRunning = False
        
    def initPassiveTCP(self):
        self.mode = "Passive"
        self.protocol = "TCP"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server.bind((self.hostID, self.port))
        except OSError as e:
            print(f"[-] Failed to bind to {self.hostID}:{self.port} ({e}). Falling back to '127.0.0.1'")
            self.server.bind(('127.0.0.1', self.port))
        self.server.listen(1)
        self.isRunning = True
        print('------------------------------')
        print(f'Current hostID: {self.hostID}')
        print(f'Current port: {self.port}')
        print(f'Current mode: {self.mode}')
        print(f'Current server protocol: {self.protocol}')
        while self.isRunning:
            try:
                self.server.settimeout(1)
                conn, addr = self.server.accept()
                print(f"Connected passive TCP by {addr}")
                
                data = conn.recv(1024)
                print(f"[TCP Received]: {data.decode("utf8")}")
                
                conn.sendall(b"Hello from Passive TCP Server!\r\n")
                conn.close()
            except socket.timeout:
                continue
            except Exception as e:
                break
            
            
            
    def initPassiveUDP(self):
        self.mode = "Passive"
        self.protocol = "UDP"
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.hostID, self.port))
        self.isRunning = True
        print('------------------------------')
        print(f'Current hostID: {self.hostID}')
        print(f'Current port: {self.port}')
        print(f'Current mode: {self.mode}')
        print(f'Current server protocol: {self.protocol}')
        
        while self.isRunning:
            try:
                self.server.settimeout(1)
                data, addr = self.server.recvfrom(1024)
                print(f"Received UDP packet from {addr} : {data.decode("utf8")}")
                
                self.server.sendto(b"Acknowledged by Passive UDP Node", addr)
            except socket.timeout:
                continue
            except Exception as e:
                break
            
            
    def switchToActiveMode(self, otherHostID, otherPort, msg):
        print(f"Switch to Active mode")
        self.mode = "Active"
        if self.protocol == "TCP":
            try:
                print(f"Trying to connect to TCP node {otherHostID}, port {otherPort}")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((otherHostID, otherPort))
                client_socket.sendall((msg.replace('\r\n','') + '\r\n').encode("utf8"))
                
                data = client_socket.recv(1024).decode("utf8")
                
                print(f"Received data: {data}")
                client_socket.close()
            except Exception as e:
                print(f"Connection failed, error: {e}")
        
        elif self.protocol == "UDP":
            try:
                print(f"Trying to send UDP packet to node {otherHostID}, port {otherPort}")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.sendto((msg.replace('\r\n','') + '\r\n').encode("utf8"), (otherHostID, otherPort))
                
                client_socket.settimeout(2)
                data, addr = client_socket.recvfrom(1024)
                
                print(f"Received data from {addr}: {data.decode('utf8')}")
                client_socket.close()
            except socket.timeout:
                print(f"Request timed out waiting for UDP response from {otherHostID}:{otherPort}")
            except Exception as e:
                print(f"Active UDP transmission failed or timed out, error: {e}")
            finally:
                client_socket.close()
    
    
    def stop(self):
        self.running = False
        if self.server:
            try:
                self.server.close()
            except:
                pass
            self.server = None                
#def switchMode(): #switch active/passive
    
if __name__ == "__main__":
    node = Node(hostID ='127.0.0.1', port=9000)

    # 1. Start in PASSIVE TCP Mode using a background thread so the main script can control it
    node.protocol = "TCP"
    passive_thread = threading.Thread(target=node.initPassiveTCP, daemon=True)
    passive_thread.start()

    time.sleep(1) # Give it a moment to spin up

    # 2. Dynamically Switch to ACTIVE TCP Mode and talk to itself (acting as its own client/server test)
    node.switchToActiveMode(otherHostID='127.0.0.1', otherPort=9000, msg="Hello Passive Server, this is an Active TCP request!")

    time.sleep(1)

    # 3. Switch Protocol to UDP and run Passive Mode again
    print("\n--- SWITCHING PROTOCOL TO UDP ---")
    node.protocol = "UDP"
    passive_thread_udp = threading.Thread(target=node.initPassiveUDP, daemon=True)
    passive_thread_udp.start()

    time.sleep(1)

    # 4. Switch to ACTIVE UDP Mode
    node.switchToActiveMode(otherHostID='127.0.0.1', otherPort=9000, msg="Ping from Active UDP Node!")

    time.sleep(1)
    node.stop()
    print("\n[*] Demonstration complete.")