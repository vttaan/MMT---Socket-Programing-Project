import socket
import threading
import time
import os
from FTPCommandHandle import handle_ftp_command

User, password = '', ''

def runningClient(s):
    try:
        while True:
            msg = input("FTP Client> ")


            command = msg + "\r\n"
            s.sendall(bytes(command, "utf8"))

            if msg.upper() == "QUIT":
                reply = s.recv(1024).decode("utf-8").strip()
                print(f"Server{reply}")
                break
                    
            
            data = s.recv(1024)

            if not data:
                break

            str_data = data.decode("utf8")
            print("Server:", str_data)

            if (msg.upper().startswith("RETR") and str_data.startswith("150")):
                print("System open to UDP port to recieve files,...")

                udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp.bind(('0.0.0.0', UDP_PORT))

                file, addr = udp.recvfrom(4096) # receive file from server

                part = msg.split(' ', 1)
                if (len(part) == 1):
                    filename = "download_file.txt"
                else:
                    filename = part[1] + "_download_file.txt"	

                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(file.decode('utf-8'))

                print(f"[System] download file named '{filename}' successfully from {addr}!")
                udp.close()

                complete_msg = s.recv(1024).decode("utf8").strip()
                print(f"Server: {complete_msg}")

                
    except:
        print("Disconnected")
    finally:
        s.close()

def setUpServer():
    global User, password
    User = input("Input server's username: ")
    password = input("Input password: ")

def runningServer(conn, addr):
    global User, password
    try:
        print(f"Connected by {conn}:{addr}")
        
        # State tracking for this connection
        auth_state = {'userName': None, 'loggedIn': False}
        
        while True:
            
            data = conn.recv(1024)
            if not data:
                break
            
            str_data = data.decode("utf8").strip() # remove "\r\n"
            part  = str_data.split(' ', 1) # split string
            cmd = part[0].upper() # make it into upper case 

            should_quit = handle_ftp_command(cmd, part, conn, addr, auth_state, User, password)
            if should_quit:
                break

    except Exception as e:
        print(f"Disconnected: {e}")
    finally:
        conn.close()
        #.close()

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
        setUpServer()
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
                
                def tcp_client_handler(c, a):
                    try:
                        data = c.recv(1024)
                        print(f"[TCP Received]: {data.decode('utf8')}")
                        c.sendall(b"Hello from Passive TCP Server!\r\n")
                        runningServer(c, a)
                    except Exception as e:
                        print(f"TCP client error {a}: {e}")
                        c.close()

                client_thread = threading.Thread(target=tcp_client_handler, args=(conn, addr), daemon=True)
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                break
            
            
            
    def initPassiveUDP(self):
        self.mode = "Passive"
        self.protocol = "UDP"
        setUpServer()
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
                print(f"Received UDP packet from {addr} : {data.decode('utf8')}")
                
                def udp_packet_handler(packet_data, client_addr):
                    try:
                        self.server.sendto(b"Acknowledged by Passive UDP Node", client_addr)
                        # Further concurrent packet processing logic can go here
                    except Exception as e:
                        print(f"UDP handling error {client_addr}: {e}")

                # Spawn a new thread to process the UDP packet concurrently
                packet_thread = threading.Thread(target=udp_packet_handler, args=(data, addr), daemon=True)
                packet_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                break
    
    def activeTCP(self, otherHostID, otherPort, username=None, password=None):
        self.protocol = "TCP"
        self.switchToActiveMode(otherHostID, otherPort, username=username, password=password)
            
    def switchToActiveMode(self, otherHostID, otherPort, msg="Hello", username=None, password=None):
        print(f"Switching to Active mode ({self.protocol})...")
        self.mode = "Active"
        
        if self.protocol == "TCP":
            try:
                print(f"Trying to connect to TCP node {otherHostID}:{otherPort}...")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((otherHostID, otherPort))

                client_socket.sendall(b"CONNECT_REQUEST\r\n")

                welcome_msg = client_socket.recv(1024).decode("utf-8").strip()
                print(f"[Server]: {welcome_msg}")

                if not username:
                    username = input("Enter Username for Server: ")
                if not password:
                    password = input("Enter Password for Server: ")

                print(f"[Client -> Server]: USER {username}")
                client_socket.sendall(f"USER {username}\r\n".encode("utf-8"))
                user_resp = client_socket.recv(1024).decode("utf-8").strip()
                print(f"[Server]: {user_resp}")

                print(f"[Client -> Server]: PASS {password}")
                client_socket.sendall(f"PASS {password}\r\n".encode("utf-8"))
                pass_resp = client_socket.recv(1024).decode("utf-8").strip()
                print(f"[Server]: {pass_resp}")

                if pass_resp.startswith("230"):
                    print("[+] Login Verification SUCCESSFUL!")
                    runningClient(client_socket)
                else:
                    print("[-] Login Verification FAILED! Closing connection.")
                    client_socket.close()

            except Exception as e:
                print(f"[-] Active TCP connection or login failed: {e}")
        
        elif self.protocol == "UDP":
            try:
                print(f"Trying to send UDP packet to node {otherHostID}:{otherPort}...")
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                client_socket.sendto((msg.replace('\r\n','') + '\r\n').encode("utf-8"), (otherHostID, otherPort))
                
                client_socket.settimeout(2)
                data, addr = client_socket.recvfrom(1024)
                
                print(f"Received data from {addr}: {data.decode('utf-8')}")
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
    
if __name__ == "__main__":
    print('bel')