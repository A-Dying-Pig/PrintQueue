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
        default: parse_error protocol_not_supported;
    }
}

header ipv4_t ipv4;
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

#endif