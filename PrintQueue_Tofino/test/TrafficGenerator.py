import socket
import random
import argparse
import time
import threading
from scapy.all import *

if_list = {'S101':'p4p2',
           'S102':'enp131s0f1',
           'S103':'enp131s0f1',
           'S104':'enp4s0f0',
           'S105':'enp5s0f0',
           'S106':'p2p2'}

ETHERTYPE_PRINTQUEUE = 0x080c
ETHERTYPE_IPV4 = 0x0800

class Dove(Packet):
    name = "Dove "
    fields_desc=[BitField('control_bit',0,1),
                 BitField('color_bit',0,1),
                 BitField('reserved_bit',0,6),
                 ShortField("packet_num",0),                 \
                 IntField('ts',0),]

class INT(Packet):
    name = "INT"
    fields_desc=[IntField('dequeue_ts',0),
                 IntField('queue_length', 0)]

class TrafficGenerator:
    def __init__(self,host):
        self.iface = if_list[host]
        self.send_pkt_num = 0
        self.recv_pkt_num = 0
    
    def printqueue_pkt(self,ip_addr_str,msg='printqueue data packet'):
        ip_addr = socket.gethostbyname(ip_addr_str)
        pkt =  Ether(src=get_if_hwaddr(self.iface), dst='ff:ff:ff:ff:ff:ff', type=ETHERTYPE_PRINTQUEUE)
        int_data = INT(dequeue_ts=random.randint(0,4096), queue_length=random.randint(0,4096))
        pkt = pkt / IP(src='101.101.101.101', dst=ip_addr) / TCP(dport=2222, sport=3333)  / int_data / msg
        sendp(pkt, iface=self.iface, verbose=False)
        return pkt

    def tcp_pkt(self,ip_addr_str,msg='tcp data packet'):
        ip_addr = socket.gethostbyname(ip_addr_str)
        pkt = Ether(src=get_if_hwaddr(self.iface), dst='ff:ff:ff:ff:ff:ff', type=ETHERTYPE_IPV4) / IP(src='101.101.101.101', dst=ip_addr) / TCP(dport=2222, sport=3333)  / msg
        sendp(pkt, iface=self.iface, verbose=False)
        return pkt

    def send_loop(self):
        while True:
            # self.printqueue_pkt(args.ip)
            self.tcp_pkt(args.ip)
            self.send_pkt_num += 1
            print('.',end='')
            sys.stdout.flush()

    def send(self,ip_addr_str,msg):
        print("sending on interface {} to IP address {}".format(self.iface, ip_addr_str))
        pkt = self.tcp_pkt(ip_addr_str,msg)
        pkt.show2()

    def handle_pkt(self,pkt):
        if pkt[Ether].type == ETHERTYPE_PRINTQUEUE or pkt[Ether].type == ETHERTYPE_IPV4 :
            print("------------got a packet-----------")
            self.recv_pkt_num += 1
            pkt.show2()
            #        hexdump(pkt)
            #        print "len(pkt) = ", len(pkt)
            sys.stdout.flush()

    def receive(self):
        print("start listening on interface {}".format(self.iface))
        sniff(iface=self.iface,prn=lambda x: self.handle_pkt(x))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', action='store_true', help="send packets")
    parser.add_argument('-r', action='store_true', help="receive packets")
    parser.add_argument('-host', type=str, help="Host",choices=['S101', 'S102', 'S103', 'S104', 'S105', 'S106'])
    parser.add_argument('-ip', type=str, help="The destination IP address to use")
    parser.add_argument('-msg', type=str, help="The message to include in packet", default="hello")
    args = parser.parse_args()
    t_g = TrafficGenerator(args.host)
    # if args.s:
    #     t_g.send(args.ip,args.msg)
    # elif args.r:
    #     t_g.receive()

    t_g.send_loop()
