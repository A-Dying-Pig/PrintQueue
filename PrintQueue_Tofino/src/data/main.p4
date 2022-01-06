/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Entrance of the PrintQueue Program.
 */
 
#include "ingress.p4"
#include "egress.p4"

control ingress {
    ingress_pipe();
}

control egress {
    // egress_pipe();
}