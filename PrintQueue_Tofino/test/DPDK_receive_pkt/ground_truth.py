import os
import matplotlib.pyplot as plt

class GroundTruth:
    def __init__(self):
        self.pkt_num = 0
        self.total_duration = 0
        self.dequeue_ts_array = []
        self.queue_len_array = []
        self.FID_array = []   # port value is big endian
        self.sum_interval = 0
        self.sum_queue_len = 0
        self.average_interval = 0
        self.average_queue_len = 0
        self.first_dts = 0
        self.last_dts = 0
        files = []
        for (root, dirs, fs) in os.walk('data'):
            sorted(fs)
            files = [os.path.join(root, f) for f in fs]
        base = 0
        for f in files:
                print("loading file: {0}".format(f))
                with open(f, 'rb') as fptr:
                    chunk = fptr.read(20)
                    p_dqts = int.from_bytes(chunk[0:4], 'little') + base
                    p_qlen = int.from_bytes(chunk[4:8], 'little')
                    p_FID = chunk[8:20].hex()
                    if self.first_dts == 0:
                        self.first_dts = p_dqts
                    self.last_dts = p_dqts
                    self.dequeue_ts_array.append(p_dqts)
                    self.queue_len_array.append(p_qlen)
                    self.FID_array.append(p_FID)
                    self.pkt_num += 1
                    self.sum_queue_len += p_qlen
                    chunk = fptr.read(20)
                    while chunk:
                        dqts = int.from_bytes(chunk[0:4], 'little') + base
                        qlen = int.from_bytes(chunk[4:8], 'little')
                        FID = chunk[8:20].hex()
                        if dqts < p_dqts:
                            base += (1 << 32)
                            dqts += (1 << 32)
                        self.sum_interval += dqts - p_dqts
                        self.dequeue_ts_array.append(dqts)
                        self.queue_len_array.append(qlen)
                        self.FID_array.append(FID)
                        self.pkt_num += 1
                        self.sum_queue_len += qlen
                        p_dqts = dqts
                        p_qlen = qlen
                        self.last_dts = dqts
                        chunk = fptr.read(20)
        self.average_interval = self.sum_interval / (self.pkt_num - 1)
        self.average_queue_len = self.sum_queue_len / self.pkt_num
        self.total_duration = self.last_dts - self.first_dts
        print('Packet number {0}, total duration: {1} nanoseconds, average queue length: {2}, average interval: {3}'
              .format(self.pkt_num, self.total_duration, self.average_queue_len, self.average_interval))
        # self.draw_flow_distribution()
        self.draw_top(self.first_dts, self.last_dts)
        self.draw_top_flow_distribution(K=5)

    def draw_queue_length(self):
        print("plotting queue length...")
        plt.plot(self.dequeue_ts_array, self.queue_len_array)
        plt.xlabel('dequeue timestamp')
        plt.ylabel('queue length')
        plt.title('Queue Length with Time')
        plt.savefig(os.path.join('fig', 'QueueLength.png'))
        plt.close()

    def top(self, ts, te, K = 0):
        # return a sorted list in descending order
        ret = {} # {FID: NUMBER}
        for (index, t) in enumerate(self.dequeue_ts_array):
            if ts <= t and t <= te:
                ret[self.FID_array[index]] = ret.get(self.FID_array[index], 0) + 1
        ret = dict(sorted(ret.items(), key=lambda item: item[1], reverse= True))
        if K == 0:
            return ret
        K = min(K, len(ret))
        return dict(list(ret.items())[0 : K])

    def draw_top(self, ts, te, K = 10):
        ret = self.top(ts, te)
        K = min(K, len(ret))
        ret = list(ret.items())[0 : K]
        print("plotting top {0} flows from {1} to {2}".format(K, ts, te))
        flow_ids = []
        pkt_num = []
        for (key,val) in ret:
            flow_ids.append(key)
            pkt_num.append(val)
        plt.bar(flow_ids, pkt_num)
        plt.xlabel('flow ID')
        plt.ylabel('packet number')
        bar_title = "top {0} flows from {1} to {2}".format(K, ts, te)
        plt.title(bar_title)
        plt.xticks(rotation=-15)
        plt.tight_layout()
        plt.savefig(os.path.join('fig', bar_title + '.png'))
        plt.close()

    def draw_top_flow_distribution(self, n_period = 100, K = 10):
        ret = self.top(self.first_dts,self.last_dts,K)
        self.draw_flow_distribution(n_period, ret.keys())

    def draw_flow_distribution(self, n_period = 100, filter_list=[]):
        # only draw flows in the list
        if filter_list == []:
            is_filter = False
        else:
            is_filter = True
        period_len = self.total_duration / n_period
        pkt_per_period = {} #{FID1: [], FID2:[]}
        period = []
        t = int(self.first_dts + period_len / 2)
        new_one_len = 0
        prev_index = 0
        while t < self.last_dts:
            period.append(t)
            ts = int(t - period_len / 2)
            te = int(t + period_len / 2)
            tmp = {} # {FID: number, FID: number}
            index = prev_index
            while index < len(self.dequeue_ts_array):
                if self.dequeue_ts_array[index] < te:
                    tmp[self.FID_array[index]] = tmp.get(self.FID_array[index], 0) + 1
                    prev_index += 1
                    index += 1
                else:
                    break
            for (key, value) in pkt_per_period.items():
                value.append(tmp.get(key,0))
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
        plt.xlabel('dequeue timestamp')
        plt.ylabel('packet number')
        plt.title('Flow Size with Time')
        for (flow, flow_number) in pkt_per_period.items():
            plt.plot(period, flow_number)
            # plt.hold(True)
        plt.savefig(os.path.join('fig', 'FlowSize.png'))
        plt.close()

if __name__ == '__main__':
    gt = GroundTruth()