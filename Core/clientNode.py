import socket
import os
import time
import struct
import select
import hashlib
from rdt import rdt_send_file, rdt_receive_file


UDP_PORT = 5000

def compute_local_hash(filepath):
    # Read file in chunks and compute SHA-256 hash 
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        return None
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"[System] ERROR when computing hash: {e}")
        return None

def send_file_sliding_window(udp_socket, file_path, target_addr, window_size=5, timeout=1.0): 
    packets = []
    seq_num = 0
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(1024)
            if not chunk:
                break
            header = struct.pack("!I", seq_num)
            packets.append(header + chunk)
            seq_num += 1
    total_packets = len(packets)
    base = 0
    next_seq_num = 0

    # Set socket to non-blocking for select-based timeout checks
    udp_socket.setblocking(False)
    print(
        f"[Client] Starting Sliding Window Upload ({total_packets} packets, Window Size={window_size})"
    )

    while base < total_packets:
        # A. Fill the window: Send available packets up to (base + window_size)
        while next_seq_num < base + window_size and next_seq_num < total_packets:
            udp_socket.sendto(packets[next_seq_num], target_addr)
            print(f"  [-> Sent] Packet Seq={next_seq_num}")
            next_seq_num += 1
        # B. Wait for ACKs using select() with a timeout
        readable, _, _ = select.select([udp_socket], [], [], timeout)
        if readable:
            try:
                ack_data, _ = udp_socket.recvfrom(1024)
                if len(ack_data) >= 4:
                    ack_num = struct.unpack('!I', ack_data[:4])[0]
                    print(f"  [<- ACK Received] ACK={ack_num}")
                    # Cumulative ACK handling: Slide window base forward
                    if ack_num >= base:
                        base = ack_num + 1
            except Exception as e:
                print(f"  [!] ACK read error: {e}")
        else:
            # C. Timeout: Retransmit all unACKed packets in current window (Go-Back-N)
            print(
                f"  [!] Timeout! Retransmitting window from Seq={base} to {next_seq_num - 1}"
            )
            next_seq_num = base  # Reset next_seq_num back to base to resend
    # 2. Send EOF marker (Special Header Seq = 0xFFFFFFFF)
    eof_header = struct.pack('!I', 0xFFFFFFFF)
    udp_socket.sendto(eof_header + b'__EOF__', target_addr)
    print('[Client] Upload finished successfully with Sliding Window!')
        
class ClientNode:
    def __init__(self, hostID="127.0.0.1", port=1234):
        self.hostID = hostID
        self.port = port
        self.protocol = "TCP" 
        self.data_mode = "ACTIVE" 
        self.control_socket = None
        self.username = None
        self.password = None

    def connect(self):
        try:
            print(f"[*] Connecting to Server {self.hostID}:{self.port}...")
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.hostID, self.port))
            
            self.control_socket.sendall(b"CONNECT_REQUEST\r\n")

            welcome_msg = self.control_socket.recv(1024).decode("utf-8").strip()
            print(f"[Server]: {welcome_msg}")
            
            if self._login():
                self._interactive_session()
            else:
                print("[-] Login failed. Disconnecting.")
                
        except Exception as e:
            print(f"[-] Connection failed: {e}")
        finally:
            if self.control_socket:
                self.control_socket.close()

    def _login(self):
        print("[!] Use USER [username] command to enter server's username")
        while True:
            fetch = input("FTP Client> ").split()
            if (len(fetch) > 1 and fetch[0].upper() == "USER"):
                self.username = fetch[1]
                break
            print("Please enter USER [username]")
            
        print("[!] Use PASS [password] command to enter server's password")
        while True:
            fetch = input("FTP Client> ").split()
            if (len(fetch) > 1 and fetch[0].upper() == "PASS"):
                self.password = fetch[1]
                break
            print("Please enter PASS [password]")
            
        print(f"[Client -> Server]: USER {self.username}")
        self.control_socket.sendall(f"USER {self.username}\r\n".encode("utf-8"))
        user_resp = self.control_socket.recv(1024).decode("utf-8").strip()
        print(f"[Server]: {user_resp}")

        print(f"[Client -> Server]: PASS {self.password}")
        self.control_socket.sendall(f"PASS {self.password}\r\n".encode("utf-8"))
        pass_resp = self.control_socket.recv(1024).decode("utf-8").strip()
        print(f"[Server]: {pass_resp}")

        if pass_resp.startswith("230"):
            print("[+] Login Verification SUCCESSFUL!")
            return True
        return False

    def _interactive_session(self):
        s = self.control_socket
        while True:
            msg = input(f"FTP Client ({self.data_mode})> ").strip()
            if not msg:
                continue
                
            # Local client toggle for data mode
            if msg.upper() == "PASV_MODE":
                self.data_mode = "PASSIVE"
                print("[*] Data connection mode set to PASSIVE")
                continue
            elif msg.upper() == "ACTV_MODE":
                self.data_mode = "ACTIVE"
                print("[*] Data connection mode set to ACTIVE")
                continue

            part = msg.split(' ', 1)
            cmd = part[0].upper()

            if cmd == "QUIT":
                s.sendall((msg + "\r\n").encode("utf8"))
                data = s.recv(1024)
                if data:
                    print(f"Server: {data.decode('utf8').strip()}")
                break

            active_udp_socket = None
            server_pasv_ip = None
            server_pasv_port = None

            # Setup Data Connection BEFORE sending data transfer commands
            if cmd in ["RETR", "LIST", "STOR"]:
                try:
                    if self.data_mode == "ACTIVE":
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
                        if not port_resp.startswith("200"):
                            print("[System] PORT command rejected by server.")
                            active_udp_socket.close()
                            active_udp_socket = None
                            continue

                    elif self.data_mode == "PASSIVE":
                        s.sendall(b"PASV\r\n")
                        pasv_resp = s.recv(1024).decode("utf-8").strip()
                        print(f"Server (PASV): {pasv_resp}")
                        
                        if pasv_resp.startswith("227"):
                            start = pasv_resp.find('(')
                            end = pasv_resp.find(')')
                            if start != -1 and end != -1:
                                params = pasv_resp[start+1:end].split(',')
                                server_pasv_ip = ".".join(params[:4])
                                server_pasv_port = (int(params[4]) << 8) + int(params[5])
                                
                                active_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                            else:
                                print("[System] Failed to parse PASV response.")
                                continue
                        else:
                            print("[System] PASV command rejected.")
                            continue

                except Exception as e:
                    print(f"[System] Data connection setup failed: {e}")
                    if active_udp_socket:
                        active_udp_socket.close()
                    continue

            # Send original command
            command = msg + "\r\n"
            s.sendall(command.encode("utf8"))
            
            data = s.recv(1024)
            if not data:
                break
                        
            str_data = data.decode("utf8").strip()
            print(f"Server: {str_data}")
            
            # Clean up if server rejects transfer
            if cmd in ["RETR", "LIST", "STOR"] and not str_data.startswith("150"):
                if active_udp_socket:
                    active_udp_socket.close()
                continue

            # --- Data Transfer Handlers ---

            if cmd == "RETR" and str_data.startswith("150"):
                try:
                    filename = "download_file.dat" if len(part) == 1 else "downloaded_" + part[1]
                    
                    if active_udp_socket is None:
                        active_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        active_udp_socket.bind(('0.0.0.0', UDP_PORT))

                    print(f"[System] Opening RDT UDP port to receive '{filename}'...")
                    rdt_receive_file(active_udp_socket, filename)
                except Exception as e:
                    print(f"[System] UDP Error: {e}")
                finally:
                    if active_udp_socket:
                        active_udp_socket.close()
                    complete_msg = s.recv(1024).decode("utf8").strip()
                    print(f"Server: {complete_msg}")

                    # Verify file integrity after download
                    if "226" in complete_msg:
                        local_hash = compute_local_hash(filename)
                        if local_hash:
                            print("[System] Verifying data integrity (Download)...")
                            # Send HASH command to server for verification
                            s.sendall(f"HASH {part[1]}\r\n".encode("utf8"))
                            hash_resp = s.recv(1024).decode("utf8").strip()
                            
                            if hash_resp.startswith("200"):
                                server_hash = hash_resp.split(" ")[1]
                                if local_hash == server_hash:
                                    print(f"[+] INTEGRITY VERIFIED: Match SHA-256!\n    Hash: {local_hash}")
                                else:
                                    print(f"[-] INTEGRITY FAILED: Data Corrupted!\n    Client: {local_hash}\n    Server: {server_hash}")

            elif cmd == "STOR" and str_data.startswith("150"):
                if len(part) > 1:
                    filename = part[1]
                    if os.path.exists(filename) and os.path.isfile(filename):
                        print(f"[System] Opening RDT UDP socket to send '{filename}'...")

                        # Compute local hash for integrity verification
                        local_hash = compute_local_hash(filename)

                        target_ip = server_pasv_ip if self.data_mode == "PASSIVE" else self.hostID
                        target_port = server_pasv_port if self.data_mode == "PASSIVE" else UDP_PORT
                        
                        if self.data_mode == "ACTIVE" and "port" in str_data:
                            try:
                                target_port = int(str_data.split("port")[-1].strip())
                            except ValueError:
                                pass
                                
                        if active_udp_socket is None:
                            active_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                        try:
                            rdt_send_file(active_udp_socket, (target_ip, target_port), filename)
                            print(f"[System] File sent via RDT UDP to {target_ip}:{target_port}!")
                        except Exception as e:
                            print(f"[System] UDP Error: {e}")
                        finally:
                            if active_udp_socket:
                                active_udp_socket.close()

                        complete_msg = s.recv(1024).decode("utf8").strip()
                        print(f"Server: {complete_msg}")
                        
                        # Post-transfer integrity verification
                        if "226" in complete_msg and local_hash:
                            print("[System] Verifying data integrity (Upload)...")
                            # Request Server to calculate hash of the file it just received
                            s.sendall(f"HASH {filename}\r\n".encode("utf8"))
                            hash_resp = s.recv(1024).decode("utf8").strip()
                            
                            if hash_resp.startswith("200"):
                                server_hash = hash_resp.split(" ")[1]
                                if local_hash == server_hash:
                                    print(f"[+] INTEGRITY VERIFIED: Match SHA-256!\n    Hash: {local_hash}")
                                else:
                                    print(f"[-] INTEGRITY FAILED: Data Corrupted!\n    Client: {local_hash}\n    Server: {server_hash}")

                    else:
                        print(f"[System] Local error: File '{filename}' not found on your machine.")
                        if active_udp_socket:
                            active_udp_socket.close()
                        complete_msg = s.recv(1024).decode("utf8").strip()
                        print(f"Server: {complete_msg}")

                # Verify file integrity after upload
                if "226" in complete_msg and local_hash:
                    print("[System] Verifying data integrity (Upload)...")
                    # Request Server to calculate hash of the file it just received
                    s.sendall(f"HASH {filename}\r\n".encode("utf8"))
                    hash_resp = s.recv(1024).decode("utf8").strip()
                            
                    if hash_resp.startswith("200"):
                        server_hash = hash_resp.split(" ")[1]
                        if local_hash == server_hash:
                            print(f"[+] INTEGRITY VERIFIED: Match SHA-256!\n    Hash: {local_hash}")
                        else:
                            print(f"[-] INTEGRITY FAILED: Data Corrupted!\n    Client: {local_hash}\n    Server: {server_hash}")

            elif cmd == "LIST" and str_data.startswith("150"):
                try:
                    if self.data_mode == "PASSIVE":
                        active_udp_socket.sendto(b"READY", (server_pasv_ip, server_pasv_port))
                        
                    print("\n--- DIRECTORY LISTING ---")
                    active_udp_socket.settimeout(5.0)
                    while True:
                        try:
                            chunk, _ = active_udp_socket.recvfrom(2048)
                            if chunk == b'__EOF__':
                                break
                            print(chunk.decode('utf-8'), end="")
                        except socket.timeout:
                            print("[System] Directory listing timed out.")
                            break
                    print("-------------------------")
                except Exception as e:
                    print(f"[SYSTEM] UDP Error: {e}")
                finally:
                    active_udp_socket.close()
                    complete_msg = s.recv(1024).decode('utf-8').strip()
                    print(f"Server: {complete_msg}")
    

if __name__ == "__main__":
    print("==========================================================")
    print("                FTP CLIENT NODE                           ")
    print("==========================================================\n")
    server_ip = input("Enter server IP (default: 127.0.0.1): ").strip() or "127.0.0.1"
    server_port = int(input("Enter server Port (default: 9000): ").strip() or 9000)
    
    print("[*] Available client commands: ACTV_MODE, PASV_MODE")
    print("Use one of these commands to toggle active/passive mode")
    print("-----------------------------------\n\n")
    client = ClientNode(hostID=server_ip, port=server_port)
    client.connect()