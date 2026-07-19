


import socket
import os
#HOST = the host IP
#PORT = port of the server application
HOST = '127.0.0.1' 


TCP_PORT = 1234 #TCP port
UDP_PORT = 5000 #UDP port
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

User = "admin"
password = "1234"

s.bind((HOST, TCP_PORT))
s.listen()


conn, addr = s.accept()

print(f"Connected by {addr}")


conn.sendall(b"220 Service ready\r\n")

user_name = ""
password_type = ""
check = False # check if valid log in



try:
	while True:
		
		data = conn.recv(1024)
		
		str_data = data.decode("utf8").strip() # remove "\r\n"
		part  = str_data.split(' ', 1) # split string
		cmd = part[0].upper() # make it into upper case 

		if cmd == "USER":
			conn.sendall("331 Username Valid, Type password\r\n".encode('utf-8'))
			if len(part) > 1:
				user_name = part[1]
		elif cmd == "PASS":
			if (len(part) > 1 and part[1] == password and user_name == User):
				check = True
				conn.sendall("230 Logged in successfully\r\n".encode('utf-8'))
			else:
				conn.sendall("530 Invalid username or password\r\n".encode('utf-8'))
				continue


		elif cmd == "RETR":
			if not check:
				conn.sendall("530 Not logged in\r\n".encode('utf-8'))
				continue
			if len(part) > 1:
				filename = part[1]
				if not os.path.exists(filename): # check if the file in the same path as yours
					conn.sendall("550 File unavailable\r\n".encode('utf-8'))
					continue
				
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
		else:
			
			conn.sendall("500 Unknown command\r\n".encode('utf-8'))

		

		if cmd == "QUIT":
			conn.sendall("221 Good bye, end system...\r\n".encode('utf-8'))
			break

except Exception:
	print(f"Disconnected")
finally:
	conn.close()
	s.close()