/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Actions and Control Logic of Egress Pipeline.
 */


#include "parser.p4"


/***************************************************
**********************0 0***************************
*********************0   0**************************
*********************0   0**************************
**********************0 0***************************
****************************************************/
//TODO: add mantis

@pragma stage 0
table prepare_TW0_tb{
    actions{
        prepare_TW0;
    }
    default_action: prepare_TW0;
    size: 1;
}

action prepare_TW0(half){
    modify_field(TW0_md.src_addr, ipv4.src_addr);
    modify_field(TW0_md.dst_addr, ipv4.dst_addr);
    modify_field(TW0_md.src_port, tcp.src_port);
    modify_field(TW0_md.dst_port, tcp.dst_port);
    modify_field(TW0_md.half_index_num, HALF_INDEX_NUM);
    modify_field(TW1_md.half_index_num, HALF_INDEX_NUM);
    //decide updating first/second half of the registers
    modify_field(R_md.half, half);          // half = 100000000000 or 000000000000
    modify_field(TW0_md.idx, half);
    modify_field(TW1_md.idx, half);
    // pass the queue information to the end to get the ground truth
    add_header(queue_int);
    add(queue_int.dequeue_ts, eg_intr_md.enq_tstamp, eg_intr_md.deq_timedelta);
    modify_field(queue_int.queue_length, eg_intr_md.deq_qdepth);
}

/***************************************************
************************1***************************
************************1***************************
************************1***************************
************************1***************************
****************************************************/

@pragma stage 1
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

@pragma stage 1 
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

@pragma stage 1
table cal_TW0_tts_idx_tb{
    actions{
        cal_TW0_tts_idx;
    }
    default_action: cal_TW0_tts_idx;
    size: 1;
}

action cal_TW0_tts_idx(){
    shift_right(R_md.half, R_md.half, HALF_INDEX_NUM);
    shift_right(TW0_md.tts, queue_int.dequeue_ts, TW0_TB);
    modify_field_with_shift(TW0_md.idx, queue_int.dequeue_ts, TW0_TB, HALF_INDEX_MASK);
}


/***************************************************
***********************222**************************
**********************    2*************************
**********************  22**************************
**********************222222************************
****************************************************/

@pragma stage 2
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
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.half_index_num);
}

@pragma stage 2
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
**********************333***************************
**********************   33*************************
**********************333***************************
**********************   33*************************
**********************333***************************
****************************************************/
@pragma stage 3
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

@pragma stage 3
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

@pragma stage 3
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

@pragma stage 3
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
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, HALF_INDEX_MASK);
}

/***************************************************
**********************4   44************************
**********************4   44************************
**********************444444************************
**********************    44************************
**********************    44************************
****************************************************/

@pragma stage 4
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
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.half_index_num);
}

@pragma stage 4
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
**********************555555************************
**********************55    ************************
**********************555555************************
**********************    55************************
**********************555555************************
****************************************************/
@pragma stage 5
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

@pragma stage 5
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

@pragma stage 5
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

@pragma stage 5
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
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, HALF_INDEX_MASK);
}

/***************************************************
**********************666666************************
**********************66    ************************
**********************666666************************
**********************66  66************************
**********************666666************************
****************************************************/

@pragma stage 6
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
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.half_index_num);
}

@pragma stage 6
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
*********************77777777***********************
**********************    77 ***********************
**********************  77  ************************
**********************  77  ************************
**********************  77  ************************
****************************************************/

@pragma stage 7
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

@pragma stage 7
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

@pragma stage 7
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

@pragma stage 7
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
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, HALF_INDEX_MASK);
}

/***************************************************
**********************888888************************
**********************8    8************************
**********************888888************************
**********************8    8************************
**********************888888************************
****************************************************/

@pragma stage 8
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
    subtract(TW1_md.tts_pre_cycle, TW1_md.tts, TW1_md.half_index_num);
}

@pragma stage 8
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
***********************999999***********************
***********************9    9***********************
***********************999999***********************
***********************     9***********************
***********************999999***********************
****************************************************/

@pragma stage 9
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

@pragma stage 9
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

@pragma stage 9
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

@pragma stage 9
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
    modify_field_with_shift(TW0_md.idx, TW1_md.tts_r, ALPHA, HALF_INDEX_MASK);
}

/***************************************************
*******************1***000000***********************
******************11***0    0***********************
*******************1***0    0***********************
*******************1***0    0***********************
******************111**000000***********************
****************************************************/

@pragma stage 10
table  TW4_check_tts_tb{
    actions{
        TW4_check_tts;
    }
    default_action: TW4_check_tts;
    size: 1;
}

register TW4_tts_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW4_check_tts_bb{
    reg: TW4_tts_r;
    update_lo_1_value: TW0_md.tts;
    output_value: register_lo;
    output_dst: TW0_md.tts_r;
}

action TW4_check_tts(){
    TW4_check_tts_bb.execute_stateful_alu(TW0_md.idx);
    subtract(TW0_md.tts_pre_cycle, TW0_md.tts, TW0_md.half_index_num);
}

@pragma stage 10
table TW4_check_src_ip_tb{
    actions{
        TW4_check_src_ip;
    }
    default_action: TW4_check_src_ip;
    size: 1;
}

register TW4_src_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW4_check_src_ip_bb{
    reg: TW4_src_ip_r;
    update_lo_1_value: TW0_md.src_addr;
    output_value: register_lo;
    output_dst: TW1_md.src_addr;
}

action TW4_check_src_ip(){
    TW4_check_src_ip_bb.execute_stateful_alu(TW0_md.idx);
}

/***************************************************
*******************1*******1************************
******************11******11************************
*******************1*******1************************
*******************1*******1************************
******************111*****111***********************
****************************************************/

@pragma stage 11
table TW4_check_dst_ip_tb{
    actions{
        TW4_check_dst_ip;
    }
    default_action: TW4_check_dst_ip;
    size: 1;
}

register TW4_dst_ip_r{
    width: 32;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW4_check_dst_ip_bb{
    reg: TW4_dst_ip_r;
    update_lo_1_value: TW0_md.dst_addr;
    output_value: register_lo;
    output_dst: TW1_md.dst_addr;
}

action TW4_check_dst_ip(){
    TW4_check_dst_ip_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 11
table TW4_check_src_port_tb{
    actions{
        TW4_check_src_port;
    }
    default_action: TW4_check_src_port;
    size: 1;
}

register TW4_src_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW4_check_src_port_bb{
    reg: TW4_src_port_r;
    update_lo_1_value: TW0_md.src_port;
    output_value: register_lo;
    output_dst: TW1_md.src_port;
}

action TW4_check_src_port(){
    TW4_check_src_port_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 11
table TW4_check_dst_port_tb{
    actions{
        TW4_check_dst_port;
    }
    default_action: TW4_check_dst_port;
    size : 1;
}

register TW4_dst_port_r{
    width: 16;
    instance_count: INDEX_NUM;
}

blackbox stateful_alu TW4_check_dst_port_bb{
    reg: TW4_dst_port_r;
    update_lo_1_value: TW0_md.dst_port;
    output_value: register_lo;
    output_dst: TW1_md.dst_port;
}

action TW4_check_dst_port(){
    TW4_check_dst_port_bb.execute_stateful_alu(TW0_md.idx);
}

@pragma stage 11
table TW4_check_pass_tb{
    actions{
        TW4_check_pass;
    }
    default_action: TW4_check_pass;
    size: 1;
}

action TW4_check_pass(){
    subtract(TW0_md.tts_delta, TW0_md.tts_pre_cycle, TW0_md.tts_r);
    shift_right(TW1_md.tts, TW0_md.tts_r, ALPHA);
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, HALF_INDEX_MASK);
}

/*******************CONTROL************************/
control egress_pipe{
    if(valid(ipv4) and valid(tcp)){
        //prepare
        apply(prepare_TW0_tb);
        if(valid(vlan_tag)){
            apply(modify_vlan_tb);
        }else{
            apply(modify_ether_tb);
        }
        apply(cal_TW0_tts_idx_tb);
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
                                if (TW1_md.tts_delta == 0){
                                    if (TW1_md.tts_r != 0){
                                        // TW4
                                        apply(TW4_check_tts_tb);
                                        apply(TW4_check_src_ip_tb);
                                        apply(TW4_check_dst_ip_tb);
                                        apply(TW4_check_src_port_tb);
                                        apply(TW4_check_dst_port_tb);
                                        apply(TW4_check_pass_tb);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}