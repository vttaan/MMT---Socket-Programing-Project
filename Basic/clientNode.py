from operatingMode import Node
import time

TCP_PORT = 1234
UDP_PORT = 5000


'''client = Node(hostID = '0.0.0.0', port = 1200, mode = "Active")
time.sleep(1)
client.switchToActiveMode(otherHostID = '127.0.0.1', otherPort = 1234, msg = "Hello")'''

client = Node(hostID = '0.0.0.0', port = 1200, mode = "Active", protocol = "UDP")
time.sleep(1)
client.switchToActiveMode(otherHostID = '127.0.0.1', otherPort = 5000, msg = "Hello")