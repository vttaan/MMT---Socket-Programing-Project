from operatingMode import Node
import time

TCP_PORT = 1234
UDP_PORT = 5000

server = Node(hostID = '127.0.0.1', port = UDP_PORT)

try:
    #server.initPassiveTCP()
    server.initPassiveUDP()
except KeyboardInterrupt:
    server.stop()
    print("Server node stopped")

