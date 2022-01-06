'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    Retrieve and store states of Time Windows
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


class TimeWindowController:
    def __init__(self, file_path = None, alpha = 1, k = 10, T = 3, TW0_TB = 7, TW0_z = 1):
        if file_path:
            self.load(file_path)
        else:
            self.alpha = alpha
            self.k = k
            self.index_number_per_window = 2**self.k
            self.T = T
            self.TW0_TB = TW0_TB
            self.TW0_z = TW0_z
            self.total_duration = int((2**(alpha*T) - 1) / (2**alpha - 1) * 2**(TW0_TB + k))
            self.TW_result = []    # a linear data structure # {FID: hex, tts: , twid: ,}
            self.cofficient = self.calculate_coefficient(TW0_z, T)
            self.config = {'alpha': alpha, 'k': k, 'TW0_TB': TW0_TB, 'T': T, 'TW0_z': TW0_z, 'total_duration': self.total_duration}
            print('Time Window total duration is: {0} nanoseconds'.format(self.total_duration))
            self.TW_registers = [] # [[{FID: hex, tts:}]]
            for i in range(0, T):
                self.TW_registers.append([])

    def load(self, file_path):
        f = open(file_path, 'r')
        self.config = json.load(f)
        f.close()
        self.alpha = self.config['alpha']
        self.k = self.config['k']
        self.index_number_per_window = 2**self.k
        self.T = self.config['T']
        self.TW0_TB = self.config['TW0_TB']
        self.TW0_z = self.config['TW0_z']
        self.total_duration = self.config['total_duration']
        self.cofficient = self.calculate_coefficient(self.TW0_z, self.T)
        self.TW_result = self.config['TW_result']
        print('Time Window total duration is: {0} nanoseconds'.format(self.total_duration))

    def calculate_coefficient(self, z, t):
        coefficient = [1]
        co = 1
        for i in range(0, t-1):
            co *= (z - 0.5*z*z*z)
            coefficient.append(co)
            z = 2*z*z - z*z*z*z
        return coefficient

    def poll_register(self):
        pass

    def save_TW(self):
        if not self.TW_result:
            print('Time window is not polled or filtered!')
            return
        file_path = './settings/TW_{0}_{1}.json'.format(self.config['smallest_ts'], self.config['largest_ts'])
        self.config['TW_result'] = self.TW_result
        with open(file_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def filter_TW(self):
        TW0 = self.TW_registers[0]
        largest_tts = 0
        largest_idx = 0
        for j in range(0, self.index_number_per_window):
            if TW0[j]['tts'] > largest_tts:
                largest_tts = TW0[j]['tts']
                largest_idx = j
        latest_CID = largest_tts >> self.k
        for i in range(0, self.T):
            for j in range(0, largest_idx + 1):
                t_CID = self.TW_registers[i][j]['tts'] >> self.k
                if t_CID == latest_CID:
                    self.TW_result.append({'FID': self.TW_registers[i][j]['FID'],
                                           'tts': self.TW_registers[i][j]['tts'],
                                           'twid': i})
            for j in range(largest_idx + 1, self.index_number_per_window):
                t_CID = self.TW_registers[i][j]['tts'] >> self.k
                if t_CID + 1 == latest_CID:
                    self.TW_result.append({'FID': self.TW_registers[i][j]['FID'],
                                           'tts': self.TW_registers[i][j]['tts'],
                                           'twid': i})

            largest_tts = (largest_tts - 2**self.k) >> self.alpha # the tts of the replaced cell
            largest_idx = largest_tts & (2**self.k - 1)
            latest_CID = largest_tts >> self.k
        #retrieve smallest and largest ts
        self.TW_result = sorted(self.TW_result, key=lambda x: (x['twid'], x['tts']))
        self.config['smallest_ts'] = self.cell_duration(self.TW_result[0]['tts'], self.TW_result[0]['twid'])[0]
        self.config['largest_ts'] = self.cell_duration(self.TW_result[-1]['tts'], self.TW_result[-1]['twid'])[1]

    def cell_duration(self, tts, twid):
        TB = 2**(self.TW0_TB + twid * self.alpha)
        return [tts << TB, (tts << TB) + 2**TB - 1, (tts << TB) + 2**(TB - 1)]

    def retrieve(self, ts, te):
        if not self.TW_result:
            print('Time window is not polled or filtered!')
            return
        retrieve_result = {}
        retrieve_result['ts'] = ts
        retrieve_result['te'] = te
        retrieve_result['retrieve_start_ts'] = ts
        retrieve_result['retrieve_end_ts'] = te
        retrieve_result['smallest_ts'] = self.config['smallest_ts']
        retrieve_result['largest_ts'] = self.config['largest_ts']
        if ts < self.config['smallest_ts']:
            print('Time Windows start from {0}. Request retrieving from {1}. Retrieve from {0}...'.
                  format(self.config['smallest_ts'], ts))
            retrieve_result['retrieve_start_ts'] = self.config['smallest_ts']
        if te > self.config['largest_ts']:
            print('Time Windows end at {0}. Request retrieving to {1}. Retrieve to {0}...'.
                  format(self.config['largest_ts'], te))
            retrieve_result['retrieve_end_ts'] = self.config['largest_ts']
        agg = [] # [{FID: N},{FID: N}]
        for i in range(0,self.T):
            agg.append({})
        # retrieve packets within the interval
        for pkt in self.TW_result:
            re_ts = self.cell_duration(pkt['tts'], pkt['twid'])[2]
            if ts <= re_ts and re_ts <= te:
                agg[pkt['twid']][pkt['FID']] = agg[pkt['twid']].get(pkt['FID'], 0) + 1
        # get the estimated number of packets
        TW_result = {} # {FID: EN}
        for twi, agg_tw in enumerate(agg):
            for FID, N in agg_tw.items():
                TW_result[FID] = TW_result.get(FID, 0) + int(N / self.cofficient[twi])
        retrieve_result['TW_result'] = TW_result
        return retrieve_result

    def retrieve_and_save(self, ts, te):
        r = self.retrieve(ts,te)
        file_path = './settings/e_{0}_{1}.json'.format(r['retrieve_start_ts'], r['retrieve_end_ts'])
        with open(file_path, 'w') as f:
            json.dump(r, f, indent=4)


if __name__ == '__main__':
    tw_controller = TimeWindowController()
