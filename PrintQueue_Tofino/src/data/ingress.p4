/*********************************************************************************
	> File Name: ingress.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description: Ingress pipeline of PrintQueue: forward, and data plane query
*********************************************************************************/
 
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
    modify_field(ig_intr_md_for_tm.ucast_egress_port, 128);  // forward to a fixed machine for simplicity
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

register dice_r{
    width: 32;
    instance_count: 1;
}

blackbox stateful_alu update_dice_bb{
    reg: dice_r;
    update_lo_1_value: register_lo ^ 1;
    output_dst: PQ_md.forward;
    output_value: register_lo;
}

table update_dice_tb{
    actions{
        update_dice;
    }
    default_action: update_dice;
    size: 1;
}

action update_dice(){
    update_dice_bb.execute_stateful_alu(0);
}

// simplify forwarding
table forward_S101_tb{
    actions{
        to_S101;
    }
    default_action: to_S101;
    size: 1;
}

action to_S101(){
    add_to_field(ipv4.ttl, -1);
    modify_field(ig_intr_md_for_tm.ucast_egress_port, 128);  // forward to a fixed machine for simplicity
}

table forward_S104_tb{
    actions{
        to_S104;        
    }
    default_action: to_S104;
    size: 1;
}

action to_S104(){
    add_to_field(ipv4.ttl, -1);
    modify_field(ig_intr_md_for_tm.ucast_egress_port, 138);  // forward to a fixed machine for simplicity
}

// get threshold to trigger data plane query for different flows
// in the egress pipeline, if the current qdepth is larger than the threshold, trigger data plane query
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

// get threshold to trigger data plane query for different flows
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

// read the threshold from the probe packet
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

table get_isolation_id_tb{
    reads{
        ig_intr_md_for_tm.ucast_egress_port: exact;
    }
    actions{
        get_isolation_id;
        no_PQ;
    }
    default_action: no_PQ;
    size: MAX_PORT_NUM;
}

action get_isolation_id(iso_id, iso_prefix){
    modify_field(PQ_md.isolation_id, iso_id);
    modify_field(R_md.isolation_prefix, iso_prefix);
    modify_field(TW0_md.idx, iso_prefix);
    modify_field(TW1_md.idx, iso_prefix);
    modify_field(PQ_md.disable_PQ, 0);
}

action no_PQ(){
    modify_field(PQ_md.disable_PQ, 1);
}

control ingress_pipe{
    apply(update_dice_tb);
    // if(PQ_md.forward == 0){
    //     apply(forward_S101_tb);
    // }else{
    //     apply(forward_S104_tb);
    // }
    apply(forward_S101_tb);
    if (PQ_md.probe == 1){
        apply(set_threshold_from_probe_pkt_tb);
    }else{
        apply(qdepth_alerting_threshold_2);
    }
    apply(get_isolation_id_tb);
}
