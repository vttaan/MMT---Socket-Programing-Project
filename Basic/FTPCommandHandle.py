import socket
import os
import hashlib
import time
import stat
import select
from datetime import datetime

UDP_PORT = 5000

def check_abort(conn):
    try:
        #select.selct -> 4 parameters(read,write,error,timeout)
        rlist, _, _ = select.select([conn], [], [], 0)
        #check if there is file transfer
        if rlist:
            data = conn.recv(1024)
            if not data:
                #abort transfer
                return True
            msg = data.decode('utf-8', errors='ignore').strip().upper()
            if "ABOR" in msg:
                return True
    except Exception:
        pass
    return False


def handle_ftp_command(cmd, part, conn, addr, auth_state, expected_user, expected_password):
    # Command used for entering username
    if cmd == "USER":
                conn.sendall("331 Username Valid, Type password\r\n".encode('utf-8'))
                if len(part) > 1:
                    auth_state['userName'] = part[1]
                return False

    # Command used for entering password
    elif cmd == "PASS":
        if len(part) > 1 and part[1] == expected_password and auth_state.get('userName') == expected_user:
            auth_state['loggedIn'] = True
            conn.sendall("230 Logged in successfully\r\n".encode('utf-8'))
        else:
            conn.sendall("530 Invalid username or password\r\n".encode('utf-8'))
        return False

    elif not auth_state.get('loggedIn') and cmd not in ["QUIT", "NOOP", "SYST"]:
        conn.sendall("530 Not logged in\r\n".encode('utf-8'))
        return False

    # Command used for NOOP (No Operation / Keep-alive)
    elif cmd == "NOOP":
        conn.sendall("200 OK\r\n".encode('utf-8'))

    # Command used for setting representation type (ASCII/Binary)
    elif cmd == "TYPE":
        if len(part) > 1:
            transfer_type = part[1].upper()
            if (transfer_type in ['A','I']):
                auth_state['type'] = transfer_type
                conn.sendall(f"200 Type set to {part[1].upper()}\r\n".encode('utf-8'))
            else:
                conn.sendall("504 Command not implemented for that parameter\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to set data transfer mode (Stream, Block, Compressed)
    elif cmd == "MODE":
        if len(part) > 1:
            mode = part[1].upper()
            if mode in ['S', 'B', 'C']:
                auth_state['mode'] = mode
                conn.sendall(f"200 Mode set to {mode}\r\n".encode('utf-8'))
            else:
                conn.sendall("504 Command not implemented for that parameter\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used for Active Mode data port configuration
    elif cmd == "PORT":
        if len(part) > 1:
            try:
                params = part[1].split(',')
                if len(params) == 6:
                    ip = ".".join(params[:4])
                    port = (int(params[4]) << 8) + int(params[5])
                    auth_state['data_addr'] = (ip, port)
                    conn.sendall("200 PORT command successful\r\n".encode('utf-8'))
                else:
                    conn.sendall("501 Illegal PORT command\r\n".encode('utf-8'))
            except Exception:
                conn.sendall("501 Syntax error\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used for Passive Mode port discovery
    elif cmd == "PASV":
        ip_formatted = addr[0].replace('.', ',')
        p1 = UDP_PORT // 256
        p2 = UDP_PORT % 256
        conn.sendall(f"227 Entering Passive Mode ({ip_formatted},{p1},{p2})\r\n".encode('utf-8'))

    # Command used to display current working directory
    elif cmd == "PWD":
        current_path = os.getcwd()
        conn.sendall(f'257 "{current_path}" is current directory.\r\n'.encode('utf-8'))

    # Command used to change directory
    elif cmd == "CWD":
        if len(part) > 1:
            try:
                os.chdir(part[1])
                conn.sendall(f'250 Directory changed to "{os.getcwd()}"\r\n'.encode('utf-8'))
            except Exception:
                conn.sendall("550 Directory not found or access denied.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to change to parent directory
    elif cmd == "CDUP": 
        try:
            os.chdir("..")
            conn.sendall(f'250 Directory changed to "{os.getcwd()}"\r\n'.encode('utf-8'))
        except Exception:
            conn.sendall("550 Failed to change directory.\r\n".encode('utf-8'))

    # Command used to list files in directory
    elif cmd == "LIST":
        try:
            conn.sendall("150 Opening data connection for directory list.\r\n".encode('utf-8'))

            list_str = ""
            target_dir = part[1] if len(part) > 1 else os.getcwd() 

            if os.path.exists(target_dir) and os.path.isdir(target_dir):
                for entry in os.scandir(target_dir):
                    info = entry.stat()

                    file_type = 'd' if entry.is_dir() else '-'
                    perms = stat.filemode(info.st_mode)

                    size = str(info.st_size) 

                    mtime = datetime.fromtimestamp(info.st_time).strftime("%b %d %H:%M")

                    name = entry.name


                    list_str += f"{file_type}{perms[1:]} {size:>8} bytes  {mtime}  {name}\r\n"

                if not list_str:
                    list_str = "Directory is empty.\r\n"

                udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                udp.sendto(list_str.encode('utf-8'), (addr[0], UDP_PORT))
                time.sleep(0.001) # Nghỉ chống nghẽn

                udp.sendto(b"__EOF__", (addr[0], UDP_PORT))
                udp.close()

                conn.sendall("226 Transfer complete.\r\n".encode('utf-8'))
            else:
                conn.sendall("550 Directory not found.\r\n".encode('utf-8'))
        except Exception as e:
            conn.sendall(f"451 Local error: {e}\r\n".encode('utf-8'))

    # Command used to display size of a file
    elif cmd == "SIZE": 
        if len(part) > 1:
            filename = part[1]
            if os.path.exists(filename) and os.path.isfile(filename):
                size = os.path.getsize(filename)
                conn.sendall(f"213 {size}\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to return last modification timestamp of a file
    elif cmd == "MDTM":
        if len(part) > 1:
            filename = part[1]
            if os.path.exists(filename) and os.path.isfile(filename):
                mtime = os.path.getmtime(filename)
                timestamp = time.strftime('%Y%m%d%H%M%S', time.gmtime(mtime))
                conn.sendall(f"213 {timestamp}\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to create a directory/folder
    elif cmd == "MKD":
        if len(part) > 1:
            try:
                os.mkdir(part[1])
                conn.sendall(f'257 "{part[1]}" directory created.\r\n'.encode('utf-8'))
            except FileExistsError:
                conn.sendall("550 Directory already exists.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to remove an empty directory
    elif cmd == "RMD":
        if len(part) > 1:
            try:
                os.rmdir(part[1])
                conn.sendall("250 Directory removed.\r\n".encode('utf-8'))
            except Exception:
                conn.sendall("550 Directory not found or not empty.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to delete a file
    elif cmd == "DELE":
        if len(part) > 1:
            if os.path.exists(part[1]) and os.path.isfile(part[1]):
                os.remove(part[1])
                conn.sendall("250 File deleted.\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to specify file to rename (Rename From)
    elif cmd == "RNFR":
        if len(part) > 1:
            if os.path.exists(part[1]):
                auth_state['rename_file_target'] = part[1]
                conn.sendall("350 Ready for RNTO.\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to specify new filename and execute rename (Rename To)
    elif cmd == "RNTO":
        if len(part) > 1:
            rename_target = auth_state.get('rename_file_target')
            if rename_target:
                os.rename(rename_target, part[1])
                auth_state['rename_file_target'] = ""
                conn.sendall("250 Rename successful.\r\n".encode('utf-8'))
            else:
                conn.sendall("503 Bad sequence of commands (Send RNFR first).\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to download file from server to client
    elif cmd == "RETR":
        if len(part) > 1:
            filename = part[1]
            if not os.path.exists(filename) or not os.path.isfile(filename):
                conn.sendall("550 File unavailable\r\n".encode('utf-8'))
            else:
                conn.sendall("150 File status okay, opening data connection\r\n".encode('utf-8'))
                udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                aborted = False
                
                with open(filename, 'rb') as f:
                    #check if aborts
                    while True:
                        if check_abort(conn):
                            aborted = True
                            break

                        chunk = f.read(1024)
                        if not chunk:
                            break

                        udp.sendto(chunk, (addr[0], UDP_PORT))
                        time.sleep(0.001) 

                if aborted:
                    udp.close()
                    conn.sendall("426 Data connection closed; transfer aborted.\r\n".encode('utf-8'))
                    conn.sendall("226 ABOR command successful.\r\n".encode('utf-8'))
                else:
                    udp.sendto(b'__EOF__', (addr[0], UDP_PORT))
                    udp.close()
                    conn.sendall("226 Transfer complete\r\n".encode('utf-8'))

    # Command used to upload file from client to server
    elif cmd == "STOR":
        if len(part) > 1:
            filename = part[1]
            conn.sendall("150 Ok to send data\r\n".encode('utf-8'))
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(('0.0.0.0', UDP_PORT))
            udp.settimeout(0.5)

            aborted = False
            with open(filename, 'wb') as f:
                while True:
                    #check if abort
                    if check_abort(conn):
                        aborted = True
                        break

                    try:
                        chunk, _ = udp.recvfrom(2048)

                        if chunk == b'__EOF__':
                            break

                        f.write(chunk)
                    except socket.timeout:
                        continue
                    except Exception:
                        break

            udp.close()

            if aborted:
                conn.sendall("426 Data connection closed; transfer aborted.\r\n".encode('utf-8'))
                conn.sendall("226 ABOR command successful.\r\n".encode('utf-8'))
            else:
                conn.sendall("226 Transfer complete\r\n".encode('utf-8'))
        else:
            conn.sendall("500 Syntax error\r\n".encode('utf-8'))

    # Command used to upload a file with a guaranteed unique filename
    elif cmd == "STOU":
        unique_filename = f"file_{int(time.time())}.dat"
        conn.sendall(f"150 FILE: {unique_filename}\r\n".encode('utf-8'))
        
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp.bind(('0.0.0.0', UDP_PORT))
        #settimeour
        udp.settimeout(0.5)

        aborted = False
        with open(unique_filename, 'wb') as f:
            while True:
                #check if abort
                if check_abort(conn):
                    aborted = True
                    break
                try:
                    chunk, _ = udp.recvfrom(2048)
                    if chunk == b'__EOF__':
                        break
                    f.write(chunk)
                    #if timeout
                except socket.timeout:
                    continue
                except Exception:
                    break
        udp.close()

        if aborted:
            conn.sendall("426 Data connection closed; transfer aborted.\r\n".encode('utf-8'))
            conn.sendall("226 ABOR command successful.\r\n".encode('utf-8'))
        else:
            conn.sendall("226 Transfer complete\r\n".encode('utf-8'))

    # Command used to append uploaded data to an existing file or create it
    elif cmd == "APPE":
        if len(part) > 1:
            filename = part[1]
            conn.sendall("150 Ok to send data\r\n".encode('utf-8'))
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(('0.0.0.0', UDP_PORT))
            udp.settimeout(0.5)

            aborted = False
            with open(filename, 'ab') as f:
                while True:
                    if check_abort(conn):
                        aborted = True
                        break
                    try:
                        chunk, _ = udp.recvfrom(2048)
                        if chunk == b'__EOF__':
                            break
                        f.write(chunk)
                    except socket.timeout:
                        continue
                    except Exception:
                        break
            udp.close()

            if aborted:
                conn.sendall("426 Data connection closed; transfer aborted.\r\n".encode('utf-8'))
                conn.sendall("226 ABOR command successful.\r\n".encode('utf-8'))
            else:
                conn.sendall("226 Transfer complete\r\n".encode('utf-8'))
        else:
            conn.sendall("500 Syntax error\r\n".encode('utf-8'))

    # Command used to calculate cryptographic hash (SHA-256) for file verification
    elif cmd == "HASH":
        if len(part) > 1:
            filename = part[1]
            if os.path.exists(filename) and os.path.isfile(filename):
                sha256_hash = hashlib.sha256()
                with open(filename, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)
                file_hash = sha256_hash.hexdigest()
                conn.sendall(f"200 {file_hash}\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
        else:
            conn.sendall("501 Syntax error\r\n".encode('utf-8'))

    # Command used to abort an active transfer/reset state (when no transfer is active)
    elif cmd == "ABOR":
        conn.sendall("226 No transfer in progress.\r\n".encode('utf-8'))

    # Command used to list supported commands
    elif cmd == "HELP":
        help_msg = "214 Supported commands: USER, PASS, PWD, CWD, CDUP, LIST, NLST, RETR, STOR, STOU, APPE, DELE, MKD, RMD, RNFR, RNTO, SIZE, MDTM, STAT, HASH, MODE, PASV, PORT, ABOR, HELP, QUIT\r\n"
        conn.sendall(help_msg.encode('utf-8'))

    # Command used to get server status or file status
    elif cmd == "STAT":
        if len(part) == 1:
            conn.sendall("211-Server status:\r\n Version: 1.0 (Basic UDP Hybrid)\r\n211 End of status.\r\n".encode('utf-8'))
        else:
            filename = part[1]
            if os.path.exists(filename) and os.path.isfile(filename):
                size = os.path.getsize(filename)
                conn.sendall(f"213-Status of {filename}:\r\n Size: {size} bytes\r\n213 End of status.\r\n".encode('utf-8'))
            else:
                conn.sendall("550 File not found.\r\n".encode('utf-8'))
                
    # Command used to get a simple list of file names
    elif cmd == "NLST":
        try:
            files = [f for f in os.listdir(os.getcwd()) if os.path.isfile(f)]
            file_list_str = "\r\n".join(files) + "\r\n"
            conn.sendall("150 Opening ASCII mode data connection for NLST.\r\n".encode('utf-8'))
            conn.sendall(file_list_str.encode('utf-8'))
            conn.sendall("226 Transfer complete.\r\n".encode('utf-8'))
        except Exception as e:
            conn.sendall(f"451 Local error: {e}\r\n".encode('utf-8'))

    # Command used to disconnect session
    elif cmd == "QUIT":
        conn.sendall("221 GOODBYE, end system...\r\n".encode('utf-8'))
        return True

    else:
        conn.sendall("500 Unknown command\r\n".encode('utf-8')) 

    return False