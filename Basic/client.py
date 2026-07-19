import socket

HOST = '127.0.0.1' #local host
TCP_PORT = 1234
UDP_PORT = 5000


# client connect server
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((HOST, TCP_PORT))

try:
	print("Server:", s.recv(1024).decode("utf8").strip())

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

			file, addr = udp.recvfrom(4096) # recieve file from server

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