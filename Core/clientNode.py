import socket
import os
import time
import struct
import select
import threading
from rdt import rdt_send_file, rdt_receive_file


UDP_PORT = 5000

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
        self.transfer_thread = None
        self.active_transfer_socket = None
        self.transfer_in_progress = False

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
            # Drain any status messages sitting on control socket before prompting
            try:
                rlist, _, _ = select.select([s], [], [], 0.05)
                if rlist:
                    data = s.recv(1024)
                    if data:
                        print(f"Server: {data.decode('utf-8', errors='ignore').strip()}")
            except Exception:
                pass

            msg = input(f"FTP Client ({self.data_mode})> ").strip()
            if not msg:
                continue

            # Drain any status messages that arrived while user was typing input
            try:
                rlist, _, _ = select.select([s], [], [], 0.05)
                if rlist:
                    data = s.recv(1024)
                    if data:
                        print(f"Server: {data.decode('utf-8', errors='ignore').strip()}")
            except Exception:
                pass

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

            if cmd == "ABOR":
                if self.transfer_in_progress:
                    print("[System] Aborting active file transfer...")
                    if self.active_transfer_socket:
                        try:
                            self.active_transfer_socket.close()
                        except Exception:
                            pass
                
                s.sendall(b"ABOR\r\n")
                self.transfer_in_progress = False

                # Read response(s) from server for ABOR
                time.sleep(0.1)
                try:
                    s.settimeout(1.0)
                    while True:
                        rlist, _, _ = select.select([s], [], [], 0.2)
                        if not rlist:
                            break
                        resp_data = s.recv(1024)
                        if not resp_data:
                            break
                        print(f"Server: {resp_data.decode('utf-8', errors='ignore').strip()}")
                except Exception:
                    pass
                finally:
                    s.settimeout(None)
                continue

            if cmd in ["STOR", "APPE"]:
                if len(part) <= 1:
                    print("[System] Syntax error: Please specify a file.")
                    continue
                filename = part[1]
                if not os.path.exists(filename) or not os.path.isfile(filename):
                    print(f"[System] Local error: File '{filename}' not found on your machine.")
                    continue

            active_udp_socket = None
            server_pasv_ip = None
            server_pasv_port = None

            # Setup Data Connection BEFORE sending data transfer commands
            if cmd in ["RETR", "LIST", "STOR", "STOU", "APPE"]:
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
            if cmd in ["RETR", "LIST", "STOR", "STOU", "APPE"] and not str_data.startswith("150"):
                if active_udp_socket:
                    active_udp_socket.close()
                continue

            # --- Data Transfer Handlers ---

            if cmd in ["RETR", "STOR", "STOU", "APPE"] and str_data.startswith("150"):
                self.active_transfer_socket = active_udp_socket
                self.transfer_in_progress = True

                def bg_transfer_worker(command_type, parts, active_sock, pasv_ip, pasv_port, initial_resp):
                    try:
                        if command_type == "RETR":
                            filename = "download_file.dat" if len(parts) == 1 else "downloaded_" + parts[1]
                            if active_sock is None:
                                active_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                active_sock.bind(('0.0.0.0', 0))

                            if self.data_mode == "PASSIVE" and pasv_ip and pasv_port:
                                active_sock.sendto(b"READY", (pasv_ip, pasv_port))

                            print(f"\n[System] Opening RDT UDP socket to receive '{filename}'...")
                            rdt_receive_file(active_sock, filename)
                        elif command_type in ["STOR", "STOU", "APPE"]:
                            filename = parts[1] if len(parts) > 1 else "upload.dat"
                            target_ip = pasv_ip if (self.data_mode == "PASSIVE" and pasv_ip) else self.hostID
                            target_port = pasv_port if (self.data_mode == "PASSIVE" and pasv_port) else UDP_PORT
                            
                            if "port" in initial_resp.lower():
                                try:
                                    target_port = int(initial_resp.lower().split("port")[-1].strip().split()[0])
                                except (ValueError, IndexError):
                                    pass
                                    
                            if active_sock is None:
                                active_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                            print(f"\n[System] Opening RDT UDP socket to send '{filename}' to {target_ip}:{target_port}...")
                            rdt_send_file(active_sock, (target_ip, target_port), filename)
                            print(f"\n[System] File '{filename}' sent via RDT UDP to {target_ip}:{target_port}!")
                    except Exception as e:
                        print(f"\n[System] UDP Transfer Error / Interrupted: {e}")
                    finally:
                        if active_sock:
                            try:
                                active_sock.close()
                            except Exception:
                                pass
                        self.transfer_in_progress = False

                self.transfer_thread = threading.Thread(
                    target=bg_transfer_worker,
                    args=(cmd, part, active_udp_socket, server_pasv_ip, server_pasv_port, str_data),
                    daemon=True
                )
                self.transfer_thread.start()
                print("[System] Transfer started in background thread. Type 'ABOR' at any time to cancel.")
                continue

            elif cmd == "LIST" and str_data.startswith("150"):
                try:
                    if self.data_mode == "PASSIVE" and server_pasv_ip and server_pasv_port:
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