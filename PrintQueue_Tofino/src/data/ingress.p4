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

// get threshold to trigger alerts for different flows
table qdepth_alerting_threshold_4{
    reads{
        ipv4.src_addr: exact;
        ipv4.dst_addr: exact;
        tcp.src_port: exact;
        tcp.dst_port: exact;
    }
    actions{
        set_threshold;
        no_matching_threshold;
    }
    default_action: no_matching_threshold;
    size: THRESHOLD_FLOW_NUMBER;
}

table qdepth_alerting_threshold_2{
    reads{
        ipv4.src_addr: exact;
        ipv4.dst_addr: exact;
    }
    actions{
        set_threshold;
        no_matching_threshold;
    }
    default_action: no_matching_threshold;
    size: THRESHOLD_FLOW_NUMBER;
}

action no_matching_threshold(){
    modify_field(PQ_md.qdepth_threshold, DEFAULT_QDEPTH_THRESHOLD);
}

action set_threshold(flow_threshold){
    modify_field(PQ_md.qdepth_threshold, flow_threshold);
}

table set_threshold_from_probe_pkt_tb{
    actions{
        set_threshold_from_probe_pkt;
    }
    default_action: set_threshold_from_probe_pkt;
    size: 1;
}

action set_threshold_from_probe_pkt(){
    modify_field(PQ_md.qdepth_threshold, printqueue_probe.qdepth_threshold);
}

control ingress_pipe{
    apply(ipv4_routing);
    if (PQ_md.probe == 1){
        apply(set_threshold_from_probe_pkt_tb);
    }else{
        apply(qdepth_alerting_threshold_4);
    }
}
