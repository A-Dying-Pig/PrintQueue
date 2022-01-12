/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Actions and Control Logic of Egress Pipeline.
 */
 
#include "parser.p4"

// ipv4 routing table
table ipv4_routing {
    reads {
        ipv4.dst_addr: lpm;
    }
    actions{
        pkt_forward;
        pkt_drop;
        pkt_forward_S101;
    }
    default_action: pkt_forward_S101;
    size : ROUTING_FLOW_NUMBER; 
}

action pkt_forward_S101(){
    add_to_field(ipv4.ttl, -1);
    modify_field(ig_intr_md_for_tm.ucast_egress_port,128);
}

action pkt_forward(dst_port){
    add_to_field(ipv4.ttl, -1);
    modify_field(ig_intr_md_for_tm.ucast_egress_port,dst_port);
}

action pkt_drop(){
    // drop in egress pipeline
    modify_field(ipv4.ttl,0);
    modify_field(ig_intr_md_for_tm.ucast_egress_port,DROP_PORT);
}


control ingress_pipe{
    apply(ipv4_routing);
}
