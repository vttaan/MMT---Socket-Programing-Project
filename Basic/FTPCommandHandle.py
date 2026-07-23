import socket
import os

UDP_PORT = 5000

def handle_ftp_command(cmd, part, conn, addr, auth_state, expected_user, expected_pass):
    
    if cmd == "USER":
        conn.sendall("331 Username Valid, Type password\r\n".encode('utf-8'))
        if len(part) > 1:
            auth_state['userName'] = part[1]
    elif cmd == "PASS":
        if (len(part) > 1 and part[1] == expected_pass and auth_state.get('userName') == expected_user):
            auth_state['loggedIn'] = True
            conn.sendall("230 Logged in successfully\r\n".encode('utf-8'))
        else:
            conn.sendall("530 Invalid username or password\r\n".encode('utf-8'))

    elif cmd == "RETR":
        if not auth_state.get('loggedIn'):
            conn.sendall("530 Not logged in\r\n".encode('utf-8'))
            return False
            
        if len(part) > 1:
            filename = part[1]
            if not os.path.exists(filename):
                conn.sendall("550 File unavailable\r\n".encode('utf-8'))
                return False
            
            conn.sendall("150 File status okay, opening data connection\r\n".encode('utf-8'))

            # UDP port
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # read file ASCII
            with open(filename,'r',encoding="utf-8") as f:
                data = f.read()
            
            # send by udp
            udp.sendto(data.encode('utf-8'), (addr[0], UDP_PORT))
            
            #end udp
            udp.close()

            conn.sendall("226 Transfer complete\r\n".encode('utf-8'))
        else:
            conn.sendall("500 Syntax error\r\n".encode('utf-8'))
            
    elif cmd == "QUIT":
        conn.sendall("221 Good bye, end system...\r\n".encode('utf-8'))
        return True
    else:
        conn.sendall("500 Unknown command\r\n".encode('utf-8'))
        
    return False
