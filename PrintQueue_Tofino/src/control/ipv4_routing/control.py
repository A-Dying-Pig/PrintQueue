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
import pathlib

import pd_base_tests

from ptf import config
from ptf.testutils import *
from ptf.thriftutils import *

import os

from printqueue.p4_pd_rpc.ttypes import *


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
IP_PROTOCOLS_TCP = 6


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

def read_csv_table(file_name):
    ret = []
    with open(file_name) as f:
        print('Table Name:' + file_name)
        csv_reader = csv.reader(f, delimiter=',')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                line_count += 1
            else:
                n_row = []
                for c in row:
                    if '.' not in c:
                        n_row.append(int(c))
                    else:
                        n_row.append(c.strip())
                ret.append(n_row)
                line_count += 1
    print('Processed ' +  str(line_count) +  ' lines.')
    return ret

print(pathlib.Path().resolve())
ipv4_routing_tb = read_csv_table('./src/control/ipv4_routing/routing.csv')
k = 12

class PopulateTables(pd_base_tests.ThriftInterfaceDataPlane):
    def __init__(self):
        self.half = 0
        pd_base_tests.ThriftInterfaceDataPlane.__init__(self, [PROGRAM_NAME])

    def setUp(self):
        pd_base_tests.ThriftInterfaceDataPlane.setUp(self)      
        self.sess_hdl = self.conn_mgr.client_init()
        self.dev_tgt = DevTarget_t(dev_id, hex_to_i16(0xFFFF))
        self.entries = {}

    def set_first_half_bit(self):
        param = self.half << k
        action_spec = printqueue_prepare_TW0_action_spec_t(param)
        self.client.prepare_TW0_tb_set_default_action_prepare_TW0(self.sess_hdl, self.dev_tgt, action_spec)
        self.conn_mgr.complete_operations(self.sess_hdl)
        self.half ^= 0x01 
        

    def addTableEntry(self, table_name, action_name, match_fields, action_parameters, priority=None):
        command_str = "%s_%s_match_spec_t" % (PROGRAM_NAME, table_name)
        match_spec = eval(command_str)(*match_fields)
        action_spec = None
        if len(action_parameters) > 0:
            command_str = "%s_%s_action_spec_t" % (PROGRAM_NAME, action_name)
            action_spec = eval(command_str)(*action_parameters)

        if action_spec is None:
            if priority is None:
                command_str = "self.client.%s_table_add_with_%s(self.sess_hdl, self.dev_tgt, match_spec)" % (
                    table_name, action_name)
            else:
                command_str = "self.client.%s_table_add_with_%s(self.sess_hdl, self.dev_tgt, match_spec, %d)" % (
                    table_name, action_name, priority)
        else:
            if priority is None:
                command_str = "self.client.%s_table_add_with_%s(self.sess_hdl, self.dev_tgt, match_spec, action_spec)" % (
                    table_name, action_name)
            else:
                command_str = "self.client.%s_table_add_with_%s(self.sess_hdl, self.dev_tgt, match_spec, action_spec, %d)" % (
                    table_name, action_name, priority)

        if table_name not in self.entries:
            self.entries[table_name] = []
        self.entries[table_name].append(eval(command_str))
        self.conn_mgr.complete_operations(self.sess_hdl)

    def configRouting(self):
        for e in ipv4_routing_tb:
            self.addTableEntry('ipv4_routing','pkt_forward',(ipv4Addr_to_i32(e[0]),e[1]),(e[2],))

    def runTest(self):
        self.set_first_half_bit()
        self.configRouting()
    
    def tearDown(self):
        print("Closing!")
        self.conn_mgr.client_cleanup(self.sess_hdl)
        print("Closed Session %d" % self.sess_hdl)
        pd_base_tests.ThriftInterfaceDataPlane.tearDown(self)