/*************************************************************************
	> File Name: includes.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description: Header and metadata definition of PrintQueue
*************************************************************************/

#ifndef _INCLUDES_H_
#define _INCLUDES_H_

// tofino headers
#include <tofino/intrinsic_metadata.p4>
#include <tofino/stateful_alu_blackbox.p4>
#include <tofino/constants.p4>

// header definition
header_type ethernet_t {
    fields {
        dst_addr : 48;
        src_addr : 48;
        ether_type : 16;
    }
}

header_type ipv4_t {
    fields {
        version : 4;
        ihl : 4;
        diffserv : 8;
        total_len : 16;
        identification : 16;
        flags : 3;
        frag_offset : 13;
        ttl : 8;
        protocol : 8;
        checksum : 16;
        src_addr : 32;
        dst_addr: 32;
    }
}


header_type tcp_t {
    fields {
        src_port : 16;
        dst_port : 16;
        seq_no : 32;
        ack_no : 32;
        data_offset : 4;
        res : 3;
        ecn : 3;
        ctrl : 6;
        window : 16;
        checksum : 16;
        urgent_ptr : 16;
    }
}

// two bits to control 4 sets of registers
header_type register_metadata_t{
    fields{
        isolation_prefix: 32;
        highest: 32;    
        second_highest: 32; 
    }
}

header_type int_t {
    fields {
        dequeue_ts : 32;
        enqueue_ts : 32;
        enq_qdepth : 32;
    }
}

header_type vlan_tag_t {
    fields {
        pri     : 3;
        cfi     : 1;
        vlan_id : 12;
        etherType : 16;
    }
}

// data plane query can be triggerd by the probe header
header_type printqueue_probe_t{
    fields {
        qdepth_threshold: 32;
    }
}

header_type printqueue_signal_t{
    fields{
        signal_type: 16;
        isolation_id: 16;
        pkt_enqueue_ts: 32;
        pkt_dequeue_ts: 32;
    }
}

// printqueue metadata
header_type PQ_metadata_t {
    fields{
        qdepth_threshold: 32;
        pkt_enqueue_ts: 32;
        pkt_dequeue_ts: 32;
        mirror_signal: 32;  // Bitmap: bit 0 = QM data plane query; bit 1 = QM seq overflow; bit 2 = TW data plane query
        lock: 16;
        isolation_id: 16;
        disable_PQ: 16;
        probe: 1;
        exceed: 1;
        stack_len_change: 1;
        forward: 1;
    }
}

// time window metadata
header_type TW_metadata_t {
    fields {
        src_addr: 32;
        dst_addr: 32;
        src_port: 16;
        dst_port: 16;
        idx : 32;
        tts : 32;
        tts_pre_cycle : 32;     // the tts of the previous cycle
        tts_delta : 32;
        tts_r: 32;              // tts value of the register
        single_port_index_num: 16;
        b1: 1;
        b2: 1;
    }
}

//queue monitor metadata
header_type QM_matadata_t{
    fields{
        src_addr: 32;
        dst_addr: 32;
        src_port: 16;
        dst_port: 16;
        idx: 32;
        seq_num: 32;
    }
}

// constant value definition
#define ETHERTYPE_VLAN          0x8100
#define ETHERTYPE_IPV4          0x0800
#define ETHERTYPE_IPV6          0x86dd
#define ETHERTYPE_ARP           0x0806
#define ETHERTYPE_RARP          0x8035
#define ETHERTYPE_NSH           0x894f
#define ETHERTYPE_PRINTQUEUE    0x080c          // used for transmit INT data
#define ETHERTYPE_PRINTQUEUE_PROBE    0x080d    // a probe packet may trigger data plane query
#define ETHERTYPE_PRINTQUEUE_SIGNAL   0x080e
#define ETHERTYPE_NEVER         0xffff

#define IP_PROTOCOLS_ICMP              1
#define IP_PROTOCOLS_IGMP              2
#define IP_PROTOCOLS_IPV4              4
#define IP_PROTOCOLS_TCP               6
#define IP_PROTOCOLS_UDP               17
#define IP_PROTOCOLS_IPV6              41
#define IP_PROTOCOLS_SR                43
#define IP_PROTOCOLS_GRE               47
#define IP_PROTOCOLS_IPSEC_ESP         50
#define IP_PROTOCOLS_IPSEC_AH          51
#define IP_PROTOCOLS_ICMPV6            58
#define IP_PROTOCOLS_EIGRP             88
#define IP_PROTOCOLS_OSPF              89
#define IP_PROTOCOLS_ETHERIP           97
#define IP_PROTOCOLS_PIM               103
#define IP_PROTOCOLS_VRRP              112

#define ICMP_TYPE_ECHO_REPLY                0
#define ICMP_TYPE_ECHO_REQUEST              8


#define S101_PORT  128
#define S102_PORT  130
#define S103_PORT  136
#define S104_PORT  138
#define S105_PORT  152
#define S106_PORT  106
#define DROP_PORT  129
#define ROUTING_FLOW_NUMBER         1024   // 1K possible IPv4 prefixes

//---------------------------------------//
//          Adjustable Parameters        //
//---------------------------------------//
//NOTICE: when changing the parameters, remember to change the parameters of the control plane program
#define ALPHA 1
#define TW0_TB 10
#define INDEX_NUM 16384                 // extra space for periodical and data plane query
#define HALF_INDEX_NUM 8192
// for a single port, cell number of a time window
#define SINGLE_PORT_INDEX_NUM 4096
#define SINGLE_PORT_INDEX_BIT 12
#define SIGNLE_PORT_INDEX_MASK 0xfff
//------------------------------------------------------------------------//
//   The nanoseconds that a packet experiences in the ingress pipeline    //
//------------------------------------------------------------------------//
// The value is based on the machine and codes.
// To get this value:
// 1. check the total ingress pipeline cycles in '$SDE/pkgsrc/p4-build/tofino/printqueue/logs/mau.config.log' after compiling PrintQueue
// 2. calculate duration with the chip frequency, e.g. 1.22 GHz 
#define INGRESS_PROCESSING_TIME 47      

#define HALF_QDEPTH 65536 // 2^16 = 65536
#define TOTAL_QDEPTH 131072 // 2^17 = 131072    // extra space for periodical and data plane query
// for a single port, stack depth of a queue monitor
#define SINGLE_PORT_QM_INDEX_NUM 32768
#define SINGLE_PORT_QM_INDEX_BIT 15
#define SINGLE_PORT_QM_INDEX_MASK 0x7fff

#define DEFAULT_QDEPTH_THRESHOLD 10000
#define THRESHOLD_FLOW_NUMBER 1024
#define MIRROR_SESS 3   // mirror session number for clone_e2e
#define MAX_PORT_NUM 16

#endif
