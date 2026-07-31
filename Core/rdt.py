import socket
import struct
import os
import time

UDP_PORT = 5000
PACKET_SIZE = 4096      # max payload
HEADER_FORMAT = "!IIB"   # big-endian + seq_num(4) + ack_num(4) + flags(1)  
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 9 bytes
TIMEOUT = 0.5            # Socket timeout in seconds for retransmission

FLAG_DATA = 0x01
FLAG_ACK  = 0x02
FLAG_FIN  = 0x04


# Pack a RDT header & data
def make_packet(seq_num: int, ack_num: int, flags: int, data: bytes = b"") -> bytes:
    header = struct.pack(HEADER_FORMAT, seq_num, ack_num, flags)
    return header + data

# Unpack a RDT header & data
def parse_packet(raw_data: bytes):
    if len(raw_data) < HEADER_SIZE:
        return None, None, None, b""
    seq_num, ack_num, flags = struct.unpack(HEADER_FORMAT, raw_data[:HEADER_SIZE])
    payload = raw_data[HEADER_SIZE:]
    return seq_num, ack_num, flags, payload


#Rdt use file(use for client RETR & server STOR)
def rdt_send_file(udp_socket: socket.socket, target_addr: tuple, filepath: str):
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        print(f"[RDT Sender] Error: File '{filepath}' does not exist.")
        return False

    udp_socket.settimeout(TIMEOUT)
    seq_num = 0

    with open(filepath, "rb") as f:
        while True:
            payload = f.read(PACKET_SIZE)
            is_eof = len(payload) == 0

            # Determine flags: regular DATA or FIN at end-of-file
            flags = FLAG_FIN if is_eof else FLAG_DATA
            packet = make_packet(seq_num, 0, flags, payload)

            # Stop and wait
            ack_received = False
            retries = 0
            max_retries = 10
            
            while not ack_received and retries < max_retries:
                try:
                    # 1. Send Packet
                    udp_socket.sendto(packet, target_addr)

                    # 2. Wait for ACK
                    ack_data, _ = udp_socket.recvfrom(1024)
                    ack_seq, ack_num, ack_flags, _ = parse_packet(ack_data)

                    # 3. Validate ACK
                    if (ack_flags & FLAG_ACK) and ack_num == seq_num:
                        ack_received = True
                        seq_num = 1 - seq_num  
                    else:
                        print(f"[RDT Sender] Duplicate/Invalid ACK {ack_num} received. Resending...")

                except socket.timeout:
                    retries += 1
                    print(f"[RDT Sender] Timeout! Resending seq={seq_num} (Attempt {retries}/{max_retries})...")
                except Exception as e:
                    print(f"[RDT Sender] Socket error: {e}")
                    break

            if retries >= max_retries:
                print(f"[RDT Sender] Failed to transmit file after max retries.")
                return False

            if is_eof:
                print(f"[RDT Sender] Successfully sent FIN packet and received ACK. Transfer complete.")
                break

    return True


#Rdt use file(use for server STOR & client RETR)
def rdt_receive_file(udp_socket: socket.socket, save_filepath: str):
    expected_seq = 0
    udp_socket.settimeout(5.0)  

    with open(save_filepath, "wb") as f:
        while True:
            try:
                raw_data, sender_addr = udp_socket.recvfrom(HEADER_SIZE + PACKET_SIZE)
                seq_num, ack_num, flags, payload = parse_packet(raw_data)

                if seq_num is None:
                    continue  # Malformed packet

                # Check if it's the expected packet
                if seq_num == expected_seq:
                    if len(payload) > 0:
                        f.write(payload)

                    # Send ACK for received packet
                    ack_packet = make_packet(0, seq_num, FLAG_ACK)
                    udp_socket.sendto(ack_packet, sender_addr)

                    # Flip expected sequence number (0 -> 1 -> 0)
                    expected_seq = 1 - expected_seq

                    # If FIN flag is present, transfer is finished
                    if flags & FLAG_FIN:
                        print(f"[RDT Receiver] FIN received. File successfully saved to '{save_filepath}'.")
                        break

                else:
                    last_ack_seq = 1 - expected_seq
                    ack_packet = make_packet(0, last_ack_seq, FLAG_ACK)
                    udp_socket.sendto(ack_packet, sender_addr)
                    print(f"[RDT Receiver] Duplicate seq={seq_num} received. Resent ACK for {last_ack_seq}.")

            except socket.timeout:
                print(f"[RDT Receiver] Transfer timed out waiting for data.")
                return False
            except Exception as e:
                print(f"[RDT Receiver] Error receiving file: {e}")
                return False

    return True