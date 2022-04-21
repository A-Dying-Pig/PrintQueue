# PrintQueue's End Host Program

The section introduces how PrintQueue sends and receives packets at end hosts in the experiments.

## Receive Packets
The program `DPDK_receive_pkt` runs at end hosts. 
It receives packets from a bound NIC. 
After extracting and storing INT headers from packets, the program drops all packets.
It is able to process packets at high throughput (~10Gbps).

### Compile and Run
PrintQueue leverages [DPDK](https://www.dpdk.org/) to receive packets and process INT headers.
[Here](https://www.yiranlei.com/DPDK_Installation_Tutorial) is a tutorial to install DPDK and bind NIC to DPDK-drivers.
Make sure your NIC is compatible with DPDK. 

After successful installation of DPDK, compile `DPDK_receive_pkt` with:
```shell script
cd DPDK_receive_pkt
make clean
make
```
The compiled program is located in the `build` folder.

After binding the NIC to DPDK-driver, run the program with:
```shell script
make run
```
 
### INT headers
When a packet runs through the time windows on the switch, it is inserted a header carrying the queuing information.
The information is later served to get the ground truth of diagnosis.
The header is identified by the `type = 0x080c` field of Ethernet header.
It is inserted after the Ethernet, IPv4, TCP header shown as below:

<img src="./doc/probe_packet_headers.png" width="350">

The program stores the dequeue timestamp, enqueue timestamp, queue depth at enqueue time, and packet's flow ID in the `gt_data`.
The layout of binary files is:

<img src="./doc/qm_binary_layout.png" width="650">


## Send Packets