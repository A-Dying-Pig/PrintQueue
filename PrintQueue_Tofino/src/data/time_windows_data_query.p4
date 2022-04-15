/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Actions and Control Logic of Time Windows with Data Plane Query Pipeline.
 */


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
    instance_count: 1;
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
table prepare_TW0_tb{
    actions{
        prepare_TW0;
    }
    default_action: prepare_TW0;
    size: 1;
}

action prepare_TW0(second_highest){
    modify_field(TW0_md.src_addr, ipv4.src_addr);
    modify_field(TW0_md.dst_addr, ipv4.dst_addr);
    modify_field(TW0_md.src_port, tcp.src_port);
    modify_field(TW0_md.dst_port, tcp.dst_port);
    modify_field(TW0_md.quarter_index_num, QUARTER_INDEX_NUM);
    modify_field(TW1_md.quarter_index_num, QUARTER_INDEX_NUM);
    //decide updating first/second quarter of the registers
    modify_field(R_md.second_highest, second_highest);          // second_highest = 100000000000 or 000000000000
    modify_field(TW0_md.idx, second_highest);
    modify_field(TW1_md.idx, second_highest);
    //get threshold comparing result
    compare_pre_pkt_qdepth_bb.execute_stateful_alu(0);
    // pass the queue information to the end to get the ground truth
    add_header(queue_int);
    modify_field(queue_int.dequeue_ts, eg_intr_md_from_parser_aux.egress_global_tstamp);
    add(queue_int.enqueue_ts, ig_intr_md_from_parser_aux.ingress_global_tstamp, INGRESS_PROCESSING_TIME);
    modify_field(queue_int.enq_qdepth, eg_intr_md.enq_qdepth);
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
    modify_field(ethernet.ether_type, ETHERTYPE_PRINTQUEUE);
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
    modify_field(vlan_tag.etherType, ETHERTYPE_PRINTQUEUE);
}

/***************************************************
************************1***************************
************************1***************************
************************1***************************
************************1***************************
****************************************************/
register data_query_lock_r{
    width: 1;
    instance_count: 1;
}

blackbox stateful_alu data_query_lock_bb{
    reg: data_query_lock_r;
    update_lo_1_value: set_bit;
    output_dst: PQ_md.lock;
    output_value: register_lo;
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
    data_query_lock_bb.execute_stateful_alu(0);
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
    shift_right(TW0_md.tts, queue_int.dequeue_ts, TW0_TB);
    modify_field_with_shift(TW0_md.idx, queue_int.dequeue_ts, TW0_TB, QUARTER_INDEX_MASK);
}


/***************************************************
***********************222**************************
**********************    2*************************
**********************  22**************************
**********************222222************************
****************************************************/


register highest_bit_r{
    width: 32;
    instance_count: 1;
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

action reverse_highest_bit(){
    reverse_highest_bit_bb.execute_stateful_alu(0);
    // ---------------------------------------
    // ---------------------------------------
    // TODO - SEND SIGNAL TO THE CONTROL PLANE
    // ---------------------------------------
    // ---------------------------------------
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
    read_highest_bit_bb.execute_stateful_alu(0);
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
    bit_or(TW0_md.idx, TW0_md.idx, R_md.highest);
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
    TW0_check_tts_bb.execute_stateful_alu(TW0_md.idx);
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.quarter_index_num);
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
    TW0_check_src_ip_bb.execute_stateful_alu(TW0_md.idx);
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
    TW0_check_dst_ip_bb.execute_stateful_alu(TW0_md.idx);
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
    TW0_check_src_port_bb.execute_stateful_alu(TW0_md.idx);
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
    TW0_check_dst_port_bb.execute_stateful_alu(TW0_md.idx);
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
    subtract(TW0_md.tts_delta, TW0_md.tts_pre_cycle, TW0_md.tts_r);
    shift_right(TW1_md.tts, TW0_md.tts_r, ALPHA);
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, QUARTER_INDEX_MASK);
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
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.quarter_index_num);
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
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, QUARTER_INDEX_MASK);
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
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.quarter_index_num);
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
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, QUARTER_INDEX_MASK);
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
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.quarter_index_num);
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
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, QUARTER_INDEX_MASK);
}


control time_windows_data_pipe{
    if(valid(ipv4) and valid(tcp)){
        apply(prepare_TW0_tb);
        if(valid(vlan_tag)){
            apply(modify_vlan_tb);
        }else{
            apply(modify_ether_tb);
        }
        // data plane query - highest bit
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

}
