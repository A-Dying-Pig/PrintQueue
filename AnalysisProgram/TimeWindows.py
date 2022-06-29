'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    1) The Analysis Program for Time Windows of PrintQueue.
    2) The simulation of related works: Count-Min Sketch, HashPipe, FlowRadar
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
import crcmod

from scapy.all import *


class TimeWindowController:
    def __init__(self, path, alpha=1, k=10, T=3, TW0_TB=7, TW0_z=1, save_file_path=None, load_file_path=None):
        """
        The class is 1) created from the TW raw data or 2) loaded from the stored TW class.
        The class can filter stale data, execute queries, and visualize heaviest flows
        :param path: the path to the parent folder of the TW data folder
        :param alpha: the compression factor, in accord with the alpha value of the data plane
        :param k: the index number, in accord with the k value of the data plane
        :param T: the number of time windows, in accord with the T value of the data plane
        :param TW0_TB: the trimmed bits of the first TW, in accord with the value of the data plane
        :param TW0_z: the probability that a cell in the first TW stores an incoming packet every cycle
        :param save_file_path: the path to store the processed TW class in a json file
        :param load_file_path: the path to load a json that is the stored TW class
        """
        if load_file_path:
            self.load(load_file_path)
        else:
            self.alpha = alpha
            self.k = k
            self.index_number_per_window = 2 ** self.k
            self.T = T
            self.TW0_TB = TW0_TB
            self.TW0_z = TW0_z
            self.total_duration = int((2 ** (alpha * T) - 1) / (2 ** alpha - 1) * 2 ** (TW0_TB + k))  # the set period
            self.cofficient = self.calculate_coefficient(TW0_z, alpha, T)
            # self.config stores the metadata of the TW class
            self.config = {'alpha': alpha, 'k': k, 'TW0_TB': TW0_TB, 'T': T, 'TW0_z': TW0_z,
                           'total_duration': self.total_duration}
            # self.TW_registers stores the raw TW data, filtered data, and oldest/latest cells of the set
            self.TW_registers, self.tw_raw_files = self.poll_register(os.path.join(path, 'tw_data'))
            self.filter_TW()
            print('-----------------------------------------------------------------------------------')
            print('-----------------       Analysis Program for Time Windows    ----------------------')
            print('------------------------       Loaded from RAW data    ----------------------------')
            print('-----------------------------------------------------------------------------------')
            print('Alpha:{0}, k:{1}, T:{2}\nSet period: {3} nanoseconds\nCofficients: {4}'.format(self.alpha, self.k,
                                                                                                  self.T,
                                                                                                  self.total_duration,
                                                                                                  self.cofficient))
            # load signals
            self.signals = self.poll_signals(os.path.join(path, 'signal_data'))
            print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            print('+++++++++++++++++++++       Load Data Plane Signals    ++++++++++++++++++++++++++++')
            print('+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
            print('Signal Number: {0}'.format(len(self.signals)))

    def poll_signals(self, path):
        """
        read signal packets from raw data
        :return: [{'type': int, 'enqueue_ts': int, 'dequeue_ts': int}]
        """
        # Raw binary files are named in the format A_B.bin,
        # where A is the time value of the seconds, B is the time value of the microseconds when the file is written
        # first sort the files according to the written time
        ret = []
        for (root, dirs, fs) in os.walk(path):
            for (i, f) in enumerate(fs):
                print("Loading SIGNAL file: {0}".format(f))
                tw_idx = 0
                file_name = f.split('.')[0].split('_')
                for (i, tws) in enumerate(self.TW_registers):
                    if tws['ts'] == file_name:
                        tw_idx = i
                        break
                CLOSE_THRESHOLD = 5
                with open(os.path.join(root, f), 'rb') as fptr:
                    chunk = fptr.read(12)
                    if chunk:
                        # storage format: [type | enqueue_ts | dequeue_ts ][type | enqueue_ts | dequeue_ts ]
                        type = int.from_bytes(chunk[0:4], 'little')
                        enqueue_ts = int.from_bytes(chunk[4:8], 'little')
                        dequeue_ts = int.from_bytes(chunk[8:12], 'little')
                        # find wrap id
                        found_near_one = False
                        for cell in self.TW_registers[tw_idx]['TW_result']:
                            tb = self.TW0_TB + self.alpha * cell['twid']
                            if ((dequeue_ts >> tb) - cell['tts'] < CLOSE_THRESHOLD) and ((dequeue_ts >> tb) - cell['tts'] > -CLOSE_THRESHOLD):
                                dequeue_wrap = cell['wrap']
                                if enqueue_ts < dequeue_ts:
                                    enqueue_wrap = dequeue_wrap
                                else:
                                    enqueue_wrap = dequeue_wrap - 1
                                ret.append({'type': type, 'enqueue_ts': enqueue_ts + enqueue_wrap * (2**32), 'dequeue_ts': dequeue_ts + dequeue_wrap * (2**32)})
                                found_near_one = True
                                break
                        if not found_near_one and tw_idx > 0:
                            for cell in self.TW_registers[tw_idx - 1]['TW_result']:
                                tb = self.TW0_TB + self.alpha * cell['twid']
                                if ((dequeue_ts >> tb) - cell['tts'] < CLOSE_THRESHOLD) and (
                                        (dequeue_ts >> tb) - cell['tts'] > -CLOSE_THRESHOLD):
                                    dequeue_wrap = cell['wrap']
                                    if enqueue_ts < dequeue_ts:
                                        enqueue_wrap = dequeue_wrap
                                    else:
                                        enqueue_wrap = dequeue_wrap - 1
                                    ret.append({'type': type, 'enqueue_ts': enqueue_ts + enqueue_wrap * (2 ** 32),
                                                'dequeue_ts': dequeue_ts + dequeue_wrap * (2 ** 32)})
                                    found_near_one = True
                                    break
        return ret

    def load(self, file_path):
        """
        load TW class from json file
        :param file_path: the path to store TW class
        """
        f = open(file_path, 'r')
        self.config = json.load(f)
        f.close()
        self.alpha = self.config['alpha']
        self.k = self.config['k']
        self.index_number_per_window = 2 ** self.k
        self.T = self.config['T']
        self.TW0_TB = self.config['TW0_TB']
        self.TW0_z = self.config['TW0_z']
        self.total_duration = self.config['total_duration']
        self.cofficient = self.calculate_coefficient(self.TW0_z, self.alpha, self.T)
        self.TW_registers = self.config['TW_registers']
        print('-----------------------------------------------------------------------------------')
        print('-----------------       Analysis Program for Time Windows    ----------------------')
        print('------------------------      Loaded from json file   -----------------------------')
        print('-----------------------------------------------------------------------------------')
        print(
            'Alpha:{0}, k:{1}, T:{2}\nSet period: {3} nanoseconds\nCofficients: {4}'.format(self.alpha, self.k, self.T,
                                                                                            self.total_duration,
                                                                                            self.cofficient))

    def calculate_coefficient(self, z, alpha, t):
        """
        :param z: cell probability
        :param alpha: compression factor
        :param t: the number of TW
        :return: [coefficient(0), coefficient(1), ..., coefficient(t-1)]
        """
        coefficient = [1]
        co = 1
        for i in range(0, t - 1):
            p = 1 - z * z
            map = 2 ** alpha
            temp = z * (1 - p ** map) / (1 - p) / map
            co *= temp
            coefficient.append(co)
            z = 1 - p ** map
        return coefficient

    def poll_register(self, path):
        """
        read and load register values
        Raw data are loaded in the ascending order of time, i.e., from the old one to the lastest
        :return: [{'ts': A_B, 'tw': [[{'tts': integer, 'FID': hex_string}]}], [sorted file name]
        each element of the return result is a file = a set of TWs
        A_B: file written time,
        tw: T dictionaries with each 2^k cells
        each element of tw is a single time window, whose cells are represented in an array
        """
        # Raw binary files are named in the format A_B.bin,
        # where A is the time value of the seconds, B is the time value of the microseconds when the file is written
        # first sort the files according to the written time
        ts = []
        root = None
        for (root, dirs, fs) in os.walk(path):
            for f in fs:
                ts.append(f.split('.')[0].split('_'))
        if not ts:
            print("Error! Path does not exist!")
            return
        ts = [[int(t[0]), int(t[1])] for t in ts]
        ts = sorted(ts, key=lambda x: (x[0], x[1]))
        ts = [[str(t[0]), str(t[1])] for t in ts]
        file_names = ['_'.join(t) + '.bin' for t in ts]
        files = [os.path.join(root, '_'.join(t) + '.bin') for t in ts]
        # read register value
        ret = []
        for (i, f) in enumerate(files):
            print("Loading TW file: {0}".format(f))
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
                # storage format: [ 2^k tts ][ 2^k srcIP ][ 2^k dstIP ] [ 2^k tts ][ 2^k srcIP ][ 2^k dstIP ]
                while chunk:
                    if order == 0:  # tts
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
            if zero_num != self.index_number_per_window * self.T:  # remove the TWs when all the registers are 0
                ret.append({'tw': current_tw, 'ts': ts[i]})
        return ret, file_names

    def save_TW(self, save_file_path):
        """
        save sets of TWs into a json file
        """
        if not self.TW_registers[0]['TW_result']:
            print('Time window is not filtered!')
            return
        print("saving Time Window...")
        file_name = 'TW_{0}_{1}_{2}.json'.format(self.alpha, self.k, self.T)
        file_path = os.path.join(save_file_path, file_name)
        for i in range(len(self.TW_registers)):
            del self.TW_registers[i]['tw']
        self.config['TW_registers'] = self.TW_registers
        with open(file_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def filter_TW(self):
        """
        filter stale register values from TW raw data
        modify self.TW_registers= [{'ts': A_B, 'tw': [[{'tts': integer, 'FID': hex_string}]],
                                    'TW_result': [cell_representation],
                                    'largest_cell': cell representation,
                                    'smallest_cell': cell representation,
                                    'sts': integer, 'lts': integer}]
        each element of self.TW_registers represents a file = a set of TWs
            'sts': smallest timestamp of the set
            'lts': largest timestamp of the set
            'largest_cell': largest cell of the set
            'smallest_cell': smallest cell of the set
            cell_representation = {'tts': integer, 'FID': hex_string, 'wrap': integer, 'twid': integer}
            'tts': trimmed timestamp of the cell
            'FID': flow ID in hex string
            'wrap': the number of timestamp overflows
            'twid': the index of time windows
        """
        wrapping = 0
        pre_largest_tts = 0
        for (tw_idx, tw) in enumerate(self.TW_registers):
            # Wrapping is to tackle situation where dequeue timestamp overflows.
            # In the unit of nanoseconds, 32 bits overflows approximately every 4 seconds
            # if a tts suddenly becomes large/small (near 2^32 or 0), there must be an overflow
            wrapping_once = False
            registers = tw['tw']
            TW0 = registers[0]
            largest_tts = TW0[0]['tts']
            largest_idx = 0
            tts_bit = 32 - self.TW0_TB
            CID_bit = tts_bit - self.k
            threshold_bit = int(
                (tts_bit + self.k) / 2)  # use a threshold to judge whether it is a burst increase/decrease
            # find largest tts in the first time window, which is also the largest tts of the set
            for j in range(0, self.index_number_per_window):
                if TW0[j]['tts'] > largest_tts:
                    if (1 << tts_bit) + largest_tts - TW0[j]['tts'] > (1 << threshold_bit):
                        # non overflow, find a larger tts
                        largest_tts = TW0[j]['tts']
                        largest_idx = j
                    # otherwise, the current tts is sometime before the largest tts when overflow happens. The
                    # current tts is actually older
                else:
                    if (1 << tts_bit) + TW0[j]['tts'] - largest_tts < (1 << threshold_bit):
                        # the current tts grows to overflow, when its value smaller, but the time represented later
                        largest_tts = TW0[j]['tts']
                        largest_idx = j
                        wrapping += 1  # wrapping means the times of overflow compared with the very beginning time
                        wrapping_once = True

            if not wrapping_once:
                if (1 << tts_bit) + largest_tts - pre_largest_tts < (1 << threshold_bit):
                    # overflow happens across sets
                    wrapping_once = True
                    wrapping += 1
                elif largest_tts < pre_largest_tts:
                    print(
                        'The largest tts across sets is not increasing, because limited traffic flows through switch '
                        'and registers are not updated.')
            pre_largest_tts = largest_tts
            # finally get the cell has the largest tts of every set
            largest_cell = TW0[largest_idx]
            largest_cell['wrap'] = wrapping
            largest_cell['twid'] = 0
            latest_CID = largest_tts >> self.k
            count = []  # Number of filtered packets in different TWs
            TW_result = []
            for i in range(0, self.T):
                count.append(0)
                first_pre_cycle = 0
                for j in range(0, largest_idx + 1):
                    # From index 0 cell to the latest cell, they should be in the same cycle with the latest cell
                    if registers[i][j]['FID'] == '0000000000000000':
                        continue
                    t_CID = registers[i][j]['tts'] >> self.k
                    t_idx = registers[i][j]['tts'] & (2 ** self.k - 1)
                    if t_CID == latest_CID:
                        count[i] += 1
                        temp = {'FID': registers[i][j]['FID'],
                                'tts': registers[i][j]['tts'],
                                'twid': i,
                                'wrap': wrapping}
                        # wrap is the time of overflows, when calculate real time, add wrap x 2^32 nanoseconds
                        TW_result.append(temp)
                        if first_pre_cycle == 0:
                            # find the oldest cell
                            first_pre_cycle = 1
                            smallest_cell = temp
                first_pre_cycle = 0
                for j in range(largest_idx + 1, self.index_number_per_window):
                    # From the latest cell to index 2^k - 1 cell, they are in the previous cycle of the latest cell
                    if registers[i][j]['FID'] == '0000000000000000':
                        continue
                    t_CID = registers[i][j]['tts'] >> self.k
                    t_idx = registers[i][j]['tts'] & (2 ** self.k - 1)
                    if (t_CID + 1) & ((1 << CID_bit) - 1) == latest_CID & ((1 << CID_bit) - 1):  # consider overflow
                        count[i] += 1
                        temp = {'FID': registers[i][j]['FID'],
                                'tts': registers[i][j]['tts'],
                                'twid': i}
                        if t_CID > latest_CID:
                            temp['wrap'] = wrapping - 1  # there is overflow, because we already find the largest tts
                        else:
                            temp['wrap'] = wrapping
                        TW_result.append(temp)
                        if first_pre_cycle == 0:
                            first_pre_cycle = 1
                            smallest_cell = temp

                CID_bit -= self.alpha
                largest_tts = (largest_tts - 2 ** self.k) >> self.alpha  # the tts of the replaced cell
                largest_idx = largest_tts & (2 ** self.k - 1)
                latest_CID = largest_tts >> self.k
            # retrieve smallest and largest ts
            print('smallest ts: {0}, largest ts: {1}, count: {2}'.format(smallest_cell, largest_cell, count))
            tw['TW_result'] = TW_result
            tw['largest_cell'] = largest_cell
            tw['smallest_cell'] = smallest_cell
            tw['lts'] = self.cell_duration(largest_cell['tts'], largest_cell['twid'])[2] + (1 << 32) * largest_cell[
                'wrap']  # ealiest timestamp of the set
            tw['sts'] = self.cell_duration(smallest_cell['tts'], smallest_cell['twid'])[2] + (1 << 32) * smallest_cell[
                'wrap']  # latest timestamp of the set

    def cell_duration(self, tts, twid):
        """
        :return: [C, D, E], C is the smallest possible timestamp, D is the largest possible timestamp,
        E is the middle of the smallest and the largest
        """
        TB = self.TW0_TB + twid * self.alpha
        return [tts << TB, (tts << TB) + 2 ** TB - 1, (tts << TB) + 2 ** (TB - 1)]

    def retrieve(self, ts, te):
        """
        Given a query interval [ts, te], return the result
        :param ts: start of query interval
        :param te: end of query interval
        :return: {'flow ID hex string': integer}, The list of sets, [[s, e]],  G
        {'flow ID hex string': integer} is the list of flows with packet number in the descending order
        The list of sets is where query falls
        [[s,e]]: the original query may be cut into several queries
        G: index of the window in which most cells are located
        """
        TW = []
        query_interval = []
        # Locate the right set
        for (i, tw) in enumerate(self.TW_registers):
            if tw['sts'] <= ts and ts <= tw['lts']:
                if te <= tw['lts']:
                    TW.append(tw)
                    query_interval.append([ts, te])
                    break
                else:
                    # cut a long query into several queries
                    TW.append(tw)
                    query_interval.append([ts, tw['lts']])
                    ts = max(tw['lts'], self.TW_registers[i + 1]['sts'])
        if not TW:
            print("For query {0} to {1}, no right set of time windows is found!".format(ts, te))
            return [], TW, query_interval, -1
        agg = []  # [{'FID': N}], each element are cells from window i
        for i in range(0, self.T):
            agg.append({})
        # retrieve packets within the interval
        for (i, window) in enumerate(TW):
            for pkt in window['TW_result']:
                re_ts = self.cell_duration(pkt['tts'], pkt['twid'])[2] + pkt['wrap'] * (1 << 32)
                if query_interval[i][0] <= re_ts and re_ts <= query_interval[i][1]:
                    agg[pkt['twid']][pkt['FID']] = agg[pkt['twid']].get(pkt['FID'], 0) + 1
        # get the estimated number of packets
        max_window = -1
        window_id = -1
        for (i, agg_tw) in enumerate(agg):
            if len(agg_tw.keys()) > max_window:
                max_window = len(agg_tw.keys())
                window_id = i
        result = {}  # {'FID': EN}
        for twi, agg_tw in enumerate(agg):
            for FID, N in agg_tw.items():
                result[FID] = result.get(FID, 0) + int(N / self.cofficient[twi])
            result = dict(sorted(result.items(), key=lambda item: item[1], reverse=True))
        return result, TW, query_interval, window_id

    def retrieve2(self, ts, te, TW_result):
        """
        Given a query interval and TW_result, return the list of flows
        :param TW_result: [cell_representation]
        cell_representation = {'tts': integer, 'FID': hex_string, 'wrap': integer, 'twid': integer}
        :return: {'flow ID hex string': integer}
        """
        agg = []  # [{'FID': N}]
        for i in range(0, self.T):
            agg.append({})
        # retrieve packets within the interval
        for pkt in TW_result:
            re_ts = self.cell_duration(pkt['tts'], pkt['twid'])[2] + pkt['wrap'] * (1 << 32)
            if ts <= re_ts and re_ts <= te:
                agg[pkt['twid']][pkt['FID']] = agg[pkt['twid']].get(pkt['FID'], 0) + 1
        # get the estimated number of packets
        result = {}  # {'FID': EN}
        for twi, agg_tw in enumerate(agg):
            for FID, N in agg_tw.items():
                result[FID] = result.get(FID, 0) + int(N / self.cofficient[twi])
        result = dict(sorted(result.items(), key=lambda item: item[1], reverse=True))
        return result

    def draw_top(self, ts, te, ret, K=10):
        """
        visualize Top-K flows given the list of flows
        :param ret: [{'FID': integer}]
        :param K: Top-K
        """
        K = min(K, len(ret))
        ret = list(ret.items())[0: K]
        print("Plotting TW result Top-{0} flows from {1} to {2}".format(K, ts, te))
        flow_ids = []
        pkt_num = []
        for (key, val) in ret:
            flow_ids.append(key)
            pkt_num.append(val)
        plt.bar(flow_ids, pkt_num)
        plt.xlabel('flow ID')
        plt.ylabel('packet number')
        bar_title = "TW result Top-{0} flows from {1} to {2}".format(K, ts, te)
        plt.title(bar_title)
        plt.xticks(rotation=-15)
        plt.tight_layout()
        plt.savefig(os.path.join('fig', bar_title + '.png'))
        plt.close()

num_pipes = 2
class TimeWindowController_stale:
    def __init__(self, path, alpha = 1, k = 12, T = 5, TW0_TB = 6, TW0_z = 64/110, save_file_path = None):
        self.alpha = alpha
        self.k = k
        self.index_number_per_window = 2**self.k
        self.T = T
        self.TW0_TB = TW0_TB
        self.TW0_z = TW0_z
        self.total_duration = int((2**(alpha*T) - 1) / (2**alpha - 1) * 2**(TW0_TB + k))
        self.TW_result = []    # a linear data structure # {FID: hex, tts: , twid: ,}
        self.cofficient = self.calculate_coefficient2(TW0_z, alpha,T)
        self.config = {'alpha': alpha, 'k': k, 'TW0_TB': TW0_TB, 'T': T, 'TW0_z': TW0_z, 'total_duration': self.total_duration}
        print('Time Window total duration is: {0} nanoseconds, cofficient: {1}'.format(self.total_duration, self.cofficient))
        self.TW_registers = self.poll_register(path) #  [{ts: , tw:[[{FID: hex, tts:}]] }]
        self.filter_TW()

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

    def poll_register(self, json_path):
        with open(json_path, 'r') as f:
            registers = json.load(f)  # [{tts: [], src_ip: [], dst_ip: [], src_port: [], dst_port: []}]
        ret = []
        for TWid in range(0, self.T):
            ret.append([])
        actual_item_number = self.index_number_per_window * num_pipes
        for TWid in range(0, self.T):
            for j in range(0, actual_item_number):
                if j % num_pipes != 1:
                    continue
                temp = {}
                temp['tts'] = registers[TWid]['tts'][j]
                sip = registers[TWid]['src_ip'][j]
                dip = registers[TWid]['dst_ip'][j]
                if sip < 0:
                    sip = sip + 2 ** 32
                if dip < 0:
                    dip = dip + 2 ** 32
                sport = registers[TWid]['src_port'][j]
                dport = registers[TWid]['dst_port'][j]
                if sport < 0:
                    sport = sport + 2 ** 16
                if dport < 0:
                    dport = dport + 2 ** 16
                temp['FID'] = (sip.to_bytes(4, 'big') + dip.to_bytes(4, 'big') + sport.to_bytes(2, 'big') + dport.to_bytes(2, 'big')).hex()
                ret[TWid].append(temp)
        return ret

    def filter_TW(self):
        TW0 = self.TW_registers[0]
        largest_tts = 0
        largest_idx = 0
        for j in range(0, self.index_number_per_window):
            if TW0[j]['tts'] > largest_tts:
                largest_tts = TW0[j]['tts']
                largest_idx = j
        l_tts = self.cell_duration(largest_tts, 0)[2]
        latest_CID = largest_tts >> self.k
        count = []  # number of filtered packets in different TW
        for i in range(0, self.T):
            count.append(0)
            first_pre_cycle = 0
            for j in range(0, largest_idx + 1):
                if self.TW_registers[i][j]['tts'] == 0:
                    continue
                t_CID = self.TW_registers[i][j]['tts'] >> self.k
                t_idx = self.TW_registers[i][j]['tts'] & (2 ** self.k - 1)
                if t_CID == latest_CID:
                    count[i] += 1
                    self.TW_result.append({'FID': self.TW_registers[i][j]['FID'],
                                           'tts': self.TW_registers[i][j]['tts'],
                                           'twid': i})
                    if first_pre_cycle == 0:
                        first_pre_cycle = 1
                        s_tts = self.cell_duration(self.TW_registers[i][j]['tts'], i)[2]
            first_pre_cycle = 0
            for j in range(largest_idx + 1, self.index_number_per_window):
                if self.TW_registers[i][j]['tts'] == 0:
                    continue
                t_CID = self.TW_registers[i][j]['tts'] >> self.k
                t_idx = self.TW_registers[i][j]['tts'] & (2 ** self.k - 1)
                if t_CID + 1 == latest_CID:
                    count[i] += 1
                    self.TW_result.append({'FID': self.TW_registers[i][j]['FID'],
                                           'tts': self.TW_registers[i][j]['tts'],
                                           'twid': i})
                    if first_pre_cycle == 0:
                        first_pre_cycle = 1
                        s_tts = self.cell_duration(self.TW_registers[i][j]['tts'], i)[2]

            largest_tts = (largest_tts - 2 ** self.k) >> self.alpha  # the tts of the replaced cell
            largest_idx = largest_tts & (2 ** self.k - 1)
            latest_CID = largest_tts >> self.k
        # retrieve smallest and largest ts
        # self.TW_result = sorted(self.TW_result, key=lambda x: (x['twid'], x['tts']))
        self.config['largest_ts'] = l_tts
        self.config['smallest_ts'] = s_tts
        print('smallest ts: {0}, largest ts: {1}'.format(self.config['smallest_ts'], self.config['largest_ts']))

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
        TW_result = dict(sorted(TW_result.items(), key=lambda item: item[1], reverse= True))
        retrieve_result['TW_result'] = TW_result
        return retrieve_result

def precision_and_recall_packet_number(gt, tw):
    """
    Precision and Recall using the packet number
    :param gt: ['FID': integer], the ground truth list of flows
    :param tw: ['FID': integer], the result from TW or related works
    :return: [precision, recall]
    """
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
    if recall_total == 0 or precision_total == 0:
        return [0, 0]
    return [precision_hit / precision_total, precision_hit / recall_total]


def precision_and_recall(gt, tw):
    """
    Precision and Recall using the number of flows
    :param gt: ['FID': integer], the ground truth list of flows
    :param tw: ['FID': integer], the result from TW or related works
    :return: [precision, recall]
    """
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
    """
    A list of distinctive hash functions
    """
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


def Count_Min(hash, gt, filter, Row=3, Col=1024):
    """
    Simulation of Count-Min Sketch. Given the list of packet numbers, use filter (flowID list) to retrieve packet number
    :return: {'flow ID hex string': integer}
    """
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


def Flow_Radar(hash, gt, cell_number=4096 * 5):
    """
    Simulation of FlowRadar. Given a list of flows as input, return the estimated flow list within a fixed interval
    :param hash: hash function list
    :param gt: input flow list
    :param cell_number: the size of the data structure
    :return: {'flow ID hex string': integer}
    """
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
        if sum == hash_number:  # old flow
            for j in pos:
                tables[j]['pn'] += n
        else:  # new flow
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


def hash_pipe(hash, traces, stages=5, cell_number=1024):
    """
    Simulation of HashPipe. Given a packet trace, return the estimated flow list within a fixed interval
    :param hash: hash function list
    :param traces: packet trace
    :param stages: HashPipe stages
    :param cell_number: number of cells per stage
    :return: {'flow ID hex string': integer}
    """
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