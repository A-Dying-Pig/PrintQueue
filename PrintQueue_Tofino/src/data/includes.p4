/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Header, Constant, Metadata Definition.
 */

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

header_type register_metadata_t{
    fields{
        half: 16;
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

header_type TW_metadata_t {
    fields {
        src_addr: 32;
        dst_addr: 32;
        src_port: 16;
        dst_port: 16;
        idx : 16;
        tts : 32;
        tts_pre_cycle : 32;
        tts_delta : 32;
        tts_r: 32;
        half_index_num: 16;
        b1: 1;
        b2: 1;
    }
}

header_type QM_matadata_t{
    fields{
        src_addr: 32;
        dst_addr: 32;
        src_port: 16;
        dst_port: 16;
        seq_mask: 32;
        seq_num: 32;
        seq_idx: 32;
        flow_idx: 16;
        stack_len_change: 1;
    }
}

// constant value definition
#define ETHERTYPE_VLAN          0x8100
#define ETHERTYPE_IPV4          0x0800
#define ETHERTYPE_IPV6          0x86dd
#define ETHERTYPE_ARP           0x0806
#define ETHERTYPE_RARP          0x8035
#define ETHERTYPE_NSH           0x894f
#define ETHERTYPE_PRINTQUEUE    0x080c
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


#define TW0_TB 6
#define INDEX_NUM 8192
#define HALF_INDEX_NUM 4096
#define HALF_INDEX_BIT 12
#define HALF_INDEX_MASK 0xfff
#define ALPHA 2
#define INGRESS_PROCESSING_TIME 47

#define MAX_QUEUE_DEPTH 32768 // 2^15
#define TOTAL_SEQ_NUM 65536  // 2^16
#define HALF_SEQ_NUM 32768
#define HALF_SEQ_BIT 15
#define HALF_SEQ_MASK 0x7fff

#endif
