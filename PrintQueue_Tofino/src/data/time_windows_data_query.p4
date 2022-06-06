/*******************************************************************************************
	> File Name: time_windows_data_query.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description: Actions and control logic of time windows with data plane query pipeline.
*********************************************************************************************/

// Time windows without data plane query can support 5 windows at most.
// Time windows with data plane query can support 4 windows at most.

#include "parser.p4"

/***************************************************
**********************0 0***************************
*********************0   0**************************
*********************0   0**************************
**********************0 0***************************
****************************************************/

// use pre packet's queue depth as the approximate depth of the current packet
register pre_pkt_qdepth_r{
    width: 32;
    instance_count: MAX_PORT_NUM;
} 

blackbox stateful_alu compare_pre_pkt_qdepth_bb{
    reg: pre_pkt_qdepth_r;
    condition_lo: register_lo >= PQ_md.qdepth_threshold; 
    update_lo_1_value: eg_intr_md.enq_qdepth;
    update_hi_1_predicate: condition_lo;
    update_hi_1_value: 1;
    update_hi_2_predicate: not condition_lo;
    update_hi_2_value: 0;
    output_value: alu_hi;
    output_dst: PQ_md.exceed;
}

@pragma stage 0
table trigger_data_plane_query_tb{
    actions{
        trigger_data_plane_query;
    }
    default_action: trigger_data_plane_query;
    size: 1;
}

action trigger_data_plane_query(){
    //get threshold comparing result
    compare_pre_pkt_qdepth_bb.execute_stateful_alu(PQ_md.isolation_id);
}

@pragma stage 0
table prepare_TW0_tb{
    reads{
        PQ_md.isolation_id: exact;
    }
    actions{
        prepare_TW0;
    }
    default_action: prepare_TW0;
    size: MAX_PORT_NUM;
}

action prepare_TW0(second_highest){
    // prepare metadata for the first time window
    modify_field(TW0_md.src_addr, ipv4.src_addr);
    modify_field(TW0_md.dst_addr, ipv4.dst_addr);
    modify_field(TW0_md.src_port, tcp.src_port);
    modify_field(TW0_md.dst_port, tcp.dst_port);
    modify_field(TW0_md.single_port_index_num, SINGLE_PORT_INDEX_NUM);
    modify_field(TW1_md.single_port_index_num, SINGLE_PORT_INDEX_NUM);
    //decide updating first/second quarter of the registers
    modify_field(R_md.second_highest, second_highest);
    bit_or(TW0_md.idx, TW0_md.idx, second_highest);                   // second highest bit flip based on control plane
    bit_or(TW1_md.idx, TW1_md.idx, second_highest);
    // pass the queue information to end hosts to get the ground truth
    add_header(queue_int);
    modify_field(queue_int.dequeue_ts, eg_intr_md_from_parser_aux.egress_global_tstamp);
    add(queue_int.enqueue_ts, ig_intr_md_from_parser_aux.ingress_global_tstamp, INGRESS_PROCESSING_TIME);
    modify_field(queue_int.enq_qdepth, eg_intr_md.enq_qdepth);
    // record pkt enqueue dequeue ts for mirrored packets
    add(PQ_md.pkt_enqueue_ts, ig_intr_md_from_parser_aux.ingress_global_tstamp, INGRESS_PROCESSING_TIME);
    modify_field(PQ_md.pkt_dequeue_ts, eg_intr_md_from_parser_aux.egress_global_tstamp);
}

@pragma stage 0
table modify_ether_tb{
    actions{
        modify_ether;
    }
    default_action: modify_ether;
    size : 1;
}

action modify_ether(){
    modify_field(ethernet.ether_type, ETHERTYPE_PRINTQUEUE);        // modify ethertype to notify end hosts of INT data
}

@pragma stage 0 
table modify_vlan_tb{
    actions{
        modify_vlan;
    }
    default_action: modify_vlan;
    size: 1;
}

action modify_vlan(){
    modify_field(vlan_tag.etherType, ETHERTYPE_PRINTQUEUE);         // modify ethertype to notify end hosts of INT data
}

/***************************************************
************************1***************************
************************1***************************
************************1***************************
************************1***************************
****************************************************/

register data_query_lock_r{
    width: 16;
    instance_count: MAX_PORT_NUM;
}

blackbox stateful_alu data_query_lock_bb{
    reg: data_query_lock_r;
    update_lo_1_value: 1;
    output_value: register_lo;
    output_dst: PQ_md.lock;
}

@pragma stage 1
table data_query_lock_tb{
    actions{
        data_query_lock;
    }
    default_action: data_query_lock;
    size: 1;
}

action data_query_lock(){
    data_query_lock_bb.execute_stateful_alu(PQ_md.isolation_id);      // lock to avoid another data plane query when registers are not ready
    modify_field(PQ_md.mirror_signal, 4);    //set signal
}

@pragma stage 1
table cal_TW0_tts_idx_tb{
    actions{
        cal_TW0_tts_idx;
    }
    default_action: cal_TW0_tts_idx;
    size: 1;
}

action cal_TW0_tts_idx(){
    shift_right(TW0_md.tts, PQ_md.pkt_dequeue_ts, TW0_TB);      // calculate tts of the first window
    modify_field_with_shift(TW0_md.idx, PQ_md.pkt_dequeue_ts, TW0_TB, SIGNLE_PORT_INDEX_MASK);  // move the lowest k bits of tts to index
}

/***************************************************
***********************222**************************
**********************    2*************************
**********************  22**************************
**********************222222************************
****************************************************/

register highest_bit_r{
    width: 32;
    instance_count: MAX_PORT_NUM;
}

blackbox stateful_alu reverse_highest_bit_bb{
    reg: highest_bit_r;
    update_lo_1_value: register_lo ^ HALF_INDEX_NUM;
    output_dst: R_md.highest;
    output_value: alu_lo;
}

@pragma stage 2
table reverse_highest_bit_tb{
    actions{
        reverse_highest_bit;
    }
    default_action: reverse_highest_bit;
    size: 1;
}

field_list mirror_fl {
  PQ_md.mirror_signal;
  PQ_md.isolation_id;
  PQ_md.pkt_enqueue_ts;
  PQ_md.pkt_dequeue_ts;
}

action reverse_highest_bit(){
    reverse_highest_bit_bb.execute_stateful_alu(PQ_md.isolation_id);     // flip the highest bit to execute data plane query
    // -----------------------------------------------------------
    // send signal to control plane to trigger register reading 
    // -----------------------------------------------------------
    clone_egress_pkt_to_egress(MIRROR_SESS , mirror_fl);
}

blackbox stateful_alu read_highest_bit_bb{
    reg: highest_bit_r;
    output_dst: R_md.highest;
    output_value: register_lo;
}

@pragma stage 2
table read_highest_bit_tb{
    actions{
        read_highest_bit;
    }
    default_action: read_highest_bit;
    size: 1;
}

action read_highest_bit(){
    read_highest_bit_bb.execute_stateful_alu(PQ_md.isolation_id);      // just read the highest bit
}

/***************************************************
**********************333***************************
**********************   33*************************
**********************333***************************
**********************   33*************************
**********************333***************************
****************************************************/

@pragma stage 3
table update_idx_highest_bit_tb{
    actions{
        update_idx_highest_bit;
    }
    default_action: update_idx_highest_bit;
    size: 1;
}

action update_idx_highest_bit(){
    bit_or(TW0_md.idx, TW0_md.idx, R_md.highest);       // pick the right set of registers (one out of four) as time windows
    bit_or(TW1_md.idx, TW1_md.idx, R_md.highest);
}

/***************************************************
**********************4   44************************
**********************4   44************************
**********************444444************************
**********************    44************************
**********************    44************************
****************************************************/

@pragma stage 4
table TW0_check_tts_tb{
    actions{
        TW0_check_tts;
    }
    default_action: TW0_check_tts;
    size: 1;
}

register TW0_tts_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW0_check_tts_bb{
    reg: TW0_tts_r;
    update_lo_1_value: TW0_md.tts;
    output_value: register_lo;
    output_dst: TW0_md.tts_r;
}

action TW0_check_tts(){
    TW0_check_tts_bb.execute_stateful_alu(TW0_md.idx);                      // evict old cell and store incoming packet
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.single_port_index_num);   // calculate the tts of the previous cycle
}

@pragma stage 4
table TW0_check_src_ip_tb{
    actions{
        TW0_check_src_ip;
    }
    default_action: TW0_check_src_ip;
    size: 1; 
}

register TW0_src_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW0_check_src_ip_bb{
    reg: TW0_src_ip_r;
    update_lo_1_value: TW0_md.src_addr;
    output_value: register_lo;
    output_dst: TW1_md.src_addr;
}

action TW0_check_src_ip(){
    TW0_check_src_ip_bb.execute_stateful_alu(TW0_md.idx);       // evict old flow ID and store incoming flow ID
}

/***************************************************
**********************555555************************
**********************55    ************************
**********************555555************************
**********************    55************************
**********************555555************************
****************************************************/
@pragma stage 5
table TW0_check_dst_ip_tb{
    actions{
        TW0_check_dst_ip;
    }
    default_action: TW0_check_dst_ip;
    size: 1; 
}

register TW0_dst_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW0_check_dst_ip_bb{
    reg: TW0_dst_ip_r;
    update_lo_1_value: TW0_md.dst_addr;
    output_value: register_lo;
    output_dst: TW1_md.dst_addr;
}

action TW0_check_dst_ip(){
    TW0_check_dst_ip_bb.execute_stateful_alu(TW0_md.idx);   // evict old flow ID and store incoming flow ID
}

@pragma stage 5
table TW0_check_src_port_tb{
    actions{
        TW0_check_src_port;
    }
    default_action: TW0_check_src_port;
    size: 1;
}

register TW0_src_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW0_check_src_port_bb{
    reg: TW0_src_port_r;
    update_lo_1_value: TW0_md.src_port;
    output_value:register_lo;
    output_dst: TW1_md.src_port;
}

action TW0_check_src_port(){
    TW0_check_src_port_bb.execute_stateful_alu(TW0_md.idx); // evict old flow ID and store incoming flow ID
} 

@pragma stage 5
table TW0_check_dst_port_tb{
    actions{
        TW0_check_dst_port;
    }
    default_action: TW0_check_dst_port;
    size: 1;
}

register TW0_dst_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW0_check_dst_port_bb{
    reg: TW0_dst_port_r;
    update_lo_1_value: TW0_md.dst_port;
    output_value: register_lo;
    output_dst: TW1_md.dst_port;
}

action TW0_check_dst_port(){
    TW0_check_dst_port_bb.execute_stateful_alu(TW0_md.idx); // evict old flow ID and store incoming flow ID
}

@pragma stage 5
table TW0_check_pass_tb{
    actions{
        TW0_check_pass;
    }
    default_action: TW0_check_pass;
    size: 1;
}

action TW0_check_pass(){
    // if the evicted packet is of the previous cycle, tts_r should be the same as tts_pre_cycle
    // in other words, cyleID of the evicted one is smaller than the incoming packet by exactly one
    subtract(TW0_md.tts_delta, TW0_md.tts_pre_cycle, TW0_md.tts_r); 
    shift_right(TW1_md.tts, TW0_md.tts_r, ALPHA);                                   // rightshift to get tts of next window
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, SIGNLE_PORT_INDEX_MASK);   // calculate the index of next window
}

/***************************************************
**********************666666************************
**********************66    ************************
**********************666666************************
**********************66  66************************
**********************666666************************
****************************************************/

@pragma stage 6
table  TW1_check_tts_tb{
    actions{
        TW1_check_tts;
    }
    default_action: TW1_check_tts;
    size: 1;
}

register TW1_tts_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW1_check_tts_bb{
    reg: TW1_tts_r;
    update_lo_1_value: TW1_md.tts;
    output_value: register_lo;
    output_dst: TW1_md.tts_r;
}

action TW1_check_tts(){
    TW1_check_tts_bb.execute_stateful_alu(TW1_md.idx);
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.single_port_index_num);
}

@pragma stage 6
table TW1_check_src_ip_tb{
    actions{
        TW1_check_src_ip;
    }
    default_action: TW1_check_src_ip;
    size: 1;
}

register TW1_src_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW1_check_src_ip_bb{
    reg: TW1_src_ip_r;
    update_lo_1_value: TW1_md.src_addr;
    output_value: register_lo;
    output_dst: TW0_md.src_addr;
}

action TW1_check_src_ip(){
    TW1_check_src_ip_bb.execute_stateful_alu(TW1_md.idx);
}

/***************************************************
*********************77777777***********************
**********************    77 ***********************
**********************  77  ************************
**********************  77  ************************
**********************  77  ************************
****************************************************/

@pragma stage 7
table TW1_check_dst_ip_tb{
    actions{
        TW1_check_dst_ip;
    }
    default_action: TW1_check_dst_ip;
    size: 1;
}

register TW1_dst_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW1_check_dst_ip_bb{
    reg: TW1_dst_ip_r;
    update_lo_1_value: TW1_md.dst_addr;
    output_value: register_lo;
    output_dst: TW0_md.dst_addr;
}

action TW1_check_dst_ip(){
    TW1_check_dst_ip_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 7
table TW1_check_src_port_tb{
    actions{
        TW1_check_src_port;
    }
    default_action: TW1_check_src_port;
    size: 1;
}

register TW1_src_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW1_check_src_port_bb{
    reg: TW1_src_port_r;
    update_lo_1_value: TW1_md.src_port;
    output_value: register_lo;
    output_dst: TW0_md.src_port;
}

action TW1_check_src_port(){
    TW1_check_src_port_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 7
table TW1_check_dst_port_tb{
    actions{
        TW1_check_dst_port;
    }
    default_action: TW1_check_dst_port;
    size : 1;
}

register TW1_dst_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW1_check_dst_port_bb{
    reg: TW1_dst_port_r;
    update_lo_1_value: TW1_md.dst_port;
    output_value: register_lo;
    output_dst: TW0_md.dst_port;
}

action TW1_check_dst_port(){
    TW1_check_dst_port_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 7
table TW1_check_pass_tb{
    actions{
        TW1_check_pass;
    }
    default_action: TW1_check_pass;
    size: 1;
}

action TW1_check_pass(){
    subtract(TW1_md.tts_delta, TW1_md.tts_pre_cycle, TW1_md.tts_r);
    shift_right(TW0_md.tts, TW1_md.tts_r, ALPHA);
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, SIGNLE_PORT_INDEX_MASK);
}

/***************************************************
**********************888888************************
**********************8    8************************
**********************888888************************
**********************8    8************************
**********************888888************************
****************************************************/

@pragma stage 8
table  TW2_check_tts_tb{
    actions{
        TW2_check_tts;
    }
    default_action: TW2_check_tts;
    size: 1;
}

register TW2_tts_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW2_check_tts_bb{
    reg: TW2_tts_r;
    update_lo_1_value: TW0_md.tts;
    output_value: register_lo;
    output_dst: TW0_md.tts_r;
}

action TW2_check_tts(){
    TW2_check_tts_bb.execute_stateful_alu(TW0_md.idx);
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.single_port_index_num);
}

@pragma stage 8
table TW2_check_src_ip_tb{
    actions{
        TW2_check_src_ip;
    }
    default_action: TW2_check_src_ip;
    size: 1;
}

register TW2_src_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW2_check_src_ip_bb{
    reg: TW2_src_ip_r;
    update_lo_1_value: TW0_md.src_addr;
    output_value: register_lo;
    output_dst: TW1_md.src_addr;
}

action TW2_check_src_ip(){
    TW2_check_src_ip_bb.execute_stateful_alu(TW0_md.idx);
}

/***************************************************
***********************999999***********************
***********************9    9***********************
***********************999999***********************
***********************     9***********************
***********************999999***********************
****************************************************/

@pragma stage 9
table TW2_check_dst_ip_tb{
    actions{
        TW2_check_dst_ip;
    }
    default_action: TW2_check_dst_ip;
    size: 1;
}

register TW2_dst_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW2_check_dst_ip_bb{
    reg: TW2_dst_ip_r;
    update_lo_1_value: TW0_md.dst_addr;
    output_value: register_lo;
    output_dst: TW1_md.dst_addr;
}

action TW2_check_dst_ip(){
    TW2_check_dst_ip_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 9
table TW2_check_src_port_tb{
    actions{
        TW2_check_src_port;
    }
    default_action: TW2_check_src_port;
    size: 1;
}

register TW2_src_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW2_check_src_port_bb{
    reg: TW2_src_port_r;
    update_lo_1_value: TW0_md.src_port;
    output_value: register_lo;
    output_dst: TW1_md.src_port;
}

action TW2_check_src_port(){
    TW2_check_src_port_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 9
table TW2_check_dst_port_tb{
    actions{
        TW2_check_dst_port;
    }
    default_action: TW2_check_dst_port;
    size : 1;
}

register TW2_dst_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW2_check_dst_port_bb{
    reg: TW2_dst_port_r;
    update_lo_1_value: TW0_md.dst_port;
    output_value: register_lo;
    output_dst: TW1_md.dst_port;
}

action TW2_check_dst_port(){
    TW2_check_dst_port_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 9
table TW2_check_pass_tb{
    actions{
        TW2_check_pass;
    }
    default_action: TW2_check_pass;
    size: 1;
}

action TW2_check_pass(){
    subtract(TW0_md.tts_delta, TW0_md.tts_pre_cycle, TW0_md.tts_r);
    shift_right(TW1_md.tts, TW0_md.tts_r, ALPHA);
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, SIGNLE_PORT_INDEX_MASK);
}

/***************************************************
*******************1***000000***********************
******************11***0    0***********************
*******************1***0    0***********************
*******************1***0    0***********************
******************111**000000***********************
****************************************************/

@pragma stage 10
table  TW3_check_tts_tb{
    actions{
        TW3_check_tts;
    }
    default_action: TW3_check_tts;
    size: 1;
}

register TW3_tts_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW3_check_tts_bb{
    reg: TW3_tts_r;
    update_lo_1_value: TW1_md.tts;
    output_value: register_lo;
    output_dst: TW1_md.tts_r;
}

action TW3_check_tts(){
    TW3_check_tts_bb.execute_stateful_alu(TW1_md.idx);
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.single_port_index_num);
}

@pragma stage 10
table TW3_check_src_ip_tb{
    actions{
        TW3_check_src_ip;
    }
    default_action: TW3_check_src_ip;
    size: 1;
}

register TW3_src_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW3_check_src_ip_bb{
    reg: TW3_src_ip_r;
    update_lo_1_value: TW1_md.src_addr;
    output_value: register_lo;
    output_dst: TW0_md.src_addr;
}

action TW3_check_src_ip(){
    TW3_check_src_ip_bb.execute_stateful_alu(TW1_md.idx);
}

/***************************************************
*******************1*******1************************
******************11******11************************
*******************1*******1************************
*******************1*******1************************
******************111*****111***********************
****************************************************/

@pragma stage 11
table TW3_check_dst_ip_tb{
    actions{
        TW3_check_dst_ip;
    }
    default_action: TW3_check_dst_ip;
    size: 1;
}

register TW3_dst_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW3_check_dst_ip_bb{
    reg: TW3_dst_ip_r;
    update_lo_1_value: TW1_md.dst_addr;
    output_value: register_lo;
    output_dst: TW0_md.dst_addr;
}

action TW3_check_dst_ip(){
    TW3_check_dst_ip_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 11
table TW3_check_src_port_tb{
    actions{
        TW3_check_src_port;
    }
    default_action: TW3_check_src_port;
    size: 1;
}

register TW3_src_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW3_check_src_port_bb{
    reg: TW3_src_port_r;
    update_lo_1_value: TW1_md.src_port;
    output_value: register_lo;
    output_dst: TW0_md.src_port;
}

action TW3_check_src_port(){
    TW3_check_src_port_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 11
table TW3_check_dst_port_tb{
    actions{
        TW3_check_dst_port;
    }
    default_action: TW3_check_dst_port;
    size : 1;
}

register TW3_dst_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW3_check_dst_port_bb{
    reg: TW3_dst_port_r;
    update_lo_1_value: TW1_md.dst_port;
    output_value: register_lo;
    output_dst: TW0_md.dst_port;
}

action TW3_check_dst_port(){
    TW3_check_dst_port_bb.execute_stateful_alu(TW1_md.idx);
}

@pragma stage 11
table TW3_check_pass_tb{
    actions{
        TW3_check_pass;
    }
    default_action: TW3_check_pass;
    size: 1;
}

action TW3_check_pass(){
    subtract(TW1_md.tts_delta, TW1_md.tts_pre_cycle, TW1_md.tts_r);
    shift_right(TW0_md.tts, TW1_md.tts_r, ALPHA);
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, SIGNLE_PORT_INDEX_MASK);
}

// Modify signal packet
table modify_signal_tb{
    actions{
        modify_signal;
    }
    default_action: modify_signal;
    size: 1;
}
//-----------------------------------------------------
//           Signal Header Stack
// Ethernet / IPv4 / TCP / [mirror signal] / payload
//----------------------------------------------------
action modify_signal(){
    remove_header(vlan_tag);
    remove_header(queue_int);
    modify_field(ethernet.ether_type, ETHERTYPE_PRINTQUEUE_SIGNAL);
    add_header(printqueue_signal);
    modify_field(printqueue_signal.signal_type, PQ_md.mirror_signal);
    modify_field(printqueue_signal.isolation_id, PQ_md.isolation_id);
    modify_field(printqueue_signal.pkt_enqueue_ts, PQ_md.pkt_enqueue_ts);
    modify_field(printqueue_signal.pkt_dequeue_ts, PQ_md.pkt_dequeue_ts);
}

//--------------------------------------------------------------------------
//        Control flow of time windows with data plane query pipeline
//--------------------------------------------------------------------------
control time_windows_data_pipe{
    if(valid(ipv4) and valid(tcp) and eg_intr_md_from_parser_aux.clone_src == NOT_CLONED and PQ_md.disable_PQ == 0){
        // a none-clone packet
        apply(trigger_data_plane_query_tb);
        apply(prepare_TW0_tb);
        if(valid(vlan_tag)){
            apply(modify_vlan_tb);
        }else{
            apply(modify_ether_tb);
        }
        apply(cal_TW0_tts_idx_tb);
        if (PQ_md.exceed == 1){ 
            apply(data_query_lock_tb); 
            if (PQ_md.lock == 0){
                // trigger data plane query
                apply(reverse_highest_bit_tb);
            }else{
                apply(read_highest_bit_tb);
            }
        }else{
            apply(read_highest_bit_tb);
        }
        apply(update_idx_highest_bit_tb);
//---------------------------------------------------------//
//          Maximum 4 time windows in total                //
//---------------------------------------------------------//
// To reduce the number of time windows, direct comment the window parts
        // TW0
        apply(TW0_check_tts_tb);
        apply(TW0_check_src_ip_tb);
        apply(TW0_check_dst_ip_tb);
        apply(TW0_check_src_port_tb);
        apply(TW0_check_dst_port_tb);
        apply(TW0_check_pass_tb);
        if (TW0_md.tts_delta == 0){
            if (TW0_md.tts_r != 0){
                // TW1
                apply(TW1_check_tts_tb);
                apply(TW1_check_src_ip_tb);
                apply(TW1_check_dst_ip_tb);
                apply(TW1_check_src_port_tb);
                apply(TW1_check_dst_port_tb);
                apply(TW1_check_pass_tb);
                if (TW1_md.tts_delta == 0){
                    if(TW1_md.tts_r != 0){
                        // TW2
                        apply(TW2_check_tts_tb);
                        apply(TW2_check_src_ip_tb);
                        apply(TW2_check_dst_ip_tb);
                        apply(TW2_check_src_port_tb);
                        apply(TW2_check_dst_port_tb);
                        apply(TW2_check_pass_tb);
                        if (TW0_md.tts_delta == 0){
                            if (TW0_md.tts_r != 0){
                                // TW3
                                apply(TW3_check_tts_tb);
                                apply(TW3_check_src_ip_tb);
                                apply(TW3_check_dst_ip_tb);
                                apply(TW3_check_src_port_tb);
                                apply(TW3_check_dst_port_tb);
                                apply(TW3_check_pass_tb);
                            }
                        }
                    }
                }
            }
        }
    }
    // modify header stack of signal packets
    if (eg_intr_md_from_parser_aux.clone_src == CLONED_FROM_EGRESS){
        apply(modify_signal_tb);
    }
}
