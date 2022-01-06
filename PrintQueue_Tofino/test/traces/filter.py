'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    Filter out TCP packets and listen to interface
'''
import argparse
import sys
import socket
import random
import struct
import string
import math
import os
import json
import signal

from scapy.all import *
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP

ETHERTYPE_PRINTQUEUE = 0x080c
ETHERTYPE_IPV4 = 0x0800
IP_PROTOCOLS_TCP = 6

class INT(Packet):
    name = "INT"
    fields_desc=[IntField('dequeue_ts',0),
                 IntField('queue_length', 0)]

class FlowID(Packet):
    name = "FlowID"
    fields_desc = [IPField("src_ip", "0.0.0.0"),
                   IPField("dst_ip", "0.0.0.0"),
                   ShortField('src_port', 0),
                   ShortField('dst_port', 0)]

class PacketFilter:
    def __init__(self, file_path = None):
        if not file_path:
            self.received_pkts = []

    def load(self, file_path):
        f = open(file_path, 'r')
        self.received_pkts = json.load(f)
        f.close()

    def hex2fields(self, flowID_hex):
        return FlowID(bytearray.fromhex(flowID_hex)).show2()

    def filter_pcap(self, pcap_path):
        filtered_pkts = []
        pkts = rdpcap(pcap_path)
        for pkt in pkts:
            # filter tcp packet
            if 'type' not in pkt[Ether].fields:
                continue
            if pkt[Ether].fields['type'] != ETHERTYPE_IPV4:
                continue
            if pkt[IP].fields['proto'] != IP_PROTOCOLS_TCP:
                continue
            filtered_pkts += pkt
        print('The total number of packets: {0}, the number of TCP packets: {1}'.format(len(pkts), len(filtered_pkts)))
        wl = pcap_path.split('.')
        wl[-2] += '_tcp'
        wrpcap('.'.join(wl), filtered_pkts)

    def retrieve(self, ts, te):
        self.received_pkts = sorted(self.received_pkts, key=lambda x: x['dequeue_ts'])
        retrieve_result = {}
        retrieve_result['ts'] = ts
        retrieve_result['te'] = te
        retrieve_result['retrieve_start_ts'] = ts
        retrieve_result['retrieve_end_ts'] = te
        retrieve_result['smallest_ts'] = self.received_pkts[0]['dequeue_ts']
        retrieve_result['largest_ts'] = self.received_pkts[0]['dequeue_ts']
        if ts < retrieve_result['smallest_ts']:
            print('Received Packets start from {0}. Request retrieving from {1}. Retrieve from {0}...'.
                  format(self.received_pkts[0]['dequeue_ts'], ts))
            retrieve_result['retrieve_start_ts'] = self.received_pkts[0]['dequeue_ts']
        if te > self.received_pkts[0]['dequeue_ts']:
            print('Received Packets end at {0}. Request retrieving to {1}. Retrieve to {0}...'.
                  format(self.received_pkts[0]['dequeue_ts'], te))
            retrieve_result['retrieve_end_ts'] = self.received_pkts[0]['dequeue_ts']
        GT_result = {} # {FID: N}
        for pkt in self.received_pkts:
            if ts < pkt['dequeue_ts'] and pkt['dequeue_ts'] < te:
                GT_result[pkt['FID']] = GT_result.get(pkt['FID'], 0) + 1
        retrieve_result['GT_result'] = GT_result
        return retrieve_result

    def retrieve_and_save(self, ts, te):
        r = self.retrieve(ts, te)
        file_path = './settings/g_{0}_{1}.json'.format(r['retrieve_start_ts'], r['retrieve_end_ts'])
        with open(file_path, 'w') as f:
            json.dump(r, f, indent=4)

    def receive(self, iface):
        print("start listening on interface {}".format(iface))
        sniff(iface=iface, prn=lambda x: self.handle_pkt(x))

    def save(self):
        self.received_pkts = sorted(self.received_pkts, key=lambda x: x['dequeue_ts'])
        file_path = './settings/R_{0}_{1}.json'.format(self.received_pkts[0]['dequeue_ts'], self.received_pkts[-1]['dequeue_ts'])
        with open(file_path, 'w') as f:
            json.dump(self.received_pkts, f, indent=4)

    def handle_pkt(self, pkt):
        if 'type' not in pkt[Ether].fields:
            return
        if pkt[Ether].type != ETHERTYPE_PRINTQUEUE:
            return
        FID_bytes = socket.inet_aton(pkt[IP].fields['src']) \
                    + socket.inet_aton(pkt[IP].fields['dst']) \
                    + pkt[TCP].fields['sport'].to_bytes(2, byteorder='big') \
                    + pkt[TCP].fields['dport'].to_bytes(2, byteorder='big')
        FID_hex = FID_bytes.hex()
        queue_info = INT(pkt[TCP].payload)
        pkt_info = {'dequeue_ts': queue_info.fields['dequeue_ts'], 'queue_length': queue_info.fields['queue_length'], 'FID': FID_hex}
        self.received_pkts.append(pkt_info)
        return

def save(signal, frame):
    print("Saving received packets...")
    filter.save()
    sys.exit(0)


if __name__ == '__main__':
    # test
    filter = PacketFilter()
    signal.signal(signal.SIGINT, save)
    filter.load_pcap('./test.pcap')
    filter.hex2fields('f0ffffffffffffff000a000f')
    filter.handle_pkt(Ether(type=ETHERTYPE_PRINTQUEUE)/IP(src='123.111.111.222',dst='34.34.34.34')/TCP(sport=3123,dport=34234)/b'123123123123')
    print(filter.received_pkts)
    filter.save()