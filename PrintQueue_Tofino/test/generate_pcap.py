import socket
import random
import argparse
import time
import threading
from scapy.all import *


ETHERTYPE_PRINTQUEUE = 0x080c
ETHERTYPE_IPV4 = 0x0800

if __name__=='__main__':
    pkt_len = 1024
    pkt = Ether(src='aa:bb:cc:dd:ee:ff', dst='ff:ff:ff:ff:ff:ff', type=ETHERTYPE_IPV4) / IP(src='202.112.237.101', dst='202.112.237.106') / TCP(dport=2222, sport=3333)
    msg_len = pkt_len - len(pkt)
    pkt = pkt / bytearray([0xcc for i in range(0, msg_len)])
    
    pkt2 = Ether(src='aa:bb:cc:dd:ee:ff', dst='ff:ff:ff:ff:ff:ff', type=ETHERTYPE_IPV4) / IP(src='202.112.237.101', dst='202.112.237.104') / TCP(dport=2222, sport=3333)
    msg_len = pkt_len - len(pkt)
    pkt2 = pkt2 / bytearray([0xaa for i in range(0, msg_len)])

    pkts = [pkt, pkt2]
    wrpcap('aa.pcap', pkts)
