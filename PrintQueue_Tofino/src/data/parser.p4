/*************************************************************************
	> File Name: parser.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description: Packet parser of the PrintQueue.
*************************************************************************/

#ifndef _PARSER_H_
#define _PARSER_H_

#include "includes.p4"

parser_exception protocol_not_supported {
    parser_drop ;
}

parser start {
    return parse_ethernet;
}

header ethernet_t ethernet;
parser parse_ethernet {
    extract(ethernet);
    return select(latest.ether_type) {
        ETHERTYPE_VLAN : parse_vlan_tag;
        ETHERTYPE_IPV4 : parse_ipv4;
        ETHERTYPE_PRINTQUEUE: parse_ipv4_int;                 // the type contain INT header after ethernet, ipv4, tcp header
        ETHERTYPE_PRINTQUEUE_PROBE: parse_printqueue_probe;   // the type contain probe header after ethernet, ipv4, tcp header
        ETHERTYPE_PRINTQUEUE_SIGNAL: parse_printqueue_signal; // the type contain signal header after ethernet, ipv4, tcp header
        default: parse_error protocol_not_supported;
    }
}

header vlan_tag_t vlan_tag;
parser parse_vlan_tag {
    extract(vlan_tag);
    return select(latest.etherType) {
        ETHERTYPE_IPV4 : parse_ipv4;
        ETHERTYPE_PRINTQUEUE: parse_ipv4_int;
        ETHERTYPE_PRINTQUEUE_PROBE: parse_printqueue_probe;
        ETHERTYPE_PRINTQUEUE_SIGNAL: parse_printqueue_signal;
        default: parse_error protocol_not_supported;
    }
}

header ipv4_t ipv4;
parser parse_ipv4_int{
    extract(ipv4);
    return select(latest.protocol) {
        IP_PROTOCOLS_TCP : parse_tcp_int;
        default: parse_error protocol_not_supported;
    }
}

parser parse_ipv4 {
    extract(ipv4);
    return select(latest.protocol) {
        IP_PROTOCOLS_TCP : parse_tcp;
        default: parse_error protocol_not_supported;
    }
}

header tcp_t tcp;
parser parse_tcp {
    extract(tcp);
    return ingress;
}

parser parse_tcp_int {
    extract(tcp);
    return parse_int;
}

header int_t queue_int;
parser parse_int {
    extract(queue_int);
    return ingress;
}

header printqueue_probe_t printqueue_probe;
parser parse_printqueue_probe {
    extract(ipv4);
    extract(tcp);
    extract(printqueue_probe);
    set_metadata(PQ_md.probe, 1);
    return ingress;
}

header printqueue_signal_t printqueue_signal;
parser parse_printqueue_signal {
    extract(ipv4);
    extract(tcp);
    extract(printqueue_signal);
    return ingress;
}


metadata TW_metadata_t TW0_md;      // TW0_md and TW1_md are used alternately for next time window
metadata TW_metadata_t TW1_md;      
metadata register_metadata_t R_md;  // use to control 4 sets of registers
metadata QM_matadata_t QM_md;
metadata PQ_metadata_t PQ_md;
#endif