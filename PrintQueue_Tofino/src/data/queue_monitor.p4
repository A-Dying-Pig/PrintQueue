/*************************************************************************
	> File Name: queue_monitor.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description:  Actions and control logic of queue monitor pipeline.
*************************************************************************/

#include "parser.p4"

// stage
/***************************************************
**********************0 0***************************
*********************0   0**************************
*********************0   0**************************
**********************0 0***************************
****************************************************/
register stack_top_r{
    width: 32;
    instance_count: MAX_PORT_NUM;
}

blackbox stateful_alu check_stack_bb{
    reg: stack_top_r;
    update_lo_1_value: eg_intr_md.enq_qdepth;
    condition_lo: eg_intr_md.enq_qdepth == register_lo;
    update_hi_1_predicate: condition_lo;
    update_hi_1_value: 0;
    update_hi_2_predicate: not condition_lo;
    update_hi_2_value: 1;
    output_dst: PQ_md.stack_len_change;
    output_value: alu_hi;
}

@pragma stage 0
table check_stack_tb{
    actions{
        check_stack;
    }
    default_action: check_stack;
    size: 1;
}

action check_stack(){
    check_stack_bb.execute_stateful_alu(PQ_md.isolation_id);         //check whether stack length has changed
}

@pragma stage 0
table prepare_qm_tb{
    reads{
        PQ_md.isolation_id: exact;
    }
    actions{
        prepare_qm;
    }
    default_action: prepare_qm;
    size:MAX_PORT_NUM;
}

action prepare_qm(second_highest){
    // update QM metadata
    modify_field(R_md.second_highest, second_highest);
    modify_field(QM_md.src_addr, ipv4.src_addr);
    modify_field(QM_md.dst_addr, ipv4.dst_addr);
}

register seq_num_r{
    width: 32;
    instance_count: MAX_PORT_NUM;
}

blackbox stateful_alu increment_seq_num_bb{
    reg: seq_num_r;
    update_lo_1_value: register_lo + 1;
    output_dst: QM_md.seq_num;
    output_value: alu_lo;
}

@pragma stage 0
table increment_seq_num_tb{
    actions{
        increment_seq_num;
    }
    default_action: increment_seq_num;
    size: 1;
}

action increment_seq_num(){
    increment_seq_num_bb.execute_stateful_alu(PQ_md.isolation_id);   // increase seq number to prepare for stack change
}

// data plane query
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
table compare_pre_pkt_qdepth_tb{
    actions{
        compare_pre_pkt_qdepth;
    }
    default_action: compare_pre_pkt_qdepth;
    size: 1;
}

action compare_pre_pkt_qdepth(){
    compare_pre_pkt_qdepth_bb.execute_stateful_alu(PQ_md.isolation_id);      // compare qdepth with the threshold to decide whether triggering data plane query
}

register idx_immediate_r{
    width: 32;
    instance_count: MAX_PORT_NUM;
}

blackbox stateful_alu cal_idx_immediate_bb{
    reg: idx_immediate_r;
    update_lo_1_value:  eg_intr_md.enq_qdepth;
    output_value: alu_lo;
    output_dst: QM_md.idx;
}

@pragma stage 0
table cal_idx_immediate_tb{
    actions{
        cal_idx_immediate;
    }
    default_action: cal_idx_immediate;
    size: 1;
}

action cal_idx_immediate(){
    cal_idx_immediate_bb.execute_stateful_alu(PQ_md.isolation_id);       // use ALU to copy the 19-bit eg_intr_md.enq_qdepth to a 32-bit metadata
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
    data_query_lock_bb.execute_stateful_alu(PQ_md.isolation_id);     // lock to avoid another data plane query when registers are not ready
}

@pragma stage 1
table update_idx_second_highest_bit_tb{
    actions{
        update_idx_second_highest_bit;
    }
    default_action: update_idx_second_highest_bit;
    size: 1;
}

action update_idx_second_highest_bit(){
    bit_or(QM_md.idx, QM_md.idx, R_md.second_highest);  // under periodical query, flip the second highest bit every time when reading the registers
}

@pragma stage 1
table seq_num_overflow_set_signal_tb{
    actions{
        seq_num_overflow_set_signal;
    }
    default_action: seq_num_overflow_set_signal;
    size: 1;
}

action seq_num_overflow_set_signal(){
    modify_field(PQ_md.mirror_signal, 2);    //set signal
}

@pragma stage 1
table data_query_set_signal_tb{
    actions{
        data_query_set_signal;
    }
    default_action: data_query_set_signal;
    size: 1;
}

action data_query_set_signal(){
    modify_field(PQ_md.mirror_signal, 1);
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
    update_lo_1_value: register_lo ^ HALF_QDEPTH;
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
}

action reverse_highest_bit(){
    reverse_highest_bit_bb.execute_stateful_alu(PQ_md.isolation_id);     // flip the highest bit due to data plane query or seq overflow
    // ---------------------------------------------------------
    // send signal to control plane to trigger register reading 
    // ---------------------------------------------------------
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

@pragma stage 2
table bit_or_iso_prefix_tb{
    actions{
        bit_or_iso_prefix;
    }
    default_action: bit_or_iso_prefix;
    size: 1;
}

action bit_or_iso_prefix(){
    bit_or(QM_md.idx, QM_md.idx,R_md.isolation_prefix);
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
    bit_or(QM_md.idx, QM_md.idx, R_md.highest);      // pick the correct set of registers (one out of four) as the running stack
}

/***************************************************
**********************4   44************************
**********************4   44************************
**********************444444************************
**********************    44************************
**********************    44************************
****************************************************/

register src_ip_r{
    width: 32;
    instance_count: TOTAL_QDEPTH;
}

blackbox stateful_alu update_src_ip_bb{
    reg: src_ip_r;
    update_lo_1_value: QM_md.src_addr;
}

@pragma stage 4
table update_src_ip_tb{
    actions{
        update_src_ip;
    }
    default_action: update_src_ip;
    size: 1;
}

action update_src_ip(){
    update_src_ip_bb.execute_stateful_alu(QM_md.idx);    // record flow ID
}

/***************************************************
**********************555555************************
**********************55    ************************
**********************555555************************
**********************    55************************
**********************555555************************
****************************************************/

register dst_ip_r{
    width: 32;
    instance_count: TOTAL_QDEPTH;
}

blackbox stateful_alu update_dst_ip_bb{
    reg: dst_ip_r;
    update_lo_1_value: QM_md.dst_addr;
}

@pragma stage 5
table update_dst_ip_tb{
    actions{
        update_dst_ip;
    }
    default_action: update_dst_ip;
    size: 1;
}

action update_dst_ip(){
    update_dst_ip_bb.execute_stateful_alu(QM_md.idx);   // record flow ID
}

/***************************************************
**********************666666************************
**********************66    ************************
**********************666666************************
**********************66  66************************
**********************666666************************
****************************************************/

register seq_array_r{
    width: 32;
    instance_count: TOTAL_QDEPTH;
}

blackbox stateful_alu update_seq_array_bb{
    reg: seq_array_r;
    update_lo_1_value: QM_md.seq_num;
}

@pragma stage 6
table update_seq_array_tb{
    actions{
        update_seq_array;
    }
    default_action: update_seq_array;
    size: 1;
}

action update_seq_array(){
    update_seq_array_bb.execute_stateful_alu(QM_md.idx);    // record seq number
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
}

//--------------------------------------------------------------------------
//             Control flow of queue monitor pipeline
//--------------------------------------------------------------------------
control queue_monitor_pipe{
    if(valid(ipv4) and valid(tcp) and eg_intr_md_from_parser_aux.clone_src == NOT_CLONED and PQ_md.disable_PQ == 0){
        apply(check_stack_tb);
        apply(prepare_qm_tb);
        apply(increment_seq_num_tb);
        apply(compare_pre_pkt_qdepth_tb);
        apply(cal_idx_immediate_tb);
        apply(update_idx_second_highest_bit_tb);
        if(PQ_md.exceed == 1 or QM_md.seq_num == 0){
            if (QM_md.seq_num == 0){
                apply(seq_num_overflow_set_signal_tb);
            }else{
                apply(data_query_set_signal_tb);
            }
            // data query or seq_num overflow
            apply(data_query_lock_tb);      // check whether it is already locked
            if (PQ_md.lock == 0){
                // trigger data plane query
                apply(reverse_highest_bit_tb);
            }else{
                apply(read_highest_bit_tb);
            }
        }else{
            apply(read_highest_bit_tb);
        }
        apply(bit_or_iso_prefix_tb);
        apply(update_idx_highest_bit_tb);
        if(PQ_md.stack_len_change == 1){
            // update stack when switch qdepth changes
            apply(update_src_ip_tb);
            apply(update_dst_ip_tb);
            apply(update_seq_array_tb);
        }
    }
    // modify header stack of signal packets
    if (eg_intr_md_from_parser_aux.clone_src == CLONED_FROM_EGRESS){
        apply(modify_signal_tb);
    }
}