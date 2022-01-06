/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Packet Parser.
 */

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
        ETHERTYPE_IPV4 : parse_ipv4;
        ETHERTYPE_PRINTQUEUE: parse_ipv4_int;
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

metadata TW_metadata_t TW0_md;
metadata TW_metadata_t TW1_md;
#endif