#include "parser.p4"

register pre_pkt_qdepth_r{
    width: 32;
    instance_count: 1;
} 

blackbox stateful_alu compare_pre_pkt_qdepth_bb{
    reg: pre_pkt_qdepth_r;
    condition_lo: register_lo >= 2000; 
    update_lo_1_value: eg_intr_md.enq_qdepth;
    update_hi_1_predicate: condition_lo;
    update_hi_1_value: 1;
    update_hi_2_predicate: not condition_lo;
    update_hi_2_value: 0;
    output_value: alu_hi;
    output_dst: PQ_md.exceed;
}

@pragma stage 0
table compare_tb{
    actions{
        compare;
    }
    default_action: compare;
    size: 1;
}

action compare(){
    compare_pre_pkt_qdepth_bb.execute_stateful_alu(0);
}

table mirror_tb{
    actions{
        mirror_pkt;
    }
    default_action: mirror_pkt;
    size: 1;
}

action mirror_pkt(){
    clone_egress_pkt_to_egress(3);
}

control test_pipe{
    apply(compare_tb);
    if (PQ_md.exceed == 1){
        apply(mirror_tb);
    }
}