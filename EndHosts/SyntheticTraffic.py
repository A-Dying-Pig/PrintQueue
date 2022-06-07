import random
import time
from scapy.all import *
from scapy.utils import wrpcap
import math
from scipy.stats import uniform, norm, poisson, expon
import matplotlib.pyplot as plt
import numpy as np
import string


class SyntheticTraffic:
    def __init__(self):
        # flow size is in KB
        self.ws_flows = self.generate_flows_by_CDF_sample([[0.15, 6], [0.2, 13], [0.3, 19],
                                                           [0.4, 33], [0.53, 53], [0.6, 133],
                                                           [0.7, 667], [0.8, 1333], [0.9, 3333],
                                                           [0.97, 6667], [1, 20000]], 100)
        self.dm_flows = self.generate_flows_by_CDF_sample([[0.5, 1], [0.6, 2], [0.7, 3], [0.8, 7],
                                                           [0.9, 267], [0.95, 2107], [0.99, 66667], [1, 666667]], 100)
        ws_avg = 0
        for f in self.ws_flows:
            ws_avg += f['size']
        ws_avg = ws_avg / len(self.ws_flows)
        print("The average bytes of flows in web search trace : {0} B".format(ws_avg))
        dm_avg = 0
        for f in self.dm_flows:
            dm_avg += f['size']
        dm_avg = dm_avg / len(self.dm_flows)
        print("The average bytes of flows in data mining trace : {0} B".format(dm_avg))
        pass

    def generate_flows_by_CDF_sample(self, cdf_sample, f_num=100):
        """
        generate flows according to samples of cdf
        :cdf_sample: [[int(cdf value), int(flow size)]], cdf value are listed in the ascending order
        :f_num: the number of generated flows
        :return: [{'id': int, 'size': int}]
        """
        ret = []
        c = 0
        for pt in cdf_sample:
            sample_n = math.floor(pt[0] * f_num)
            while c <= sample_n:
                ret.append({'id': c, 'size': pt[1] * 1024, 'pn': math.ceil((pt[1] * 1024) / 1046)})
                c += 1
        return ret

    def generate_trace(self, duration, warmup, fset, target):
        '''
        :warmup: the period when all flows start to transmit
        :duration: the duration of the trace, in second
        :fset: flow set - [{'id': int, 'size': int, 'pn': int}]
        :target: target bandwidth - in GB
        '''
        avg_size = 0
        for f in fset:
            avg_size += f['size']
        avg_size = avg_size / len(fset)
        fn = math.ceil(duration * target * 1024 * 1024 * 1024 / avg_size)
        trace = []
        # flows arrive according to a poisson process with warmup period, inter flow is an exponential distribution
        avg_flow_inter = warmup / (fn - 1) # in second
        flow_inter = expon.rvs(scale=avg_flow_inter, size=fn - 1)
        flow_inter = np.append([0], flow_inter)
        t = 0
        print("Set flows and packets...")
        for i in range(0, fn):
            sample_id = random.randint(0, len(fset) - 1)
            flow = {'id': fset[sample_id]['id'], 'pn': fset[sample_id]['pn']}
            # generate flow ID
            src_ip = ".".join([str(random.randint(1, 255)) for i in range(0, 4)])
            dst_ip = ".".join([str(random.randint(1, 255)) for i in range(0, 4)])
            src_port = random.randint(10000, 65536)
            dst_port = random.randint(10000, 65536)
            flow['src_ip'] = src_ip
            flow['dst_ip'] = dst_ip
            flow['src_port'] = src_port
            flow['dst_port'] = dst_port
            t += flow_inter[i]
            flow['start_ts'] = t
            # now deal with packets
            if flow['pn'] > 1:
                avg_pkt_interval = (duration - flow['start_ts']) / (flow['pn'] - 1)
                inters = [expon.rvs(scale=avg_pkt_interval, size=flow['pn'] - 1),
                          np.array([avg_pkt_interval for i in range(0, flow['pn'] - 1)])]
                chosen_inter = inters[random.randint(0, 1)]
                pkt_ts = [flow['start_ts']]
                pkt_t = flow['start_ts']
                for delta in chosen_inter:
                    pkt_t += delta
                    pkt_ts.append(pkt_t)
                flow['pkt_ts'] = np.array(pkt_ts)
            else:
                flow['pkt_ts'] = np.array([flow['start_ts']])
            trace.append(flow)
        # generate trace
        print("Sorting all packets...")
        trace_pkt = []
        for flow in trace:
            for ts in flow['pkt_ts']:
                trace_pkt.append({'src_ip': flow['src_ip'], 'dst_ip': flow['dst_ip'], 'src_port': flow['src_port'], 'dst_port': flow['dst_port'], 'ts': ts})
        trace_pkt.sort(key=lambda p : p['ts'])
        letters = string.ascii_letters + string.digits
        lorem = ''.join(random.choice(letters) for i in range(int(1e6)))
        pkts = []
        print("Generating pcap...")
        for pkt in trace_pkt:
            beg = random.randint(0, 1000000 - 1448)
            p = Ether() / IP(src=pkt['src_ip'], dst=pkt['dst_ip']) / TCP(sport=pkt['src_port'], dport=pkt['dst_port']) / lorem[beg:beg + 1448] # leave 12 bytes for int header, not exceed MTU
            p.time = pkt['ts']
            pkts.append(p)
        print("Saving pcap files...")
        wrpcap('./workloads/syn4_{0}.pcap'.format(len(trace_pkt)), pkts)


if __name__ == '__main__':
    trace = SyntheticTraffic()
    trace.generate_trace(0.1, 0.025, trace.ws_flows, 3)
    trace.generate_trace(0.1, 0.025, trace.dm_flows, 3)
