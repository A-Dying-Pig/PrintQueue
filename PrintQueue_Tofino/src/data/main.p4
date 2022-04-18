/**
 * Authors:
 *     Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
 * File Description:
 *     Entrance of the PrintQueue Program.
 */
 
#include "ingress.p4"
// #include "time_windows.p4"
// #include "time_windows_data_query.p4"
#include "queue_monitor.p4"


control ingress {
    ingress_pipe();
}

control egress {
    // time_windows_periodical_pipe();
    // time_windows_data_pipe();
    queue_monitor_pipe();
}