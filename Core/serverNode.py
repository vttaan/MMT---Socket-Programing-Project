import socket
import threading
from FTPCommandHandle import handle_ftp_command

class ServerNode:
    def __init__(self, hostID="127.0.0.1", port=1234):
        self.hostID = hostID
        self.port = port
        self.server = None
        self.isRunning = False
        self.username = "admin"
        self.password = "1234"
        
    def setUpCredentials(self):
        u = input("Input server's username (default: admin): ").strip()
        p = input("Input password (default: 1234): ").strip()
        self.username = u if u else "admin"
        self.password = p if p else "1234"
        print(f"[SERVER] Configured credentials: Username={self.username}, Password={self.password}")

    def start(self):
        self.setUpCredentials()
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
        print(f'Server listening on {self.hostID}:{self.port}')
        print('------------------------------')
        
        while self.isRunning:
            try:
                self.server.settimeout(1)
                conn, addr = self.server.accept()
                
                client_thread = threading.Thread(target=self._client_handler, args=(conn, addr), daemon=True)
                client_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                break
                
    def _client_handler(self, conn, addr):
        tid = threading.get_ident()
        print(f"[SERVER Thread-{tid}] [+] Accepted new connection from {addr}")
        try:
            data = conn.recv(1024)
            print(f"[SERVER Thread-{tid}] Handshake payload: {data.decode('utf8').strip()}")
            conn.sendall(b"Hello from FTP Server!\r\n")
            
            # State tracking for this connection
            auth_state = {'userName': None, 'loggedIn': False, 'cwd': '/'}
            
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                
                str_data = data.decode("utf8").strip()
                part = str_data.split(' ', 1)
                cmd = part[0].upper()

                should_quit = handle_ftp_command(cmd, part, conn, addr, auth_state, self.username, self.password)
                if should_quit:
                    break

        except Exception as e:
            print(f"[SERVER Thread-{tid}] Disconnected client {addr}: {e}")
        finally:
            print(f"[SERVER Thread-{tid}] Closed connection for client {addr}")
            conn.close()

    def stop(self):
        self.isRunning = False
        if self.server:
            try:
                self.server.close()
            except:
                pass
            self.server = None

if __name__ == "__main__":
    print("==========================================================")
    print("             FTP SERVER NODE                              ")
    print("==========================================================\n")
    server = ServerNode(hostID="127.0.0.1", port=9000)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[-] Stopping server...")
    finally:
        server.stop()
        print("\n[=== SERVER ENDED ===]")
