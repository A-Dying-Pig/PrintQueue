'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    The analysis program for Queue Monitor of PrintQueue
Last Update Time:
    2022.4.19
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
import matplotlib.pyplot as plt
import numpy as np

from scapy.all import *
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP

ETHERTYPE_PRINTQUEUE = 0x080c
ETHERTYPE_IPV4 = 0x0800
IP_PROTOCOLS_TCP = 6

class QueueMonitor:
    def __init__(self, path, max_qdepth = 25000):
        """
        The class is created from QM raw data.
        The class can construct the queue stack, visualize queue stack
        :param path: the path to the parent folder of the QM data folder
        """
        self.max_qdepth = max_qdepth
        self.QM_registers = []
        self.QM_result = []
        self.QM_registers = self.poll_registers(path)
        self.QM_result = self.filter_QM()
        print('-----------------------------------------------------------------------------------')
        print('-----------------      Analysis Program for Queue Monitor    ----------------------')
        print('------------------------      Loaded from RAW data    -----------------------------')
        print('-----------------------------------------------------------------------------------')

    def poll_registers(self, path):
        """
        read and load register values
        Raw data are loaded in the ascending order of time, i.e., from the old one to the lastest
        :return: [{'ts': A_B_C, 'qm': [{'FID': hex_string, 'seq': integer, 'wrap': integer}]}]
        A_B is the file written time, C indicates whether seq num overflow, qm is the stack
        The elements of qm correspond to slots in the stack
        wrap is the overflow times of the seq number
        """
        # Raw binary files are named in the format A_B_C.bin,
        # where A is the time value of the seconds, B is the time value of the microseconds when the file is written
        # if C == 1, then the seq num overflows
        # first sort the files according to the written time
        ts = []
        root = None
        for (root, dirs, fs) in os.walk(path):
            for f in fs:
                ts.append(f.split('.')[0].split('_'))
        if not ts:
            print("Error! Path does not exist!")
            return
        ts = [[int(t[0]), int(t[1]), int(t[2])] for t in ts]
        ts = sorted(ts, key=lambda x: (x[0], x[1]))
        ts = [[str(t[0]), str(t[1]), str(t[2])] for t in ts]
        files = [os.path.join(root, '_'.join(t) + '.bin') for t in ts]
        ret = [] #
        wrap = 0
        for (i, f) in enumerate(files):
            print("Loading QM file: {0}".format(f))
            if ts[i][2] == '1':
                wrap += 1
            with open(f, 'rb') as fptr:
                current_qm = [] #[{'FID': hex_string, 'seq': integer, 'wrap': integer}]
                for j in range(self.max_qdepth):
                    current_qm.append({})
                order = 0
                num = 0
                chunk = fptr.read(4)
                while chunk:
                    if order == 0 or order == 1: #srcIP and dstIP
                        FID = bytes([chunk[3], chunk[2], chunk[1], chunk[0]]).hex()
                        current_qm[num]['FID'] = current_qm[num].get('FID', '') + FID
                    else:   # seq number
                        seq = int.from_bytes(chunk[0:4], 'little')
                        current_qm[num]['seq'] = seq
                        current_qm[num]['wrap'] = wrap
                    num += 1
                    if num == self.max_qdepth:
                        num = 0
                        order += 1
                    chunk = fptr.read(4)
            ret.append({'qm': current_qm, 'ts': ts[i]})
        return ret

    def filter_QM(self):
        """
        filter stale register values from QM data
        :return: [{'ts': A_B_C, 'qdepth': integer, 'QM_result': [{'index': integer, 'FID': hex_string}]}]
        """
        ret = []
        if not self.QM_registers:
            print('Error! Queue monitor has not polled register values!')
            return ret
        # pick the first QM as the base
        first_QM = self.QM_registers[0]['qm'] # [{'FID': hex_string, 'seq': integer, 'wrap': integer}]
        first_ret = []
        current_seq = -1
        for (i, slot) in enumerate(first_QM):
            if slot['FID'] != '0000000000000000' and slot['seq'] + (slot['wrap'] << 32) > current_seq:
                # valid slot, otherwise stale
                first_ret.append({'index': i, 'FID': slot['FID'], 'seq': slot['seq'] + (slot['wrap'] << 32)})
                current_seq = slot['seq'] + (slot['wrap'] << 32)
        if not first_ret:
            ret.append({'ts': self.QM_registers[0]['ts'], 'qdepth': 0, 'QM_result': []})
        else:
            ret.append({'ts': self.QM_registers[0]['ts'], 'qdepth': first_ret[-1]['index'], 'QM_result': first_ret})
        # get the current QM from the previous QM
        for i in range(1, len(self.QM_registers)):
            current_QM = self.QM_registers[i]['qm']
            prev_ret = ret[i - 1]['QM_result']
            current_ret = []
            j = 0
            larger_one_found = False
            # check whether all the registers are empty
            all_empty = True
            for z in range(0, len(current_QM)):
                if current_QM[z]['FID'] != '0000000000000000':
                    all_empty = False
                    break
            if all_empty:
                ret.append({'ts': self.QM_registers[i]['ts'], 'qdepth': 0, 'QM_result': []})
                continue
            # check whether there is an later packet in the previous stack
            for item in prev_ret:
                while j <= item['index']:
                    if current_QM[j]['FID'] != '0000000000000000' and current_QM[j]['seq'] + (current_QM[j]['wrap'] << 32) > current_seq:
                        current_seq = current_QM[j]['seq'] + (current_QM[j]['wrap'] << 32)
                        current_ret.append({'index': j, 'FID': current_QM[j]['FID'], 'seq': current_seq})
                        j += 1
                        larger_one_found = True
                        break
                    j += 1
                if larger_one_found:
                    break
                else:
                    current_ret.append(item)
            # so far, indexes from 0 to j are verified. From index j to the last slot, check slot updates.
            for z in range(j, len(current_QM)):
                if current_QM[z]['FID'] != '0000000000000000' and current_QM[z]['seq'] + (current_QM[z]['wrap'] << 32) > current_seq:
                    current_seq = current_QM[z]['seq'] + (current_QM[z]['wrap'] << 32)
                    current_ret.append({'index': z, 'FID': current_QM[z]['FID'], 'seq': current_seq})
            if not current_ret:
                ret.append({'ts': self.QM_registers[i]['ts'], 'qdepth': 0, 'QM_result': []})
            else:
                ret.append({'ts': self.QM_registers[i]['ts'], 'qdepth': current_ret[-1]['index'], 'QM_result': current_ret})
        return ret


if __name__ == '__main__':
    qm = QueueMonitor(path='./d/qm/0/qm_data')
