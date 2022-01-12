'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    Tofino Control Plane Settings
'''

from collections import OrderedDict

import time
import sys
import logging
import copy
import pdb
import csv

import unittest
import random

import pd_base_tests

from ptf import config
from ptf.testutils import *
from ptf.thriftutils import *

import os

from printqueue.p4_pd_rpc.ttypes import *
from printqueue.p4_pd_rpc.printqueue import *


from conn_mgr_pd_rpc.ttypes import *
from mc_pd_rpc.ttypes import *
from res_pd_rpc.ttypes import *
from devport_mgr_pd_rpc.ttypes import *
from ptf_port import *
from mirror_pd_rpc.ttypes import *

import inspect


dev_id = 0
PROGRAM_NAME = 'printqueue'
DROP_PORT = 129


def make_port(pipe, local_port):
    assert pipe >= 0 and pipe < 4                            # 4 pipes in total
    assert local_port >= 0 and local_port < 72
    return pipe << 7 | local_port                            # _pipe_idx | local port

def portToPipe(port):
    return port >> 7

def portToPipeLocalId(port):
    return port & 0x7F

def portToBitIdx(port):
    pipe = portToPipe(port)
    index = portToPipeLocalId(port)
    return 72 * pipe + index

def set_port_map(indicies):
    bit_map = [0] * ((288+7)/8)
    for i in indicies:
        index = portToBitIdx(i)
        bit_map[index/8] = (bit_map[index/8] | (1 << (index%8))) & 0xFF
    return bytes_to_string(bit_map)

def set_lag_map(indicies):
    bit_map = [0] * ((256+7)/8)
    for i in indicies:
        bit_map[i/8] = (bit_map[i/8] | (1 << (i%8))) & 0xFF
    return bytes_to_string(bit_map)


# SETTINGS of TIME WINDOW
alpha = 1
k = 12
T = 5
TW0_TB = 6
TW0_z = 1
index_number_per_window = 2**k
total_duration = int((2**(alpha*T) - 1) / (2**alpha - 1) * 2**(TW0_TB + k))


class PollTimeWindows(pd_base_tests.ThriftInterfaceDataPlane):
    def __init__(self):
        print("Alpha: %d, T: %d, k: %d, total_duration: %d"%(alpha, T, k, total_duration))
        pd_base_tests.ThriftInterfaceDataPlane.__init__(self, [PROGRAM_NAME])
        self.half = 1
        self.total_duration_us = total_duration / 1e3
        self.TW_registers = [] # [[{FID: hex, tts:}]]
        self.poll_duration = 1e6

    def setUp(self):
        pd_base_tests.ThriftInterfaceDataPlane.setUp(self)      
        self.sess_hdl = self.conn_mgr.client_init()
        self.dev_tgt = DevTarget_t(dev_id, hex_to_i16(0xFFFF))
        self.flags = printqueue_register_flags_t(read_hw_sync = True)


    def set_first_half_bit(self):
        param = self.half << k
        action_spec = printqueue_prepare_TW0_action_spec_t(param)
        self.client.prepare_TW0_tb_set_default_action_prepare_TW0(self.sess_hdl, self.dev_tgt, action_spec)
        self.conn_mgr.complete_operations(self.sess_hdl)
        self.half ^= 0x01 


    def pollTimeWindows(self, TWid, half):
        s = half << k
        n = 1 << k
        tts_str = "self.client.register_range_read_TW%d_tts_r(self.sess_hdl, self.dev_tgt, %d, %d, self.flags)" % (TWid, s, n)
        src_ip_str = "self.client.register_range_read_TW%d_src_ip_r(self.sess_hdl, self.dev_tgt, %d, %d, self.flags)" % (TWid, s, n)
        dst_ip_str = "self.client.register_range_read_TW%d_dst_ip_r(self.sess_hdl, self.dev_tgt, %d, %d, self.flags)" % (TWid, s, n)
        src_port_str = "self.client.register_range_read_TW%d_src_port_r(self.sess_hdl, self.dev_tgt, %d, %d, self.flags)" % (TWid, s, n)
        dst_port_str = "self.client.register_range_read_TW%d_dst_port_r(self.sess_hdl, self.dev_tgt, %d, %d, self.flags)" % (TWid, s, n)
        tts = eval(tts_str)
        self.conn_mgr.complete_operations(self.sess_hdl)
        src_ip = eval(src_ip_str)
        self.conn_mgr.complete_operations(self.sess_hdl)
        dst_ip = eval(dst_ip_str)
        self.conn_mgr.complete_operations(self.sess_hdl)
        src_port = eval(src_port_str)
        self.conn_mgr.complete_operations(self.sess_hdl)
        dst_port = eval(dst_port_str)
        self.conn_mgr.complete_operations(self.sess_hdl)
        return {'tts': tts, 'src_ip': src_ip, 'dst_ip': dst_ip, 'src_port':src_port, 'dst_port': dst_port}


    def runTest(self):
        start = time.time() * 1e6
        poll_duration = 0
        poll_s = 0
        poll_e = 0
        while True:
            if poll_duration >= self.total_duration_us:
                TW_registers = []
                self.set_first_half_bit()
                poll_s = time.time() * 1e6
                for i in range(0, T):
                    TW_registers.append(self.pollTimeWindows(i, self.half))
                with open('./src/control/read_flip/data/%ld.json'%(poll_s), 'w') as f:
                    json.dump(TW_registers, f, indent=4)  
            poll_e = time.time() * 1e6
            poll_duration = poll_e - poll_s
            if poll_e - start >= self.poll_duration:
                break


    # def runTest(self):
    #     ret = self.client.register_range_read_TW0_tts_r(self.sess_hdl, self.dev_tgt, 0, 1, self.flags)
    #     print(len(ret))
    #     print(ret)
    #     ret2 = self.client.register_read_TW0_tts_r(self.sess_hdl, self.dev_tgt, 0, self.flags)
    #     print(ret2)
    #     TW_registers = []
    #     for i in range(0, T):
    #         TW_registers.append(self.pollTimeWindows(i, self.half))
    #     with open('./src/control/read_flip/data/%ld.json'%(time.time() * 1e6), 'w') as f:
    #         json.dump(TW_registers, f, indent=4)  
    

    def tearDown(self):
        print("Closing!")
        self.conn_mgr.client_cleanup(self.sess_hdl)
        print("Closed Session %d" % self.sess_hdl)
        pd_base_tests.ThriftInterfaceDataPlane.tearDown(self)
