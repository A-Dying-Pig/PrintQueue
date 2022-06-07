/*************************************************************************
	> File Name: main.p4
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
    > Description: Entrance of the PrintQueue program.
*************************************************************************/

#include "ingress.p4"

//-------------------------------------------------------------------------//
//                Include Only One of the Two File                       //
//-------------------------------------------------------------------------//
//    1. time windows with data plane query (time_windows_data_query.p4)   //
//    2. queue monitor with data plane query (queue_monitor.p4)            //
//-------------------------------------------------------------------------//
#include "time_windows_data_query.p4"
// #include "queue_monitor.p4"

control ingress {
    ingress_pipe();
}

control egress {
    time_windows_data_pipe();
    // queue_monitor_pipe();
}