import os
import matplotlib.pyplot as plt
from TimeWindowController import *
import random
import csv

class GroundTruth:
    def __init__(self, root_dir='./'):
        files = []
        data_path = os.path.join(root_dir, 'data')
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
            print("loading file: {0}".format(f))
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
                        if p_dqts - dqts > 4000000000:
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
        print(
            'Packet number {0}, dequeue_total: {1} nanoseconds, enqueue_total: {4} nanosecond, average queue length: {2}, average interval: {3}'
            .format(self.pkt_num, self.dequeue_total, self.average_queue_len, self.average_interval, self.enqueue_total))
        # self.draw_flow_distribution()
        self.draw_queue_length()
        # self.draw_top(self.first_ets, self.last_ets)
        # self.draw_top_flow_distribution(K=10)
        self.draw_total_distribution(self.first_ets, self.last_ets)

    def packet_experiencing_high_delay(self, threshold=500):
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

    def draw_queue_length(self):
        print("plotting queue length...")
        plt.plot(self.enqueue_ts_array, self.queue_len_array)
        plt.xlabel('enqueue timestamp')
        plt.ylabel('enqueue queue length')
        plt.title('Queue Length with Time')
        plt.savefig(os.path.join('fig', 'QueueLength.png'))
        plt.close()

    def output_queue_length(self):
        csv_file = open('queue.csv', 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        for i in range(0, self.pkt_num):
            resultWriter.writerow([self.enqueue_ts_array[i], self.queue_len_array[i]])
        csv_file.close()


    def top(self, ts, te, K=0):
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
        ret = []  # {FID}
        for (index, t) in enumerate(self.dequeue_ts_array):
            if ts <= t and t <= te:
                ret.append(self.FID_array[index])
        return ret

    def draw_top(self, ts, te, K=10):
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
        plt.savefig(os.path.join('fig', bar_title + '.png'))
        plt.close()


    def draw_total_distribution(self, ts, te, n_period=100):
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
        csv_file = open('flow.csv', 'w')
        resultWriter = csv.writer(csv_file, dialect='excel-tab')
        for i in range(0, len(period)):
            resultWriter.writerow([period[i], total_pkt[i]])
        csv_file.close()

        # draw
        print("plotting traffic...")
        plt.xlabel('enqueue timestamp')
        plt.ylabel('total packet number')
        plot_title = "Total Traffic with Time"
        plt.title(plot_title)
        plt.plot(period, total_pkt)
        plt.savefig(os.path.join('fig', plot_title + '.png'))
        plt.close()


    def draw_top_flow_distribution(self, n_period=100, K=10):
        ret = self.top(self.first_ets, self.last_ets, K)
        self.draw_flow_distribution(n_period, ret.keys())


    def draw_flow_distribution(self, n_period=100, filter_list=[]):
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
        plt.savefig(os.path.join('fig', plot_title + '.png'))
        plt.close()

if __name__ == '__main__':
    # tw = TimeWindowController(path='../test/tw_data', alpha=1, k=12, T=5, TW0_TB=6, TW0_z=64 / 100)
    gt = GroundTruth('../test')
    # gt.output_queue_length()

    # exp1
    # csv_file = open('packet2.csv', 'w')
    # resultWriter = csv.writer(csv_file, dialect='excel-tab')
    # pkts = gt.packet_experiencing_high_delay(5000)
    # pkts_number = len(pkts)
    # sample_pkts = []
    # sample_pkts_ids = []
    # hash_list = HashFunction()
    # while len(sample_pkts_ids) < 2000:
    #     id = random.randint(0, pkts_number-1)
    #     if id not in sample_pkts_ids:
    #         sample_pkts_ids.append(id)
    #         sample_pkts.append(pkts[id])
    # idx = 0
    # for pkt in sample_pkts:
    #     pkt['gt'] = gt.retrieve(pkt['ets'], pkt['dts'])
    #     pkt['tw'], sts, lts = tw.retrieve(pkt['ets'], pkt['dts'])
    #     if pkt['tw']:
    #         p,r = precision_and_recall_packet_number(pkt['gt'],pkt['tw'])
    #         print('P: {0}, R: {1}'.format(p,r))
    #         gt_pkt = gt.retrieve(sts, lts)
    #         proportion = (pkt['dts'] - pkt['ets']) / (lts - sts)
    #
    #         ret = Count_Min(hash_list, gt_pkt, pkt['gt'], 3,  1024)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         CM1_p, CM1_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("Count-Min Sketch: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(CM1_p, CM1_r))
    #
    #         ret = Count_Min(hash_list, gt_pkt, pkt['gt'], 5,  4096)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         CM2_p, CM2_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("Count-Min Sketch: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(CM2_p, CM2_r))
    #
    #         traces = gt.traces(sts,lts)
    #         ret = hash_pipe(hash_list, traces, 2, 512)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         HP1_p, HP1_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("HashPipe: 512 x 2, Number Precision: {0}, Number Recall: {1}".format(HP1_p, HP1_r))
    #
    #         ret = hash_pipe(hash_list, traces, 5, 4096)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         HP2_p, HP2_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("HashPipe: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(HP2_p, HP2_r))
    #
    #         ret = Flow_Radar(hash_list, gt_pkt, 1024*3)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         FR1_p, FR1_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("FlowRadar: 1024 x 3, Number Precision: {0}, Number Recall: {1}".format(FR1_p, FR1_r))
    #
    #         ret = Flow_Radar(hash_list,gt_pkt, 4096*5)
    #         for key, val in ret.items():
    #             ret[key] = int(val * proportion)
    #         FR2_p, FR2_r = precision_and_recall_packet_number(pkt['gt'], ret)
    #         print("FlowRadar: 4096 x 5, Number Precision: {0}, Number Recall: {1}".format(FR2_p, FR2_r))
    #
    #         resultWriter.writerow([idx, pkt['ets'], pkt['dts'], pkt['qlen'], p, r, CM1_p, CM1_r, CM2_p, CM2_r, HP1_p, HP1_r, HP2_p, HP2_r, FR1_p, FR1_r, FR2_p, FR2_r])
    #         idx += 1
    # csv_file.close()




