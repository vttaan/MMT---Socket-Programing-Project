import socket
import threading
import time
import os
from FTPCommandHandle import handle_ftp_command

User, password = '', ''

def runningClient(s, HostId):
    try:
        active_udp_socket = None
        while True:
            msg = input("FTP Client> ").strip()
            if not msg:
                continue 
            
            part = msg.split(' ', 1)
            cmd = part[0].upper()
            
            if cmd == "QUIT":
                s.sendall((msg + "\r\n").encode("utf8"))
                data = s.recv(1024)
                if data:
                    print(f"Server: {data.decode('utf8').strip()}")
                break

            # Intercept RETR and LIST to pre-configure a dynamic UDP socket and PORT command
            if cmd in ["RETR", "LIST"]:
                try:
                    active_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    active_udp_socket.bind(('0.0.0.0', 0))
                    client_data_port = active_udp_socket.getsockname()[1]
                    
                    local_ip = s.getsockname()[0]
                    ip_formatted = local_ip.replace('.', ',')
                    p1 = client_data_port // 256
                    p2 = client_data_port % 256
                    
                    port_cmd = f"PORT {ip_formatted},{p1},{p2}\r\n"
                    s.sendall(port_cmd.encode("utf-8"))
                    
                    port_resp = s.recv(1024).decode("utf-8").strip()
                    print(f"Server (PORT): {port_resp}")
                except Exception as e:
                    print(f"[System] Port pre-configuration failed: {e}")
                    if active_udp_socket:
                        active_udp_socket.close()
                        active_udp_socket = None

            # Send original command
            command = msg + "\r\n"
            s.sendall(command.encode("utf8"))
            
            data = s.recv(1024)
            if not data:
                break
                        
            str_data = data.decode("utf8").strip()
            print(f"Server: {str_data}")
            
            # Clean up the prepared UDP socket if server did not accept with status 150
            if cmd in ["RETR", "LIST"] and not str_data.startswith("150") and active_udp_socket:
                active_udp_socket.close()
                active_udp_socket = None

            # 1. RETR (Download) Command Handling
            if cmd == "RETR" and str_data.startswith("150"):
                udp = active_udp_socket
                active_udp_socket = None
                
                if udp is None:
                    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp.bind(('0.0.0.0', UDP_PORT))

                try:
                    if len(part) == 1:
                        filename = "download_file.dat"
                    else:
                        filename = "downloaded_" + part[1]

                    print(f"[System] Downloading to '{filename}'...")
                    with open(filename, 'wb') as f:
                        while True:
                            chunk, address = udp.recvfrom(2048)
                            if chunk == b'__EOF__':
                                break
                            f.write(chunk)
                    print(f"[System] Download complete!")
                except Exception as e:
                    print(f"[System] UDP Error: {e}")
                finally:
                    udp.close()
                    
                    # Receive success notice from TCP control channel
                    complete_msg = s.recv(1024).decode("utf8").strip()
                    print(f"Server: {complete_msg}")

            # 2. STOR (Upload) Command Handling
            elif cmd == "STOR" and str_data.startswith("150"):
                if len(part) > 1:
                    filename = part[1]
                    if os.path.exists(filename) and os.path.isfile(filename):
                        print(f"[System] Uploading '{filename}'...")
                        
                        # Parse dynamic port from server response if present
                        target_port = UDP_PORT
                        if "port" in str_data:
                            try:
                                target_port = int(str_data.split("port")[-1].strip())
                            except ValueError:
                                pass
                                
                        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        try:
                            with open(filename, 'rb') as f:
                                while True:
                                    chunk = f.read(1024)
                                    if not chunk:
                                        break
                                    udp.sendto(chunk, (HostId, target_port))
                                    time.sleep(0.001)
                            
                            udp.sendto(b'__EOF__', (HostId, target_port))
                            print(f"[System] File sent via UDP to port {target_port}!")
                        except Exception as e:
                            print(f"[System] UDP Error: {e}")
                        finally:
                            udp.close()
                    else:
                        print(f"[System] Local error: File '{filename}' not found.")
                
                # Receive final status response from server
                complete_msg = s.recv(1024).decode("utf8").strip()
                print(f"Server: {complete_msg}")

            # 3. LIST (Directory listing) Command Handling
            elif cmd == "LIST" and str_data.startswith("150"):
                udp = active_udp_socket
                active_udp_socket = None
                
                if udp is None:
                    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    udp.bind(('0.0.0.0', UDP_PORT))

                try:
                    print("\n--- DIRECTORY LISTING ---")
                    while True:
                        chunk, _ = udp.recvfrom(2048)
                        if chunk == b'__EOF__':
                            break
                        print(chunk.decode('utf-8'), end="")
                    print("-------------------------")
                except Exception as e:
                    print(f"[SYSTEM] UDP Error: {e}")
                finally:
                    udp.close()
                    
                    # Receive success notice from TCP control channel
                    complete_msg = s.recv(1024).decode('utf-8').strip()
                    print(f"Server: {complete_msg}")
            
    except Exception as e:
        print(f"Disconnected or Error: {e}")
    finally:
        s.close()

def setUpServer():
    global User, password
    u = input("Input server's username (default: admin): ").strip()
    p = input("Input password (default: 1234): ").strip()
    User = u if u else "admin"
    password = p if p else "1234"
    print(f"[SERVER] Configured credentials: Username={User}, Password={password}")

def runningServer(conn, addr):
    global User, password
    tid = threading.get_ident()
    try:
        print(f"[SERVER Thread-{tid}] Starting FTP command loop for client {addr}")
        
        # State tracking for this connection
        auth_state = {'userName': None, 'loggedIn': False, 'cwd': '/'}
        
        while True:
            data = conn.recv(1024)
            if not data:
                break
            
            str_data = data.decode("utf8").strip()
            part = str_data.split(' ', 1)
            cmd = part[0].upper()

            should_quit = handle_ftp_command(cmd, part, conn, addr, auth_state, User, password)
            if should_quit:
                break

    except Exception as e:
        print(f"[SERVER Thread-{tid}] Disconnected client {addr}: {e}")
    finally:
        print(f"[SERVER Thread-{tid}] Closed connection for client {addr}")
        conn.close()

TCP_PORT = 1234
UDP_PORT = 5000

class Node:
    def __init__(self, hostID = "127.0.0.1", port = TCP_PORT, protocol = "TCP", mode = "Active"):
        self.hostID = hostID
        self.port = port
        self.protocol = protocol
        self.mode = mode
        self.server = None
        self.isRunning = False
        
    def initPassiveTCP(self):
        self.mode = "Passive"
        self.protocol = "TCP"
        if not User and not password:
            setUpServer()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server.bind((self.hostID, self.port))
        except OSError as e:
            print(f"[-] Failed to bind to {self.hostID}:{self.port} ({e}). Falling back to '127.0.0.1'")
            self.hostID = '127.0.0.1'
            self.server.bind(('127.0.0.1', self.port))
        self.server.listen(5)
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
                
                def tcp_client_handler(c, a):
                    tid = threading.get_ident()
                    print(f"[SERVER Thread-{tid}] [+] Accepted new connection from {a}")
                    try:
                        data = c.recv(1024)
                        print(f"[SERVER Thread-{tid}] Handshake payload: {data.decode('utf8').strip()}")
                        c.sendall(b"Hello from Passive TCP Server!\r\n")
                        runningServer(c, a)
                    except Exception as e:
                        print(f"[SERVER Thread-{tid}] Error handling client {a}: {e}")
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
        if not User and not password:
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
                    tid = threading.get_ident()
                    try:
                        self.server.sendto(b"Acknowledged by Passive UDP Node", client_addr)
                    except Exception as e:
                        print(f"[SERVER Thread-{tid}] UDP handling error {client_addr}: {e}")

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
                    print("[!] Use USER [username] command to enter server's username")
                    while True:
                        fetch = input().split()
                        if (len(fetch) > 1 and fetch[0] == "USER"):
                            username = fetch[1]
                            break
                    if not username:
                        username = "admin"
                if not password:
                    print("[!] Use PASS [password] command to enter server's password")
                    while True:
                        fetch = input().split()
                        if (len(fetch) > 1 and fetch[0] == "PASS"):
                                password = fetch[1]
                                break
                    if not password:
                        password = "1234"

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
                    runningClient(client_socket, otherHostID)
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
        self.isRunning = False
        if self.server:
            try:
                self.server.close()
            except:
                pass
            self.server = None

if __name__ == "__main__":
    print("Node class loaded.") 