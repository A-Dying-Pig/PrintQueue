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
@pragma stage 0
table prepare_TW0_tb{
    actions{
        prepare_TW0;
    }
    default_action: prepare_TW0;
    size: 1;
}

action prepare_TW0(){
    modify_field(TW0_md.src_addr, ipv4.src_addr);
    modify_field(TW0_md.dst_addr, ipv4.dst_addr);
    modify_field(TW0_md.src_port, tcp.src_port);
    modify_field(TW0_md.dst_port, tcp.dst_port);
    shift_right(TW0_md.tts, eg_intr_md_from_parser_aux.egress_global_tstamp, TW0_TB);
    modify_field_with_shift(TW0_md.idx, eg_intr_md_from_parser_aux.egress_global_tstamp, TW0_TB, 0xFFFF);
    // pass the queue information to the end to get the ground truth
    add_header(queue_int);
    modify_field(queue_int.dequeue_ts, eg_intr_md_from_parser_aux.egress_global_tstamp);
    // modify_field(queue_int.queue_length, );
}


/***************************************************
************************1***************************
************************1***************************
************************1***************************
************************1***************************
****************************************************/

@pragma stage 1
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
}

@pragma stage 1
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
***********************222**************************
**********************    2*************************
**********************  22**************************
**********************222222************************
****************************************************/

@pragma stage 2
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

@pragma stage 2
table TW0_check_src_port_tb{
    actions{
        TW0_check_src_port;
    }
    default_action: TW0_check_src_port;
    size: 1;
}

register TW0_src_port_r{
    width: 16:
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

@pragma stage 2
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

@pragma stage 2
table TW0_check_pass_tb{
    actions{
        TW0_check_pass;
    }
    default_action: TW0_check_pass;
    size: 1;
}

action TW0_check_pass(){
    subtract(TW0_md.tts_delta, TW0_md.tts, TW0_md.tts_r);
    shift_right(TW1_md.tts, TW0_md.tts_r, ALPHA);
    modify_field_with_shift(TW1_md.idx, TW0_md.tts_r, ALPHA, 0xFFFF);
}

/***************************************************
**********************333***************************
**********************   33*************************
**********************333***************************
**********************   33*************************
**********************333***************************
****************************************************/

@pragma stage 3
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
}

@pragma stage 3
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
**********************4   44************************
**********************4   44************************
**********************444444************************
**********************    44************************
**********************    44************************
****************************************************/

@pragma stage 4
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

@pragma stage 4
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

@pragma stage 4
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

@pragma stage 4
table TW1_check_pass_tb{
    actions{
        TW1_check_pass;
    }
    default_action: TW1_check_pass;
    size: 1;
}

action TW1_check_pass(){
    subtract(TW1_md.tts_delta, TW1_md.tts, TW1_md.tts_r);
    shift_right(TW0_md.tts, TW1_md.tts_r, ALPHA);
    modify_field_with_shift(TW0_md.idx, TW0_md.tts_r, ALPHA, 0xFFFF);
}

/*******************CONTROL************************/
control egress_pipe{
    if(valid(ipv4) and valid(tcp)){
        // TW0
        apply(TW0_check_tts_tb);
        apply(TW0_check_src_ip_tb);
        apply(TW0_check_dst_ip_tb);
        apply(TW0_check_src_port_tb);
        apply(TW0_check_dst_port_tb);
        apply(TW0_check_pass_tb);
        if (TW0_md.tts_delta == INDEX_NUM and TW0_md.tts_r != 0){
            // TW1
            apply(TW1_check_tts_tb);
            apply(TW1_check_src_ip_tb);
            apply(TW1_check_dst_ip_tb);
            apply(TW1_check_src_port_tb);
            apply(TW1_check_dst_port_tb);
            apply(TW1_check_pass_tb);
            if (TW1_md.tts_delta == INDEX_NUM and TW1_md.tts_r != 0){
                // TW2

            }
        }
    }
}