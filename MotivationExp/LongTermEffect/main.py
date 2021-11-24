import numpy as np
from matplotlib import pyplot as plt
import time
import queue
import random


def ts():
    # microsecond level timestamp, but consider it nanosecond level
    return int(time.time() * 1000000)


class Packet:
    def __init__(self, ID):
        self.flowID = ID
        self.arr_ts = ts()
        self.enq_ts = None
        self.deq_ts = None
        self.drop_ts = None


class FIFO:
    def __init__(self, q_cap, p_cap):
        self.queue_capacity = q_cap
        self.process_capacity = p_cap #constant time processing, microseconds
        self.bias = 20
        self.drop_num = 0
        self.enq_num = 0
        self.deq_num = 0
        self.q = queue.Queue(q_cap)
        self.deq_ts = 0

    def enqueue(self, pkt):
        if self.q.qsize() < self.queue_capacity:
            # print('enq: {0}'.format(self.q.qsize()))
            if self.q.empty():
                self.deq_ts = ts() + self.process_time()
                # print('enq deq ts: ' + str(self.deq_ts))
            self.q.put(pkt)
            pkt.enq_ts = ts()
            self.enq_num += 1
        else:
            pkt.drop_ts = ts()
            self.drop_num += 1

    def dequeue(self):
        pkt = None
        if not self.q.empty():
            # print('deq: {0}'.format(self.q.qsize()))
            pkt = self.q.get()
            self.deq_num += 1
            if not self.q.empty():
                self.deq_ts = ts() + self.process_time()
                # print('deq ts: ' + str(self.deq_ts))
        return pkt

    def process_time(self):
        return int(self.process_capacity + random.uniform(-self.bias, self.bias))

    def preload(self, num):
        for i in range(0, num):
            temp = Packet(0)
            if self.q.qsize() < self.queue_capacity:
                self.q.put(temp)
                temp.enq_ts = ts()



def simulate():
    fifo = FIFO(4096, 2000)
    f_s = [ts(), ts(), ts()]
    total_duration = 10000000
    sample_interval = 10000
    data = np.zeros((5, int(total_duration/sample_interval)+10))
    flow_counter = [0,0,0]
    data_num = 0
    st_interval = 0
    st = ts()
    cur = ts()

    f1_enq = 0
    f2_enq = 0
    deq = 0
    while cur - st < total_duration:
        cur = ts()
        if cur > fifo.deq_ts:
            fifo.dequeue()
            deq += 1
        if cur > f_s[0]:
            # generate flow 1 pkt
            flow_counter[0] += 1
            fifo.enqueue(Packet(1))
            f_s[0] = ts() + np.random.poisson(3000)  # flow 1 6000 us
            # print('f1 ts: '+ str(f_s[0]))
            f1_enq += 1
        if cur > f_s[1]:
            # generate flow 2 pkt
            flow_counter[1] += 1
            fifo.enqueue(Packet(2))
            f_s[1] = ts() + np.random.poisson(3000)  # flow 2 3000 us
            # print('f2 ts: '+ str(f_s[0]))
            f2_enq += 1
        #collect data
        if cur - st_interval > sample_interval:
            data[0, data_num] = cur - st
            data[1, data_num] = fifo.q.qsize()
            data[2, data_num] = 1514 * flow_counter[0] * 1e9 / sample_interval / 1e6  #flow 1 size: MB
            data[3, data_num] = 1514 * flow_counter[1] * 1e9 / sample_interval / 1e6  #flow 2 size: MB
            flow_counter = [0,0,0]
            st_interval = cur
            data_num += 1
    print('f1 enq: {0}, f2 enq: {1}, deq: {2}'.format(f1_enq,f2_enq,deq))
    print('FIFO enq: {0}, deq: {1}, drop: {2}'.format(fifo.enq_num,fifo.deq_num,fifo.drop_num))
    plt.title("Queue Length")
    plt.xlabel("Time (ms)")
    plt.ylabel("Queue Length")
    plt.ylim((0, fifo.queue_capacity))
    plt.plot(data[0,0:data_num]/1e6, data[1,0:data_num])
    plt.show()

if __name__ == '__main__':
    simulate()
