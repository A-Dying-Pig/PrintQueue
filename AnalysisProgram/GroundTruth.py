'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    1) The Analysis Program for interpreting ground truth data.
    2) Comparison between Time Windows and related works, Count-Min Sketch, HashPipe, FlowRadar
Last Update Time:
    2022.4.19
'''
import os
import matplotlib.pyplot as plt
from TimeWindows import *
import random
import csv
import time
import math

class GroundTruth:
    def __init__(self, path):
        """
        The class reads ground truth (INT data), visualize data, and sample packets.
        :param path: the path to the parent folder of the ground truth data folder
        """
        files = []
        self.root_dir = path
        data_path = os.path.join(path, 'gt_data')
        for (root, dirs, fs) in os.walk(data_path):
            sorted(fs)
            files = [os.path.join(root, f) for f in fs]
        self.enqueue_ts_array = []
        self.dequeue_ts_array = []
        self.queue_len_array = []
        self.FID_array = []   # port value is big endian
        self.sum_interval = 0
        base_enqueue = 0
        base_dequeue = 0
        first = 0
        first_K = 10
        last_K = 10
        for f in files:
            print("loading file: {0}".format(f))    # load INT data
            with open(f, 'rb') as fptr:
                chunk = fptr.read(20)
                p_dqts = int.from_bytes(chunk[0:4], 'big') + base_dequeue
                p_eqts = int.from_bytes(chunk[4:8], 'big') + base_enqueue
                p_qlen = int.from_bytes(chunk[8:12], 'big')
                p_FID = chunk[12:20].hex()
                if p_eqts > p_dqts:
                    base_dequeue += (1 << 32)
                    p_dqts += (1 << 32)
                chunk = fptr.read(20)
                while chunk:
                    dqts = int.from_bytes(chunk[0:4], 'big') + base_dequeue
                    eqts = int.from_bytes(chunk[4:8], 'big') + base_enqueue
                    qlen = int.from_bytes(chunk[8:12], 'big')
                    FID = chunk[12:20].hex()
                    chunk = fptr.read(20)
                    if first < first_K:
                        first += 1
                        p_dqts = dqts
                        p_qlen = qlen
                        p_eqts = eqts
                        continue
                    if eqts > dqts:
                        base_dequeue += (1 << 32)
                        dqts += (1 << 32)
                    if dqts < p_dqts:
                        if p_dqts - dqts > 4000000000:  # dequeue timestamp overflow
                            base_dequeue += (1 << 32)
                            dqts += (1 << 32)
                        else:
                            continue
                    if eqts < p_eqts:
                        if p_eqts - eqts > 4000000000:
                            base_enqueue += (1 << 32)
                            eqts += (1 << 32)
                        else:
                            continue
                    self.dequeue_ts_array.append(dqts)
                    self.queue_len_array.append(qlen)
                    self.enqueue_ts_array.append(eqts)
                    self.FID_array.append(FID)
                    p_dqts = dqts
                    p_qlen = qlen
                    p_eqts = eqts
        self.dequeue_ts_array = self.dequeue_ts_array[0:-last_K]
        self.enqueue_ts_array = self.enqueue_ts_array[0:-last_K]
        self.FID_array = self.FID_array[0:-last_K]
        self.queue_len_array = self.queue_len_array[0:-last_K]
        self.first_dts = self.dequeue_ts_array[0]
        self.last_dts = self.dequeue_ts_array[-1]
        self.first_ets = self.enqueue_ts_array[0]
        self.last_ets = self.enqueue_ts_array[-1]
        self.pkt_num = len(self.dequeue_ts_array)
        self.sum_queue_len = self.queue_len_array[0]
        p_dqts = self.dequeue_ts_array[0]
        for i in range(1, self.pkt_num):
            self.sum_queue_len += self.queue_len_array[i]
            self.sum_interval += self.dequeue_ts_array[i] - p_dqts
            p_dqts = self.dequeue_ts_array[i]
        self.average_interval = self.sum_interval / (self.pkt_num - 1)
        self.average_queue_len = self.sum_queue_len / self.pkt_num
        self.dequeue_total = self.last_dts - self.first_dts
        self.enqueue_total = self.last_ets - self.first_ets
        print('-----------------------------------------------------------------------------------')
        print('-----------------       Analysis Program for Ground Truth    ----------------------')
        print('------------------------       Loaded from INT data    ----------------------------')
        print('-----------------------------------------------------------------------------------')
        print(
            'Packet number: {0}\nTotal duration (dequeue timestamp): {1} nanoseconds\nTotal duration (enqueue '
            'timestamp): {4} nanoseconds\nAverage queue length: {2}\nAverage interval: {3}'
            .format(self.pkt_num, self.dequeue_total, self.average_queue_len, self.average_interval, self.enqueue_total))
        # draw
        # self.draw_queue_length()
        # self.draw_total_distribution(self.first_ets, self.last_ets)

    def packet_experiencing_high_delay(self, threshold=500):
        """
        :param threshold: integer
        :return: [packet], packets whose queue depths are larger than the threshold
        """
        ret = [] # [{FID: , ets: , dts:  ,qlen:}]
        for i in range(0, self.pkt_num):
            if self.queue_len_array[i] > threshold:
                tmp = {}
                tmp['FID'] = self.FID_array[i]
                tmp['ets'] = self.enqueue_ts_array[i]
                tmp['dts'] = self.dequeue_ts_array[i]
                tmp['qlen'] = self.queue_len_array[i]
                ret.append(tmp)
        return ret

    def packet_experiencing_high_delay2(self, threshold):
        """
        :param threshold: [A, B, D, E ... Z]
        :return: [[{'FID': hex_string, 'ets': enqueue_timestamp, 'dts': dequeue_timestamp, 'qlen': qdepth}]]
        packets whose queue depths are within [A, B], [B,C], [C,D] ... >Z
        """
        ret = [] # [{FID: , ets: , dts:  ,qlen:}]
        for i in range(0, len(threshold)):
            ret.append([])
        for i in range(0, self.pkt_num):
            save = False
            j = 0
            for j in range(0, len(threshold)):
                if self.queue_len_array[i] < threshold[0]:
                    break
                if j == len(threshold) - 1:
                    save = True
                    break
                if self.queue_len_array[i] > threshold[j] and self.queue_len_array[i] <= threshold[j+1]:
                    save = True
                    break
            if save:
                tmp = {}
                tmp['FID'] = self.FID_array[i]
                tmp['ets'] = self.enqueue_ts_array[i]
                tmp['dts'] = self.dequeue_ts_array[i]
                tmp['qlen'] = self.queue_len_array[i]
                ret[j].append(tmp)
        return ret

    def draw_queue_length(self):
        """
        Visualize queue depth changes according to the enqueue timestamp
        """
        print("Plotting queue length...")
        plt.plot(self.enqueue_ts_array, self.queue_len_array)
        plt.xlabel('enqueue timestamp')
        plt.ylabel('enqueue queue length')
        plt.title('Queue Length with Time')
        plt.savefig(os.path.join(self.root_dir, 'QueueLength.png'))
        plt.close()
        self.output_queue_length()

    def output_queue_length(self):
        """
        Write enqueue timestamp along with queue depth into csv file
        """
        csv_file = open(os.path.join(self.root_dir,'queue.csv'), 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        for i in range(0, self.pkt_num):
            resultWriter.writerow([self.enqueue_ts_array[i], self.queue_len_array[i]])
        csv_file.close()

    def output_queue_length_with_queuing_time(self):
        """
        Write queue depth along with queuing delay into csv file
        """
        csv_file = open(os.path.join(self.root_dir,'queuing.csv'), 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        for i in range(0, self.pkt_num):
            if i % 100000 == 0:
                resultWriter.writerow([self.queue_len_array[i], self.dequeue_ts_array[i] - self.enqueue_ts_array[i]])
        csv_file.close()


    def top(self, ts, te, K=0):
        """
        Given a interval, return Top-K flows (ground truth) within that interval
        :param ts: start of the interval
        :param te: end of the interval
        :param K: Top-K
        :return: {'flow ID hex string': integer}
        """
        # return a sorted list in descending order
        ret = {}  # {FID: NUMBER}
        for (index, t) in enumerate(self.enqueue_ts_array):
            if ts <= t and t <= te:
                ret[self.FID_array[index]] = ret.get(self.FID_array[index], 0) + 1
        ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
        if K == 0:
            return ret
        K = min(K, len(ret))
        return dict(list(ret.items())[0: K])

    def retrieve(self, ts, te, K=0):
        ret = {}
        for (index, t) in enumerate(self.dequeue_ts_array):
            if ts <= t and t <= te:
                ret[self.FID_array[index]] = ret.get(self.FID_array[index], 0) + 1
        ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
        if K == 0:
            return ret
        K = min(K, len(ret))
        return dict(list(ret.items())[0: K])


    def traces(self, ts, te):
        """
        Given a interval, return the packet traces in the switch (in the original order)
        :return: ['flow ID hex string']
        """
        ret = []
        for (index, t) in enumerate(self.dequeue_ts_array):
            if ts <= t and t <= te:
                ret.append(self.FID_array[index])
        return ret

    def draw_top(self, ts, te, K=10):
        """
        Visualize Top-K flows within the interval [ts, te]
        """
        ret = self.top(ts, te)
        K = min(K, len(ret))
        ret = list(ret.items())[0: K]
        print("plotting top {0} flows from {1} to {2}".format(K, ts, te))
        flow_ids = []
        pkt_num = []
        for (key, val) in ret:
            flow_ids.append(key)
            pkt_num.append(val)
        plt.bar(flow_ids, pkt_num)
        plt.xlabel('flow ID')
        plt.ylabel('packet number')
        bar_title = "Ground Truth top {0} flows from {1} to {2}".format(K, ts, te)
        plt.title(bar_title)
        plt.xticks(rotation=-15)
        plt.tight_layout()
        plt.savefig(os.path.join(self.root_dir, bar_title + '.png'))
        plt.close()


    def draw_total_distribution(self, ts, te, n_period=100):
        """
        Visualize the distribution of the total traffic along with time
        :param n_period: cut the interval [ts, te] into n_period small periods
        """
        period_len = self.enqueue_total / n_period
        total_pkt = []
        period = []
        t = int(self.first_ets + period_len / 2)
        prev_index = 0
        j = 0
        while t < self.last_ets:
            period.append(t)
            total_pkt.append(0)
            te = int(t + period_len / 2)
            index = prev_index
            while index < len(self.enqueue_ts_array):
                if self.enqueue_ts_array[index] < te:
                    total_pkt[j] += 1
                    prev_index += 1
                    index += 1
                else:
                    break
            t += period_len
            j += 1
        # output
        csv_file = open(os.path.join(self.root_dir,'flow.csv'), 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        for i in range(0, len(period)):
            resultWriter.writerow([period[i], total_pkt[i]])
        csv_file.close()
        # draw
        print("Plotting total traffic...")
        plt.xlabel('enqueue timestamp')
        plt.ylabel('total packet number')
        plot_title = "Total Traffic with Time"
        plt.title(plot_title)
        plt.plot(period, total_pkt)
        plt.savefig(os.path.join(self.root_dir, plot_title + '.png'))
        plt.close()

    def draw_top_flow_distribution(self, n_period=100, K=10):
        """
        Visualize Top-K flows of the whole trace
        """
        ret = self.top(self.first_ets, self.last_ets, K)
        self.draw_flow_distribution(n_period, ret.keys())

    def draw_flow_distribution(self, n_period=100, filter_list=[]):
        """
        Visualize flow size distribution along with time
        :param filter_list: if not [], only visualize flows in the list
        """
        # only draw flows in the list
        if filter_list == []:
            is_filter = False
        else:
            is_filter = True
        period_len = self.enqueue_total / n_period
        pkt_per_period = {}  # {FID1: [], FID2:[]}
        period = []
        t = int(self.first_ets + period_len / 2)
        new_one_len = 0
        prev_index = 0
        while t < self.last_ets:
            period.append(t)
            ts = int(t - period_len / 2)
            te = int(t + period_len / 2)
            tmp = {}  # {FID: number, FID: number}
            index = prev_index
            while index < len(self.enqueue_ts_array):
                if self.enqueue_ts_array[index] < te:
                    tmp[self.FID_array[index]] = tmp.get(self.FID_array[index], 0) + 1
                    prev_index += 1
                    index += 1
                else:
                    break
            for (key, value) in pkt_per_period.items():
                value.append(tmp.get(key, 0))
                if key in tmp:
                    del tmp[key]
            for (new_key, value) in tmp.items():
                if is_filter and new_key not in filter_list:
                    continue
                if new_one_len == 0:
                    temp_list = []
                else:
                    temp_list = [0 for i in range(0, new_one_len)]
                temp_list.append(value)
                pkt_per_period[new_key] = temp_list
            t += period_len
            new_one_len += 1
        # draw plot
        print("plotting flow size...")
        plt.xlabel('enqueue timestamp')
        plt.ylabel('packet number')
        if len(filter_list) == 0:
            plot_title = "All Flow Size with Time"
        else:
            plot_title = "{0} Flow Size with Time".format(len(filter_list))
        plt.title(plot_title)
        for (flow, flow_number) in pkt_per_period.items():
            plt.plot(period, flow_number)
        plt.savefig(os.path.join(self.root_dir, plot_title + '.png'))
        plt.close()

class GroundTruth_stale:
    def __init__(self, root_dir='./'):
        files = []
        data_path = os.path.join(root_dir, 'gt_data')
        for (root, dirs, fs) in os.walk(data_path):
            sorted(fs)
            files = [os.path.join(root, f) for f in fs]
        self.dequeue_ts_array = []
        self.queue_len_array = []
        self.FID_array = []   # port value is big endian
        self.sum_interval = 0
        base_dequeue = 0
        first = 0
        first_K = 10
        last_K = 10
        for f in files:
            print("loading file: {0}".format(f))
            with open(f, 'rb') as fptr:
                chunk = fptr.read(20)
                p_dqts = int.from_bytes(chunk[0:4], 'big') + base_dequeue
                p_qlen = int.from_bytes(chunk[4:8], 'big')
                p_FID = chunk[8:20].hex()
                chunk = fptr.read(20)
                while chunk:
                    dqts = int.from_bytes(chunk[0:4], 'big') + base_dequeue
                    qlen = int.from_bytes(chunk[4:8], 'big')
                    FID = chunk[8:20].hex()
                    chunk = fptr.read(20)
                    if first < first_K:
                        first += 1
                        p_dqts = dqts
                        p_qlen = qlen
                        continue
                    if dqts < p_dqts:
                        base_dequeue += (1 << 32)
                        dqts += (1 << 32)
                    self.dequeue_ts_array.append(dqts)
                    self.queue_len_array.append(qlen)
                    self.FID_array.append(FID)
                    p_dqts = dqts
                    p_qlen = qlen
        self.dequeue_ts_array = self.dequeue_ts_array[0:-last_K]
        self.FID_array = self.FID_array[0:-last_K]
        self.queue_len_array = self.queue_len_array[0:-last_K]
        self.first_dts = self.dequeue_ts_array[0]
        self.last_dts = self.dequeue_ts_array[-1]
        self.pkt_num = len(self.dequeue_ts_array)
        self.sum_queue_len = self.queue_len_array[0]
        p_dqts = self.dequeue_ts_array[0]
        for i in range(1, self.pkt_num):
            self.sum_queue_len += self.queue_len_array[i]
            self.sum_interval += self.dequeue_ts_array[i] - p_dqts
            p_dqts = self.dequeue_ts_array[i]
        self.average_interval = self.sum_interval / (self.pkt_num - 1)
        self.average_queue_len = self.sum_queue_len / self.pkt_num
        self.dequeue_total = self.last_dts - self.first_dts
        print(
            'Packet number {0}, dequeue_total: {1} nanoseconds, nanosecond, average queue length: {2}, average interval: {3}'
            .format(self.pkt_num, self.dequeue_total, self.average_queue_len, self.average_interval))

    def top(self, ts, te, K=0):
        # return a sorted list in descending order
        ret = {}  # {FID: NUMBER}
        for (index, t) in enumerate(self.dequeue_ts_array):
            if ts <= t and t <= te:
                ret[self.FID_array[index]] = ret.get(self.FID_array[index], 0) + 1
        ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse=True))
        if K == 0:
            return ret
        K = min(K, len(ret))
        return dict(list(ret.items())[0: K])


def Comparison(path, alpha, k, T, TW0_TB, TW0_z, sample_threshold=[1000, 2000, 5000, 10000, 15000, 20000], packet_sample_number=20):
    """
    Compare TW with related works: Count-Min Sketch, HashPipe, FlowRadar
    :param path: the path to the parent folder of RAW and INT data
    outputs comparison result to a csv file
    """
    tw = TimeWindowController(path=path, alpha=alpha, k=k, T=T, TW0_TB=TW0_TB, TW0_z=TW0_z)
    gt = GroundTruth(path)
    print('-----------------------------------------------------------------------------------')
    print('---------------    Compare Time Windows with Related Works   ----------------------')
    print('-----------------------------------------------------------------------------------')
    # exp1
    hash_list = HashFunction()
    print("Sampling packets")
    pkts = gt.packet_experiencing_high_delay2(sample_threshold)
    sample_pkts = []
    sample_pkts_ids = []
    for i in range(0, len(pkts)):
        sample_pkts.append([])
        sample_pkts_ids.append([])
        pkts_number = len(pkts[i])
        while len(sample_pkts_ids[i]) < packet_sample_number:
            id = random.randint(0, pkts_number - 1)
            if id not in sample_pkts_ids[i]:
                sample_pkts_ids[i].append(id)
                sample_pkts[i].append(pkts[i][id])
    for j in range(len(sample_pkts)):
        csv_file = open(os.path.join(path, 'qdepth_level_{0}_result.csv'.format(j)), 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        idx = 0
        for pkt in sample_pkts[j]:
            pkt['gt'] = gt.retrieve(pkt['ets'], pkt['dts'])
            pkt['tw'], tws, query_interval, ret_window = tw.retrieve(pkt['ets'], pkt['dts'])

            if pkt['tw']:
                PQ_p,PQ_r = precision_and_recall_packet_number(pkt['gt'],pkt['tw'])
                if PQ_p == 0 and PQ_r == 0:
                    continue
                print('Time Windows, Number Precision: {0}, Number Recall: {1}'.format(PQ_p,PQ_r))

                proportion = []
                gt_packets = []
                traces = []
                for i in range(0,len(tws)):
                    if tws[i]['lts'] == tws[i]['sts']:
                        p = 1
                    else:
                        p = (query_interval[i][1] - query_interval[i][0]) / (tws[i]['lts'] - tws[i]['sts'])
                    proportion.append(p)
                    gt_pkt = gt.retrieve(tws[i]['sts'], tws[i]['lts'])
                    gt_packets.append(gt_pkt)
                    t = gt.traces(tws[i]['sts'], tws[i]['lts'])
                    traces.append(t)

                result = {}
                for i in range(0,len(tws)):
                    ret = Count_Min(hash_list, gt_packets[i], pkt['gt'], 3, 1024)
                    for (key, val) in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                CM1_p, CM1_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("Count-Min Sketch: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(CM1_p, CM1_r))

                result = {}
                for i in range(0, len(tws)):
                    ret = Count_Min(hash_list, gt_packets[i], pkt['gt'], 5,  4096)
                    for (key, val) in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                CM2_p, CM2_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("Count-Min Sketch: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(CM2_p, CM2_r))

                result = {}
                for i in range(0, len(tws)):
                    ret = hash_pipe(hash_list, traces[i], 3, 1024)
                    for key, val in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                HP1_p, HP1_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("HashPipe: 512 x 2, Number Precision: {0}, Number Recall: {1}".format(HP1_p, HP1_r))

                result = {}
                for i in range(0, len(tws)):
                    ret = hash_pipe(hash_list, traces[i], 5, 4096)
                    for key, val in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                HP2_p, HP2_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("HashPipe: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(HP2_p, HP2_r))

                result = {}
                for i in range(0, len(tws)):
                    ret = Flow_Radar(hash_list, gt_packets[i], 1024*3)
                    for key, val in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                FR1_p, FR1_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("FlowRadar: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(FR1_p, FR1_r))

                result = {}
                for i in range(0, len(tws)):
                    ret = Flow_Radar(hash_list,gt_packets[i], 4096*5)
                    for key, val in ret.items():
                        result[key] = result.get(key, 0) + int(val * proportion[i])
                FR2_p, FR2_r = precision_and_recall_packet_number(pkt['gt'], result)
                print("FlowRadar: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(FR2_p, FR2_r))

                resultWriter.writerow([idx, pkt['ets'], pkt['dts'], pkt['qlen'], PQ_p,PQ_r, CM1_p, CM1_r, CM2_p, CM2_r, HP1_p, HP1_r, HP2_p, HP2_r, FR1_p, FR1_r, FR2_p, FR2_r])
                idx += 1
        csv_file.close()

def DataPlaneQuery(path, alpha, k, T, TW0_TB, TW0_z):
    """
    Compare TW data plane query with related works: Count-Min Sketch, HashPipe, FlowRadar
    :param path: the path to the parent folder of RAW and INT data
    outputs comparison result to a csv file
    """
    tw = TimeWindowController(path=path, alpha=alpha, k=k, T=T, TW0_TB=TW0_TB, TW0_z=TW0_z)
    gt = GroundTruth(path)
    print('---------------------------------------------------------------------------------------')
    print('---------------    Compare Data Plane Query with Related Works   ----------------------')
    print('---------------------------------------------------------------------------------------')
    csv_file = open(os.path.join(path, 'data_plane_query_accuracy.csv'), 'w')
    resultWriter = csv.writer(csv_file, dialect='excel-tab')
    for pkt in tw.signals:
        pkt['gt'] = gt.retrieve(pkt['enqueue_ts'], pkt['dequeue_ts'])
        pkt['tw_dpq'], tws, query_interval, ret_window = tw.retrieve(pkt['enqueue_ts'], pkt['dequeue_ts'])
        if pkt['tw_dpq']:
            PQ_p, PQ_r = precision_and_recall_packet_number(pkt['gt'], pkt['tw_dpq'])
            if PQ_p == 0 and PQ_r == 0:
                continue
            print('Time Windows Data Plane Query, Number Precision: {0}, Number Recall: {1}'.format(PQ_p, PQ_r))
            resultWriter.writerow([PQ_p, PQ_r])
    csv_file.close()

def timer(path, alpha, k, T, TW0_TB, TW0_z, packet_sample_number=20):
    '''
    Count the execution time of query
    '''
    tw = TimeWindowController(path=path, alpha=alpha, k=k, T=T, TW0_TB=TW0_TB, TW0_z=TW0_z)
    gt = GroundTruth(path)
    stairs = [1000, 2000, 5000, 10000, 15000, 20000]
    pkts = gt.packet_experiencing_high_delay2(stairs)
    sample_pkts = []
    sample_pkts_ids = []
    for i in range(0, len(pkts)):
        sample_pkts.append([])
        sample_pkts_ids.append([])
        pkts_number = len(pkts[i])
        while len(sample_pkts_ids[i]) < packet_sample_number:
            id = random.randint(0, pkts_number - 1)
            if id not in sample_pkts_ids[i]:
                sample_pkts_ids[i].append(id)
                sample_pkts[i].append(pkts[i][id])
    start = time.time() * 1e6 #us
    for j in range(len(sample_pkts)):
        for pkt in sample_pkts[j]:
            pkt['tw'], tws, query_interval, ret_window = tw.retrieve(pkt['ets'], pkt['dts'])
    end = time.time() * 1e6 #us
    query_num = packet_sample_number * len(stairs)
    per_query_time = (end - start) / query_num
    QPS = math.floor(1e6 / per_query_time)
    print("Execute {0} queris, each query takes {1} us, QPS: {2}".format(query_num, per_query_time, QPS))


def TopK(path):
    for (root, dir, file) in os.walk(path):
        for subdir in dir:
            current_dir = os.path.join(root, subdir)
            TW_dir = os.path.join(current_dir, 'tw_data')
            for (r, d, f) in os.walk(TW_dir):
                json_file = f[0]
            json_path = os.path.join(TW_dir, json_file)
            csv_file = open(os.path.join(current_dir, 'TopK.csv'), 'w')
            resultWriter = csv.writer(csv_file, dialect='excel-tab')
            tw = TimeWindowController_stale(path=json_path, alpha=1, k=12, T=5, TW0_TB=6, TW0_z=64 / 105)
            gt = GroundTruth_stale(current_dir)
            # Each time windows TopK precision & recall
            stairs = [50, 100, 200, 500]
            for i in range(0, tw.T):
                print('Calculating TopK P&R in time window: {0}'.format(i))
                ts, te = tw.TW_start_end_timestamp(i)
                pkt_gt = gt.top(ts, te)
                pkt_tw = tw.retrieve(ts, te)['TW_result']
                for j in range(0, len(stairs)):
                    gt_ret = dict(list(pkt_gt.items())[0: stairs[j]])
                    tw_ret = dict(list(pkt_tw.items())[0: stairs[j]])
                    np, nr = precision_and_recall_packet_number(gt_ret, tw_ret)
                    print("Top-{0}. time window: {1}, Number Precision: {2}, Number Recall: {3}".format(stairs[j], i, np, nr))
                    resultWriter.writerow(['Window {0}'.format(i), 'Top-{0}'.format(stairs[j]), np, nr])
                np, nr = precision_and_recall_packet_number(pkt_gt, pkt_tw)
                print("Top-All. time window: {0}, Number Precision: {1}, Number Recall: {2}".format(i, np, nr))
                resultWriter.writerow(['Window {0}'.format(i), 'Top-All', np, nr])
            csv_file.close()
        break

if __name__ == '__main__':
    Comparison(path='./d/ports/1/0', alpha=1, k=12, T=4, TW0_TB=10, TW0_z=1024 / 1250, sample_threshold=[10000])
    DataPlaneQuery(path='./d/ports/1/0', alpha=1, k=12, T=4, TW0_TB=10, TW0_z=1024 / 1250)
    # # timer(path='./d/syn3/1000', alpha=1, k=12, T=4, TW0_TB=10, TW0_z=1024 / 1250)
    # TopK('./d/TopK/')

