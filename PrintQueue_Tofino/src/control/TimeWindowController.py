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
import matplotlib.pyplot as plt
import numpy as np
import crcmod

# from ground_truth import *


from scapy.all import *
from scapy.layers.l2 import Ether
from scapy.layers.inet import IP, TCP

ETHERTYPE_PRINTQUEUE = 0x080c
ETHERTYPE_IPV4 = 0x0800
IP_PROTOCOLS_TCP = 6
num_pipes = 2

class TimeWindowController:
    def __init__(self, path, alpha = 1, k = 10, T = 3, TW0_TB = 7, TW0_z = 1, save_file_path = None, load_file_path = None):
        if load_file_path:
            self.load(load_file_path)
        else:
            self.alpha = alpha
            self.k = k
            self.index_number_per_window = 2**self.k
            self.T = T
            self.TW0_TB = TW0_TB
            self.TW0_z = TW0_z
            self.total_duration = int((2**(alpha*T) - 1) / (2**alpha - 1) * 2**(TW0_TB + k))
            self.TW_result = []    # a linear data structure # {FID: hex, tts: , twid: ,}
            # self.cofficient = self.calculate_coefficient(TW0_z, T)
            # print(self.calculate_coefficient(TW0_z, T))
            self.cofficient = self.calculate_coefficient2(TW0_z, alpha,T)
            self.config = {'alpha': alpha, 'k': k, 'TW0_TB': TW0_TB, 'T': T, 'TW0_z': TW0_z, 'total_duration': self.total_duration}
            print('Time Window total duration is: {0} nanoseconds, cofficient: {1}'.format(self.total_duration, self.cofficient))
            self.TW_registers = self.poll_register(path) #  [{ts: , tw:[[{FID: hex, tts:}]] }]
            self.filter_TW()
            # self.retrieve(self.config['smallest_ts'], self.config['largest_ts'])
            # self.save_TW(save_file_path)

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
        # self.save_TW()

    def calculate_coefficient(self, z, t):
        coefficient = [1]
        co = 1
        for i in range(0, t-1):
            co *= (z - 0.5*z*z*z)
            coefficient.append(co)
            z = 2*z*z - z*z*z*z
        return coefficient

    def calculate_coefficient2(self, z, alpha, t):
        coefficient = [1]
        co = 1
        p = 1 - z*z
        for i in range(0, t-1):
            map = 2**alpha
            temp = z * (1 - p**map) / (1-p) / map
            co *= temp
            coefficient.append(co)
            z = 1 - p**map
        return coefficient

    def poll_register(self, path):
        ts = []
        for (root, dirs, fs) in os.walk(path):
            for f in fs:
                ts.append(f.split('.')[0].split('_'))
        ts = [[int(t[0]), int(t[1])] for t in ts]
        ts = sorted(ts, key= lambda x: (x[0], x[1]))
        ts = [[str(t[0]), str(t[1])] for t in ts]
        files = [os.path.join(root, '_'.join(t) + '.bin') for t in ts]

        ret = [] # [{ts, tw: }]
        for (i,f) in enumerate(files):
            print("loading tw file: {0}".format(f))
            with open(f, 'rb') as fptr:
                current_tw = []
                zero_num = 0
                for TWid in range(0, self.T):
                    current_tw.append([])
                    for j in range(0, self.index_number_per_window):
                        current_tw[TWid].append({})
                TWid = 0
                num = 0
                order = 0
                chunk = fptr.read(4)
                while chunk:
                    if order == 0: # tts
                        tts = int.from_bytes(chunk[0:4], 'little')
                        current_tw[TWid][num]['tts'] = tts
                    else:
                        FID = bytes([chunk[3], chunk[2], chunk[1], chunk[0]]).hex()
                        current_tw[TWid][num]['FID'] = current_tw[TWid][num].get('FID', '') + FID
                        if current_tw[TWid][num]['FID'] == '0000000000000000':
                            zero_num += 1
                    num += 1
                    if num == self.index_number_per_window:
                        num = 0
                        if order == 2:
                            order = 0
                            TWid += 1
                        else:
                            order += 1
                    chunk = fptr.read(4)
            if zero_num != self.index_number_per_window * self.T:
                ret.append({'tw': current_tw, 'ts': ts[i]})


        return ret


    def save_TW(self, save_file_path):
        if not self.TW_result:
            print('Time window is not polled or filtered!')
            return
        print("saving Time Window...")
        file_name = 'TW_{0}_{1}.json'.format(self.config['smallest_ts'], self.config['largest_ts'])
        file_path = os.path.join(save_file_path, file_name)
        self.config['TW_result'] = self.TW_result
        with open(file_path, 'w') as f:
            json.dump(self.config, f, indent=4)


    def filter_TW(self):
        wrapping = 0
        for tw in self.TW_registers:
            registers = tw['tw']
            TW0 = registers[0]
            largest_tts = TW0[0]['tts']
            largest_idx = 0
            tts_bit = 32 - self.TW0_TB
            CID_bit = tts_bit - self.k
            threshold_bit = int((tts_bit + self.k)/2)
            for j in range(0, self.index_number_per_window):
                if TW0[j]['tts'] > largest_tts:
                    if (1 << tts_bit) + largest_tts - TW0[j]['tts'] > (1 << threshold_bit):
                        # not wrapping
                        largest_tts = TW0[j]['tts']
                        largest_idx = j
                else:
                    if (1 << tts_bit) + TW0[j]['tts'] - largest_tts < (1 << threshold_bit):
                        largest_tts = TW0[j]['tts']
                        largest_idx = j
                        wrapping += 1

            largest_cell = TW0[largest_idx]
            largest_cell['wrap'] = wrapping
            largest_cell['twid'] = 0

            latest_CID = largest_tts >> self.k
            count = [] # number of filtered packets in different TW
            TW_result = []
            for i in range(0, self.T):
                count.append(0)
                first_pre_cycle = 0
                for j in range(0, largest_idx + 1):
                    if registers[i][j]['FID'] == '0000000000000000':
                        continue
                    t_CID = registers[i][j]['tts'] >> self.k
                    t_idx = registers[i][j]['tts'] & (2**self.k - 1)
                    if t_CID == latest_CID:
                        count[i] += 1
                        temp = {'FID': registers[i][j]['FID'],
                                'tts': registers[i][j]['tts'],
                                'twid': i,
                                'wrap': wrapping}
                        TW_result.append(temp)
                        if first_pre_cycle == 0:
                            first_pre_cycle = 1
                            smallest_cell = temp
                first_pre_cycle = 0
                for j in range(largest_idx + 1, self.index_number_per_window):
                    if registers[i][j]['FID'] == '0000000000000000':
                        continue
                    t_CID = registers[i][j]['tts'] >> self.k
                    t_idx = registers[i][j]['tts'] & (2**self.k - 1)
                    if (t_CID + 1) & ((1 << CID_bit) - 1) == latest_CID & ((1 << CID_bit) - 1):
                        count[i] += 1
                        temp = {'FID': registers[i][j]['FID'],
                                'tts': registers[i][j]['tts'],
                                'twid': i}
                        if t_CID > latest_CID:
                            temp['wrap'] = wrapping - 1
                        else:
                            temp['wrap'] = wrapping
                        TW_result.append(temp)
                        if first_pre_cycle == 0:
                            first_pre_cycle = 1
                            smallest_cell = temp

                CID_bit -= self.alpha
                largest_tts = (largest_tts - 2**self.k) >> self.alpha # the tts of the replaced cell
                largest_idx = largest_tts & (2**self.k - 1)
                latest_CID = largest_tts >> self.k
            #retrieve smallest and largest ts
            print('smallest ts: {0}, largest ts: {1}, count: {2}'.format(smallest_cell, largest_cell, count))
            tw['TW_result'] = TW_result
            tw['largest_cell'] = largest_cell
            tw['smallest_cell'] = smallest_cell
            tw['lts'] = self.cell_duration(largest_cell['tts'], largest_cell['twid'])[2] + (1 << 32) * largest_cell['wrap']
            tw['sts'] = self.cell_duration(smallest_cell['tts'], smallest_cell['twid'])[2] + (1 << 32) * smallest_cell['wrap']
            # ret = self.retrieve2(tw['sts'], tw['lts'], TW_result)
            # self.draw_top(tw['sts'], tw['lts'],ret)

    def cell_duration(self, tts, twid):
        TB = self.TW0_TB + twid * self.alpha
        return [tts << TB, (tts << TB) + 2**TB - 1, (tts << TB) + 2**(TB - 1)]

    def TW_start_end_timestamp(self, TWid):
        if not self.TW_result:
            print('Time window is not polled or filtered!')
            return
        ts = 0
        te = 0
        first = 1
        for c in self.TW_result:
            if c['twid'] != TWid:
                continue
            if first == 1:
                ts = c['tts']
                te = c['tts']
                first = 0
                continue
            if c['tts'] > te:
                te = c['tts']
            if c['tts'] < ts:
                ts = c['tts']
        return self.cell_duration(ts, TWid)[2], self.cell_duration(te, TWid)[2]

    def retrieve(self, ts, te):
        TW = None
        for tw in self.TW_registers:
            if ts >= tw['sts'] and te <= tw['lts']:
                TW = tw
                break
        if not TW:
            print("No Time Window Found!")
            return [], 0, 0
        agg = [] # [{FID: N},{FID: N}]
        for i in range(0,self.T):
            agg.append({})
        # retrieve packets within the interval
        for pkt in TW['TW_result']:
            re_ts = self.cell_duration(pkt['tts'], pkt['twid'])[2] + pkt['wrap'] * (1<<32)
            if ts <= re_ts and re_ts <= te:
                agg[pkt['twid']][pkt['FID']] = agg[pkt['twid']].get(pkt['FID'], 0) + 1
        # get the estimated number of packets
        result = {} # {FID: EN}
        for twi, agg_tw in enumerate(agg):
            for FID, N in agg_tw.items():
                result[FID] = result.get(FID, 0) + int(N / self.cofficient[twi])
        result = dict(sorted(result.items(), key=lambda item: item[1], reverse= True))
        return result, tw['sts'], tw['lts']


    def retrieve2(self, ts, te, TW_result):
        agg = [] # [{FID: N},{FID: N}]
        for i in range(0,self.T):
            agg.append({})
        # retrieve packets within the interval
        for pkt in TW_result:
            re_ts = self.cell_duration(pkt['tts'], pkt['twid'])[2] + pkt['wrap'] * (1<<32)
            if ts <= re_ts and re_ts <= te:
                agg[pkt['twid']][pkt['FID']] = agg[pkt['twid']].get(pkt['FID'], 0) + 1
        # get the estimated number of packets
        result = {} # {FID: EN}
        for twi, agg_tw in enumerate(agg):
            for FID, N in agg_tw.items():
                result[FID] = result.get(FID, 0) + int(N / self.cofficient[twi])
        result = dict(sorted(result.items(), key=lambda item: item[1], reverse= True))
        # self.draw_top(ts, te, TW_result)
        return result


    def draw_top(self, ts, te, ret, K = 10):
        K = min(K, len(ret))
        ret = list(ret.items())[0 : K]
        print("plotting TW result top {0} flows from {1} to {2}".format(K, ts, te))
        flow_ids = []
        pkt_num = []
        for (key,val) in ret:
            flow_ids.append(key)
            pkt_num.append(val)
        plt.bar(flow_ids, pkt_num)
        plt.xlabel('flow ID')
        plt.ylabel('packet number')
        bar_title = "TW result top {0} flows from {1} to {2}".format(K, ts, te)
        plt.title(bar_title)
        plt.xticks(rotation=-15)
        plt.tight_layout()
        plt.savefig( os.path.join('fig', bar_title + '.png'))
        plt.close()


    def retrieve_and_save(self, ts, te):
        r = self.retrieve(ts,te)
        file_path = './settings/e_{0}_{1}.json'.format(r['retrieve_start_ts'], r['retrieve_end_ts'])
        with open(file_path, 'w') as f:
            json.dump(r, f, indent=4)


def precision_and_recall_packet_number(gt, tw):
    precision_total = 0
    precision_hit = 0
    tw_filter = dict(list(tw.items())[0:-1])
    gt_filter = dict(list(gt.items())[0:-1])
    for FID, en in tw_filter.items():
        precision_total += en
        if FID in gt_filter:
            precision_hit += min(en, gt_filter[FID])
    recall_total = 0
    recall_hit = 0

    for FID, n in gt_filter.items():
        recall_total += n

    return [precision_hit / precision_total, precision_hit / recall_total]


def precision_and_recall(gt, tw):
    precision_total = 0
    precision_hit = 0
    tw_filter = dict(list(tw.items())[0:100])
    gt_filter = dict(list(gt.items())[0:100])

    for FID, en in tw_filter.items():
        precision_total += 1
        if FID in gt_filter:
            precision_hit += 1
    # filter out some packets
    recall_total = 0
    for FID, n in gt_filter.items():
        recall_total += 1
    return [precision_hit / precision_total, precision_hit / recall_total]


class HashFunction:
    def __init__(self):
        self.h = []
        crc16 = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0x0000, xorOut=0x0000)
        self.h.append(crc16)
        crc16_usb = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0x0000, xorOut=0xFFFF)
        self.h.append(crc16_usb)
        crc16_genibus = crcmod.mkCrcFun(0x11021, rev=False, initCrc=0x0000, xorOut=0xFFFF)
        self.h.append(crc16_genibus)
        crc16_buypass = crcmod.mkCrcFun(0x18005, rev=False, initCrc=0x0000, xorOut=0x0000)
        self.h.append(crc16_buypass)
        crc16_dect = crcmod.mkCrcFun(0x10589, rev=False, initCrc=0x0001, xorOut=0x0001)
        self.h.append(crc16_dect)
        crc16_dnp = crcmod.mkCrcFun(0x13d65, rev=True, initCrc=0xffff, xorOut=0xffff)
        self.h.append(crc16_dnp)
        crc16_maxim = crcmod.mkCrcFun(0x18005, rev=True, initCrc=0xffff, xorOut=0xffff)
        self.h.append(crc16_maxim)
        crc16_dds_110 = crcmod.mkCrcFun(0x18005, rev=False, initCrc=0x800d, xorOut=0x0000)
        self.h.append(crc16_dds_110)


def Count_Min(hash, gt, filter, Row = 3,  Col = 1024):

    Col_Mask = Col - 1
    tables = np.zeros((Row, Col))
    # run
    for (FID, n) in gt.items():
        FID_bytes = bytearray.fromhex(FID)
        for i in range(0, Row):
            idx = hash.h[i](FID_bytes) & Col_Mask
            tables[i, idx] += n
    # Query
    ret = {}
    for (FID, n) in filter.items():
        FID_bytes = bytearray.fromhex(FID)
        smallest = 0
        for i in range(0, Row):
            idx = hash.h[i](FID_bytes) & Col_Mask
            if i == 0:
                smallest = tables[i, idx]
                continue
            if tables[i, idx] < smallest:
                smallest = tables[i, idx]
        ret[FID] = smallest
    ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
    return ret

def Flow_Radar(hash, gt, cell_number = 4096*5):
    hash_number = 3
    bit_array = []
    tables = []
    for i in range(0, cell_number):
        bit_array.append(0)
        tmp = {}
        tmp['fn'] = 0
        tmp['pn'] = 0
        tmp['FIDXOR'] = 0x0000000000000000
        tables.append(tmp)
    for (FID, n) in gt.items():
        pos = []
        FID_bytes = bytearray.fromhex(FID)
        for i in range(0, hash_number):
            idx = hash.h[i](FID_bytes) % cell_number
            pos.append(idx)
        sum = 0
        for j in pos:
            sum += bit_array[j]
            bit_array[j] = 1
        if sum == hash_number: # old flow
            for j in pos:
                tables[j]['pn'] += n
        else: # new flow
            for j in pos:
                tables[j]['fn'] += 1
                tables[j]['pn'] += n
                tables[j]['FIDXOR'] ^= int(FID, 16)
    # retrieve
    ret = {}
    while True:
        new_one = False
        for i in range(0, cell_number):
            if tables[i]['fn'] == 1:
                FID_int = tables[i]['FIDXOR']
                FID = "{0:0{1}x}".format(FID_int, 16)
                FID_bytes = bytearray.fromhex(FID)
                ret[FID] = tables[i]['pn']
                new_one = True
                for j in range(0, hash_number):
                    idx = hash.h[j](FID_bytes) % cell_number
                    tables[idx]['fn'] -= 1
                    tables[idx]['pn'] -= tables[i]['pn']
                    tables[idx]['FIDXOR'] ^= FID_int
        if new_one == False:
            break
    ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
    return ret


def hash_pipe(hash, traces, stages = 5,  cell_number = 1024):
    tables = []
    for i in range(0, stages):
        tables.append([])
        for j in range(0, cell_number):
            tables[i].append({'FID': None, 'n': 0})
    # go through hash pipe
    for pkt in traces:
        FID_bytes = bytearray.fromhex(pkt)
        idx = hash.h[0](FID_bytes) % cell_number
        if tables[0][idx]['FID'] == None:
            tables[0][idx]['FID'] = pkt
            tables[0][idx]['n'] = 1
            continue
        elif tables[0][idx]['FID'] == pkt:
            tables[0][idx]['n'] += 1
            continue
        swap_FID = tables[0][idx]['FID']
        swap_n = tables[0][idx]['n']
        tables[0][idx]['FID'] = pkt
        tables[0][idx]['n'] = 1

        for i in range(1, stages):
            FID_bytes = bytearray.fromhex(swap_FID)
            idx = hash.h[i](FID_bytes) % cell_number
            if tables[i][idx]['FID'] == swap_FID:
                tables[i][idx]['n'] += swap_n
                break
            elif tables[i][idx]['FID'] == None:
                tables[i][idx]['FID'] = swap_FID
                tables[i][idx]['n'] = swap_n
                break
            if tables[i][idx]['n'] < swap_n:
                temp_FID = tables[i][idx]['FID']
                temp_n = tables[i][idx]['n']
                tables[i][idx]['FID'] = swap_FID
                tables[i][idx]['n'] = swap_n
                swap_FID = temp_FID
                swap_n = temp_n

    # retrieve
    ret = {}
    for i in range(0, stages):
        for j in range(0, cell_number):
            if tables[i][j]['FID'] != None:
                ret[tables[i][j]['FID']] = ret.get(tables[i][j]['FID'], 0) + tables[i][j]['n']
    ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
    return ret



if __name__ == '__main__':
    ret_dir = './univ1_pt12_10Gbps_1_12_5'
    TW_dir = os.path.join(ret_dir, 'TW')
    for (root, dir, file) in os.walk(TW_dir):
        json_file = file[0]
    json_path = os.path.join(TW_dir, json_file)

    tw = TimeWindowController(path=json_path, alpha = 1, k = 12, T = 5, TW0_TB = 6, TW0_z = 64/105)
    gt = GroundTruth(ret_dir)
    whole_gt = gt.top(tw.config['smallest_ts'], tw.config['largest_ts'])
    # gt.draw_top(tw.config['smallest_ts'], tw.config['largest_ts'])
    whole_tw = tw.retrieve(tw.config['smallest_ts'], tw.config['largest_ts'])
    Wfp, Wfr = precision_and_recall(whole_gt, whole_tw['TW_result'])
    Wnp, Wnr = precision_and_recall_packet_number(whole_gt, whole_tw['TW_result'])
    print("Whole Time window, Flow Precision: {0}, Flow Recall: {1}".format(Wfp, Wfr))
    print("Whole Time Window, Number Precision: {0}, Number Recall: {1}".format(Wnp, Wnr))
    # Each time windows precision & recall
    for i in range(0, tw.T):
        print('time window: {0}'.format(i))
        ts, te = tw.TW_start_end_timestamp(i)
        TW_gt = gt.top(ts, te)
        TW_tw = tw.retrieve(ts, te)
        fp, fr = precision_and_recall(TW_gt, TW_tw['TW_result'])
        np, nr = precision_and_recall_packet_number(TW_gt, TW_tw['TW_result'])
        print("Time window: {0}, Flow Precision: {1}, Flow Recall: {2}".format(i, fp, fr))
        print("Time window: {0}, Number Precision: {1}, Number Recall: {2}".format(i, np, nr))

    # hash_list = HashFunction()
    # top_100_gt = dict(list(whole_gt.items())[0:100])
    # ret = Count_Min(hash_list, whole_gt, top_100_gt, 3,  1024)
    # CM_p, CM_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("Count-Min Sketch: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(CM_p, CM_r))
    #
    # top_100_gt = dict(list(whole_gt.items())[0:100])
    # ret = Count_Min(hash_list, whole_gt, top_100_gt, 5,  4096)
    # CM_p, CM_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("Count-Min Sketch: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(CM_p, CM_r))
    #
    # ret = Flow_Radar(hash_list,whole_gt,1024*3)
    # FR_p, FR_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("FlowRadar: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(FR_p, FR_r))
    #
    # ret = Flow_Radar(hash_list,whole_gt, 4096*5)
    # FR_p, FR_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("FlowRadar: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(FR_p, FR_r))
    #
    # traces = gt.traces(tw.config['smallest_ts'], tw.config['largest_ts'])
    # ret = hash_pipe(hash_list, traces, 2, 512)
    # HP_p, HP_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("HashPipe: 512 x 2, Number Precision: {0}, Number Recall: {1}".format(HP_p, HP_r))
    #
    # ret = hash_pipe(hash_list, traces, 5, 4096)
    # HP_p, HP_r = precision_and_recall_packet_number(whole_gt, ret)
    # print("HashPipe: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(HP_p, HP_r))