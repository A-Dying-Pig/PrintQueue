
/*************************************************************************
	> File Name: PrintQueue.c
	> Author: Yiran Lei
	> Mail: leiyr20@mails.tsinghua.edu.cn
	> Lase Update Time: 2022.4.20
  > Description: Data plane (Tofino) control interfaces for PrintQueue
*************************************************************************/


/* Standard includes */
#include <stdio.h>
#include <string.h>
#include <getopt.h>
#include <signal.h>
#include <sys/time.h>
#include <unistd.h>
#include <tofino/pdfixed/pd_mirror.h>
#include <tofino/pdfixed/pd_tm.h>
#include <bf_pm/bf_pm_intf.h>
#include <net/if.h>
#include <sys/socket.h>
#include <linux/if_packet.h>
#include <linux/if_ether.h>
#include <arpa/inet.h>
#include <sys/ioctl.h>
#include <net/ethernet.h>
#include <pthread.h>
#include <math.h>

/* Local includes */
#include "bf_switchd.h"
#include "switch_config.h"
#include "pd/pd.h"

#define PIPE_MGR_SUCCESS 0
#define HDL_BUF_SIZE 100
#define RCV_BUF_SIZE 256
#define CONFIG_BUF_SIZE 100
#define ETHERTYPE_PRINTQUEUE_SIGNAL   0x080e
#define MAX_PORT_NUM 16

static void bf_switchd_parse_hld_mgrs_list(bf_switchd_context_t *ctx,
                                           char *mgrs_list) {
  int len = strlen(mgrs_list);
  int i = 0;
  char mgr;

  while (i < len) {
    mgr = mgrs_list[i];
    switch (mgr) {
      case 'p':
        ctx->skip_hld.pipe_mgr = true;
        break;
      case 'm':
        ctx->skip_hld.mc_mgr = true;
        break;
      case 'k':
        ctx->skip_hld.pkt_mgr = true;
        break;
      case 'r':
        ctx->skip_hld.port_mgr = true;
        break;
      case 't':
        ctx->skip_hld.traffic_mgr = true;
        break;
      default:
        printf("Unknown skip-hld option %c \n", mgr);
        break;
    }
    i++;
  }
}

/* Parse cmd-line options of bf_switchd */
static void bf_switchd_parse_options(bf_switchd_context_t *ctx,
                                     int argc,
                                     char **argv) {
  char *skip_hld_mgrs_list = NULL;
  while (1) {
    int option_index = 0;
    /* Options without short equivalents */
    enum long_opts {
      OPT_START = 256,
      OPT_INSTALLDIR,
      OPT_CONFFILE,
      OPT_TCPPORTBASE,
      OPT_SKIP_P4,
      OPT_SKIP_HLD,
      OPT_SKIP_PORT_ADD,
      OPT_STS_PORT,
      OPT_KERNEL_PKT,
      OPT_BACKGROUND,
      OPT_UCLI,
      OPT_BFS_LOCAL,
      OPT_INIT_MODE,
      OPT_NO_PI,
    };
    static struct option long_options[] = {
        {"help", no_argument, 0, 'h'},
        {"install-dir", required_argument, 0, OPT_INSTALLDIR},
        {"conf-file", required_argument, 0, OPT_CONFFILE},
        {"tcp-port-base", required_argument, 0, OPT_TCPPORTBASE},
        {"skip-p4", no_argument, 0, OPT_SKIP_P4},
        {"skip-hld", required_argument, 0, OPT_SKIP_HLD},
        {"skip-port-add", no_argument, 0, OPT_SKIP_PORT_ADD},
        {"status-port", required_argument, 0, OPT_STS_PORT},
        {"kernel-pkt", no_argument, 0, OPT_KERNEL_PKT},
        {"background", no_argument, 0, OPT_BACKGROUND},
        {"ucli", no_argument, 0, OPT_UCLI},
        {"bfs-local-only", no_argument, 0, OPT_BFS_LOCAL},
        {"init-mode", required_argument, 0, OPT_INIT_MODE},
        {"no-pi", no_argument, 0, OPT_NO_PI},
        {0, 0, 0, 0}};
    int c = getopt_long(argc, argv, "h", long_options, &option_index);
    if (c == -1) {
      break;
    }
    switch (c) {
      case OPT_INSTALLDIR:
        ctx->install_dir = strdup(optarg);
        printf("Install Dir: %s (%p)\n",
               ctx->install_dir,
               (void *)ctx->install_dir);
        break;
      case OPT_CONFFILE:
        ctx->conf_file = strdup(optarg);
        break;
      case OPT_TCPPORTBASE:
        ctx->tcp_port_base = atoi(optarg);
        break;
      case OPT_SKIP_P4:
        ctx->skip_p4 = true;
        break;
      case OPT_SKIP_HLD:
        skip_hld_mgrs_list = strdup(optarg);
        printf("Skip-hld-mgrs list is %s \n", skip_hld_mgrs_list);
        bf_switchd_parse_hld_mgrs_list(ctx, skip_hld_mgrs_list);
        free(skip_hld_mgrs_list);
        break;
      case OPT_SKIP_PORT_ADD:
        ctx->skip_port_add = true;
        break;
      case OPT_STS_PORT:
        ctx->dev_sts_thread = true;
        ctx->dev_sts_port = atoi(optarg);
        break;
      case OPT_KERNEL_PKT:
        ctx->kernel_pkt = true;
        break;
      case OPT_BACKGROUND:
        ctx->running_in_background = true;
        break;
      case OPT_UCLI:
        ctx->shell_set_ucli = true;
        break;
      case OPT_BFS_LOCAL:
        ctx->bfshell_local_only = true;
        break;
      case OPT_INIT_MODE:
        if (!strncmp(optarg, "cold", 4)) {
          ctx->init_mode = BF_DEV_INIT_COLD;
        } else if (!strncmp(optarg, "fastreconfig", 4)) {
          ctx->init_mode = BF_DEV_WARM_INIT_FAST_RECFG;
        } else if (!strncmp(optarg, "hitless", 4)) {
          ctx->init_mode = BF_DEV_WARM_INIT_HITLESS;
        } else {
          printf(
              "Unknown init mode, expected one of: \"cold\", \"fastreconfig\", "
              "\"hitless\"\nDefaulting to \"cold\"");
          ctx->init_mode = BF_DEV_INIT_COLD;
        }
        break;
      case OPT_NO_PI:
        ctx->no_pi = true;
        break;
      case 'h':
      case '?':
        printf("bf_switchd \n");
        printf("Usage: bf_switchd --conf-file <file> [OPTIONS]...\n");
        printf("\n");
        printf(" --install-dir=directory that has installed build artifacts\n");
        printf(" --conf-file=configuration file for bf_switchd\n");
        printf(" --tcp-port-base=TCP port base to be used for DMA sim\n");
        printf(" --skip-p4 Skip loading P4 program\n");
        printf(" --skip-hld Skip high level drivers\n");
        printf(
            "   p:pipe_mgr, m:mc_mgr, k:pkt_mgr, r:port_mgr, t:traffic_mgr\n");
        printf(" --skip-port-add Skip adding ports\n");
        printf(" --background Disable interactive features so bf_switchd\n");
        printf("              can run in the background\n");
        printf(" --init-mode Specify cold boot or warm init mode\n");
        printf(
            " cold:Cold boot device, fastreconfig:Apply fast reconfig to "
            "device\n");
        printf(
            " --no-pi Do not activate PI even if it was enabled at compile "
            "time\n");
        printf(" -h,--help Display this help message and exit\n");
        exit(c == 'h' ? 0 : 1);
        break;
    }
  }

  /* Sanity check args */
  if ((ctx->install_dir == NULL) || (ctx->conf_file == NULL)) {
    printf("ERROR: --install-dir and --conf-file must be specified\n");
    exit(0);
  }
}

static void coverage_handler(int signum) {
  printf("bf_switchd:received signal %d\n", signum);
#ifdef COVERAGE_ENABLED
  extern void __gcov_flush(void);
  /* coverage signal handler to allow flush of coverage data*/
  __gcov_flush(); /* dump coverage data on receiving SIGUSR1 */
#endif
  exit(-1);
}

static void setup_coverage_sighandler() {
  struct sigaction new_action;
  /* setup signal hander */
  new_action.sa_handler = coverage_handler;
  sigemptyset(&new_action.sa_mask);
  new_action.sa_flags = 0;

  sigaction(SIGKILL, &new_action, NULL);
  sigaction(SIGTERM, &new_action, NULL);
  sigaction(SIGQUIT, &new_action, NULL);
}

//----------------------------------------------------------------------
// Handler when receiving USR1 signal.
// The main program starts to periodically poll registers when loop_flag = true, stops when loop_flag = false.
// The signal-receiving thread starts monitoring CPU-switch interface when signal_flag = true, stops when signal_flag = false;
//----------------------------------------------------------------------
static bool loop_flag = false;
static bool signal_flag = false;  
static void sigusr1_handler(int signum) {
  printf("printqueue: received signal %d, flip loop_flag and signal_flag\n", signum);
  if(loop_flag) {
    loop_flag = false;
    signal_flag = false;
  }
  else {
    loop_flag = true;
    signal_flag = true;
  }
}

//----------------------------------------------------------------------
// Handler when receiving USR2 signal.
// The main program ends when running_flag = false.
//----------------------------------------------------------------------
static bool running_flag = true;
static void sigusr2_handler(int signum) {
  printf("printqueue: received signal %d, flip running_flag\n", signum);
  if(running_flag) {
    running_flag = false;
  }
  else {
    running_flag = true;
  }
}

//----------------------------------------------------------------------
// The following function range read registers of time windows.
// Based on the C API provided after compilation, the following
// code gets rid of some unneccessary parts to achieve higher reading
// speed and less used memory.
//-----------------------------------------------------------------------
p4_pd_status_t
p4_pd_time_windows_register_range_read
(
 p4_pd_sess_hdl_t sess_hdl,
 p4_pd_dev_target_t dev_tgt,
 int index,
 int count,
 int flags,
 int *num_actually_read,
 uint8_t *register_values,
 int *value_count,
 int output_pipe_id,
 int T
)
{
  p4_pd_status_t status;
  dev_target_t pipe_mgr_dev_tgt;
  pipe_mgr_dev_tgt.device_id = dev_tgt.device_id;
  pipe_mgr_dev_tgt.dev_pipe_id = dev_tgt.dev_pipe_id;

  uint32_t pipe_api_flags = flags & REGISTER_READ_HW_SYNC ?
                            PIPE_FLAG_SYNC_REQ : 0;
  /* Get the maximum number of elements the query can return. */
  int pipe_count, num_vals_per_pipe;
  status = pipe_stful_query_get_sizes(sess_hdl,
                                      dev_tgt.device_id,
                                      100663301,
                                      &pipe_count,
                                      &num_vals_per_pipe);
  if(status != PIPE_MGR_SUCCESS) return status;
  /* Allocate space for the query results. */
  pipe_stful_mem_query_t *stful_query = bf_sys_calloc(count, sizeof *stful_query);
  pipe_stful_mem_spec_t **pipe_data = bf_sys_calloc(pipe_count * count, sizeof *pipe_data);
  pipe_stful_mem_spec_t *stage_data = bf_sys_calloc(pipe_count * num_vals_per_pipe * count, sizeof *stage_data);
  if (!stful_query || !pipe_data || !stage_data) {
    status = PIPE_NO_SYS_RESOURCES;
    goto free_query_data;
  }

  for (int j=0; j<count; ++j) {
    stful_query[j].pipe_count = pipe_count;
    stful_query[j].instance_per_pipe_count = num_vals_per_pipe;
    stful_query[j].data = pipe_data + (pipe_count * j);
    for (int o=0; o<pipe_count; ++o) {
      stful_query[j].data[o] = stage_data + (pipe_count * j * num_vals_per_pipe) + (num_vals_per_pipe * o);
    }
  }
//   printf("pipe count: %d, instance_per_pipe_count: %d, count: %d\n", pipe_count, num_vals_per_pipe, count);
 
    // ------------------------------------------------------------------------------------------------------------------
    //   Please check and modify the handle_id under your environment. 
    //   They can be found at your $SDE/pkgsrc/p4-build/tofino/printqueue/src/pd.c after compilation.
    //   When the number of time windows changes, remember to modify the number of elements in handle_id
    //-------------------------------------------------------------------------------------------------------------------
    int handle_id_data_query[] = {100663301, 100663302, 100663303, // TW0: tts, srcIP, dstIP
                            100663306, 100663307, 100663308,       // TW1: tts, srcIP, dstIP
                            100663311, 100663312, 100663313,       // TW2: tts, srcIP, dstIP
                            100663316, 100663317, 100663318        // TW3: tts, srcIP, dstIP
                          };
    uint total = 0;
    for (int rn = 0; rn < T * 3; rn ++){
        /* Perform the query.*/
        // ------------------------------------------------------------------------------------
        // The following function accepts the handle id. Change according to your setting.
        //------------------------------------------------------------------------------------
        status = pipe_stful_ent_query_range(sess_hdl, pipe_mgr_dev_tgt,
                                            handle_id_data_query[rn], index, count,
                                            stful_query, num_actually_read,
                                            pipe_api_flags);

        // if(status != PIPE_MGR_SUCCESS) goto free_query_data;
        /* Convert the query data to PD format. */
        *value_count = 0;
        // printf("num_actual_read: %d\n", *num_actually_read);
        for (int i=0; i<*num_actually_read; ++i) {
            *value_count += 1 * stful_query->instance_per_pipe_count;

            for(int s = 0; s < stful_query->instance_per_pipe_count; s++) {
                memcpy(register_values, &(stful_query + i)->data[output_pipe_id][s].word, 4);
                register_values += 4;
                total++;
            }
        }
        // printf("value count: %d\n", *value_count);
    }
    // printf("total: %d\n", total);
  
free_query_data:
  if (stful_query) bf_sys_free(stful_query);
  if (pipe_data) bf_sys_free(pipe_data);
  if (stage_data) bf_sys_free(stage_data);
  return status;
}

//----------------------------------------------------------------------
// The following function range read registers of queue monitor.
// Based on the C API provided after compilation, the following
// code gets rid of some unneccessary parts to achieve higher reading
// speed and less used memory.
//-----------------------------------------------------------------------
p4_pd_status_t
p4_pd_queue_monitor_register_range_read
(
 p4_pd_sess_hdl_t sess_hdl,
 p4_pd_dev_target_t dev_tgt,
 int index,
 int count,
 int flags,
 int *num_actually_read,
 uint8_t *register_values,
 int *value_count,
 int output_pipe_id
)
{
  p4_pd_status_t status;
  dev_target_t pipe_mgr_dev_tgt;
  pipe_mgr_dev_tgt.device_id = dev_tgt.device_id;
  pipe_mgr_dev_tgt.dev_pipe_id = dev_tgt.dev_pipe_id;

  uint32_t pipe_api_flags = flags & REGISTER_READ_HW_SYNC ?
                            PIPE_FLAG_SYNC_REQ : 0;
  /* Get the maximum number of elements the query can return. */
  int pipe_count, num_vals_per_pipe;
  status = pipe_stful_query_get_sizes(sess_hdl,
                                      dev_tgt.device_id,
                                      100663304,
                                      &pipe_count,
                                      &num_vals_per_pipe);
  if(status != PIPE_MGR_SUCCESS) return status;
  /* Allocate space for the query results. */
  pipe_stful_mem_query_t *stful_query = bf_sys_calloc(count, sizeof *stful_query);
  pipe_stful_mem_spec_t **pipe_data = bf_sys_calloc(pipe_count * count, sizeof *pipe_data);
  pipe_stful_mem_spec_t *stage_data = bf_sys_calloc(pipe_count * num_vals_per_pipe * count, sizeof *stage_data);
  if (!stful_query || !pipe_data || !stage_data) {
    status = PIPE_NO_SYS_RESOURCES;
    goto free_query_data;
  }

  for (int j=0; j<count; ++j) {
    stful_query[j].pipe_count = pipe_count;
    stful_query[j].instance_per_pipe_count = num_vals_per_pipe;
    stful_query[j].data = pipe_data + (pipe_count * j);
    for (int o=0; o<pipe_count; ++o) {
      stful_query[j].data[o] = stage_data + (pipe_count * j * num_vals_per_pipe) + (num_vals_per_pipe * o);
    }
  }
//   printf("pipe count: %d, instance_per_pipe_count: %d, count: %d\n", pipe_count, num_vals_per_pipe, count);

    // ------------------------------------------------------------------------------------------------------------------
    //   Please check and modify the handle_id under your environment. They can be found at your pd.c after compilation.
    //-------------------------------------------------------------------------------------------------------------------
    int handle_id[] = {100663304, 100663305,100663306}; // src_ip, dst_ip, seq_num

    uint total = 0;
    for (int rn = 0; rn < 3; rn ++){
        /* Perform the query. */
        // ------------------------------------------------------------------------------------
        // The following function accepts the handle id. Change according to your setting.
        //------------------------------------------------------------------------------------
        status = pipe_stful_ent_query_range(sess_hdl, pipe_mgr_dev_tgt,
                                            handle_id[rn], index, count,
                                            stful_query, num_actually_read,
                                            pipe_api_flags);
        // if(status != PIPE_MGR_SUCCESS) goto free_query_data;
        /* Convert the query data to PD format. */
        *value_count = 0;
        // printf("num_actual_read: %d\n", *num_actually_read);
        for (int i=0; i<*num_actually_read; ++i) {
            *value_count += 1 * stful_query->instance_per_pipe_count;

            for(int s = 0; s < stful_query->instance_per_pipe_count; s++) {
                memcpy(register_values, &(stful_query + i)->data[output_pipe_id][s].word, 4);
                register_values += 4;
                total++;
            }
        }
        // printf("value count: %d\n", *value_count);
    }
    // printf("total: %d\n", total);
  
free_query_data:
  if (stful_query) bf_sys_free(stful_query);
  if (pipe_data) bf_sys_free(pipe_data);
  if (stage_data) bf_sys_free(stage_data);
  return status;
}

// used in transforming address string to uint32
typedef struct ipv4_address{
  union
  {
    struct{
      uint8_t b1, b2, b3, b4;
    } bytes_addr;
    uint32_t uint32_addr;
  } addr;
} ipv4_address_t;

// -------------------------------------------------------------------//
//    The following is the configurable parameters of TIME WINDOWS    //
//                Tune them according to your setting                 //
//--------------------------------------------------------------------//
// for a single port
// k: the cell number of a single time window: 2^k
// T: the number of time windows
// a: compression factor
// duration: the number of seconds for which the periodical register reading lasts
static uint32_t k = 12, T = 4, a = 1, duration = 2, TB0 = 10;
static uint32_t highest_shift_bit = 13, second_highest_shift_bit = 12;  // total registers 2^14
//-----------------------------------------------------------------------------------------------------------------------------------
// -------------------------------------------------------------------//
//    The following is the configurable parameters of QUEUE MONITOR   //
//                Tune them according to your setting                 //
//--------------------------------------------------------------------//
// for a single port
// kq: the cell number of a single queue monitor: 2^kq
// max_qdepth: the maximum qdepth number, must be smaller than 2^kq
// read_interval: the number of microseconds which is the reading interval
// duration_q: the number of seconds for which the periodical register reading lasts
static uint32_t kq = 15, max_qdepth = 25000, read_interval = 100000, duration_q = 5;
static uint32_t highest_shift_bit_q = 16, second_highest_shift_bit_q = 15; // total registers 2^17
//-----------------------------------------------------------------------------------------------------------------------------------
static uint32_t highest[MAX_PORT_NUM], second_highest[MAX_PORT_NUM], cell_number = 0;  // highest i-th item <-> i-th port entry
static bool wrap[MAX_PORT_NUM];

//--------------------------------------------------------------------------//
//                                                                          //
//                      Signal Receiving Thread                             //
//                                                                          //
//--------------------------------------------------------------------------//
//------------------------------------------------------//
//                  Port Isolation                      //
//------------------------------------------------------//
typedef struct port_entry{
  uint16_t port;
  uint16_t isolation_id;
  uint32_t isolation_prefix;
} port_entry_t;
static port_entry_t port_table[MAX_PORT_NUM];
static uint16_t port_entry_num = 0;

typedef struct data_signal{
  struct timeval ts;
  uint32_t type;  // Bitmap: bit 0 = QM data plane query; bit 1 = QM seq overflow; bit 2 = TW data plane query
  uint16_t table_idx;
  uint16_t iso_id;
  uint16_t data_port;
  struct in_addr src_ip;
  struct in_addr dst_ip;
  uint16_t src_port;
  uint16_t dst_port;
  uint32_t enqueue_ts; 
  uint32_t dequeue_ts;
  uint32_t isolation_prefix;
  uint32_t previous_highest;
  uint32_t previous_second_highest;
} data_signal_t;
static data_signal_t data_signal[MAX_PORT_NUM + 2]; // 0 - 16
static uint16_t data_signal_head = 0, data_signal_tail = 0;
static bool new_signal;
static bool poll_ready;
static bool finish_last;

void* listen_on_interface_thread(){
  printf("*********************************************************\nSignal-receiving Thread Initiated\n*********************************************************\n");
  //----------------------------------------------------------------------//
  //                      Create raw socket                               //
  //----------------------------------------------------------------------//
  printf ("Configuring a raw socket...\n");
  int sockfd_rcv;
  if ((sockfd_rcv = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))) == -1) {
    printf("Fail to open the raw socket.\n");
    return false;
  }
  struct ifreq ifr;
  memset(&ifr, 0, sizeof(struct ifreq));
  strncpy(ifr.ifr_name, "bf_pci0", IFNAMSIZ-1);
  if (ioctl(sockfd_rcv, SIOCGIFINDEX, &ifr) < 0) {
    printf("SIOCGIFINDEX failed.\n");
    return false;
  }
  // Promisc, so that even if Ethernet interface filters frames (MAC addr unmatch, broadcast...)
  struct packet_mreq mreq = {0};
  mreq.mr_ifindex = ifr.ifr_ifindex;
  mreq.mr_type = PACKET_MR_PROMISC;
  if (setsockopt(sockfd_rcv, SOL_PACKET, PACKET_ADD_MEMBERSHIP, &mreq, sizeof(mreq)) == -1) {
    printf("setsockopt failed.\n");
    return false;
  }
  struct sockaddr_ll addr = {0};
  addr.sll_family = AF_PACKET;
  addr.sll_ifindex = ifr.ifr_ifindex;
  addr.sll_protocol = htons(ETH_P_ALL);
  if (bind(sockfd_rcv, (struct sockaddr*)&addr, sizeof(addr)) == -1) {
    printf("Bind failed.\n");
    return false;
  }
  char rcv_buf[RCV_BUF_SIZE];
  uint32_t n, enqueue_ts, dequeue_ts, data_port;
  uint16_t rcv_signal, iso_id;
  uint16_t ether_type, src_port, dst_port;
  struct in_addr src_ip, dst_ip;  //network byte order
  printf ("Raw socket configuration succeeds.\n");
  while(running_flag){
    while(signal_flag){
      n = recvfrom(sockfd_rcv, &rcv_buf, RCV_BUF_SIZE-1, 0, NULL, NULL);
      if (n < 14){
        printf("Signal-receiving thread error: reading packet fails!\n");
        signal_flag = false;
        break;
      }
      // parse packet
      memcpy(&ether_type, rcv_buf + 12, 2);
      ether_type = ntohs(ether_type);
      if (ether_type == ETHERTYPE_PRINTQUEUE_SIGNAL){
        if (n < 66) {
          printf("Received an invalid signal packet, length: %d.\n", n);
          continue;
        }
        if ((data_signal_tail + 1) % (MAX_PORT_NUM + 2) == data_signal_head){
          printf("Warning: data signal queue overflows!\n");
          continue;
        }
        memcpy(&src_ip.s_addr, rcv_buf + 26, 4);
        memcpy(&dst_ip.s_addr, rcv_buf + 30, 4);
        memcpy(&src_port, rcv_buf + 34, 2);
        memcpy(&dst_port, rcv_buf + 36, 2);
        memcpy(&rcv_signal, rcv_buf + 54, 2);
        memcpy(&iso_id, rcv_buf + 56, 2);
        memcpy(&enqueue_ts, rcv_buf + 58, 4);
        memcpy(&dequeue_ts, rcv_buf + 62, 4);
        src_port = ntohs(src_port);
        dst_port = ntohs(dst_port);
        rcv_signal = ntohs(rcv_signal);
        iso_id = ntohs(iso_id);
        enqueue_ts = ntohl(enqueue_ts);
        dequeue_ts = ntohl(dequeue_ts);
        data_port = 0;
        for (int i = 0; i < port_entry_num; i++){
          if (port_table[i].isolation_id == iso_id){
            data_signal[data_signal_tail].table_idx = i;
            data_port = port_table[i].port;
            // printf("table index: %d, iso id: %d, iso_pref: %d, data_port:%d\n", i, iso_id, port_table[i].isolation_prefix ,data_port);
            break;
          }
        }
        printf("\n-----------------------------------------------------------------\nPort %d - data plane query signal - src_ip: %s, dst_ip: %s, src_port: %d, dst_port: %d, type: %d, iso_id: %d, enqueue_ts: %lu, dequeue_ts: %lu.\n-----------------------------------------------------------------\n",
              data_port,inet_ntoa(src_ip), inet_ntoa(dst_ip), src_port, dst_port, rcv_signal, iso_id, enqueue_ts, dequeue_ts);

        // receiving a data plane signal - add to the queue
        gettimeofday(&data_signal[data_signal_tail].ts, NULL);
        data_signal[data_signal_tail].type = rcv_signal;
        data_signal[data_signal_tail].src_ip = src_ip;
        data_signal[data_signal_tail].dst_ip = dst_ip;
        data_signal[data_signal_tail].src_port = src_port;
        data_signal[data_signal_tail].dst_port = dst_port;
        data_signal[data_signal_tail].data_port = data_port;
        data_signal[data_signal_tail].iso_id = iso_id;
        data_signal[data_signal_tail].enqueue_ts = enqueue_ts;
        data_signal[data_signal_tail].dequeue_ts = dequeue_ts;
        data_signal[data_signal_tail].isolation_prefix = iso_id << k;
        if (rcv_signal == 2){
          wrap[data_signal[data_signal_tail].table_idx] = true;   //seq num overflow
        }
        //flip highest bit ASAP
        printf("flip highest bit\n");
        data_signal[data_signal_tail].previous_highest = highest[data_signal[data_signal_tail].table_idx];
        highest[data_signal[data_signal_tail].table_idx] ^= 1;
        data_signal[data_signal_tail].previous_second_highest = second_highest[data_signal[data_signal_tail].table_idx] ^ 1;
        data_signal_tail = (data_signal_tail + 1) % (MAX_PORT_NUM + 2);
        new_signal = true;
      }
    }
  }
  printf("Signal-receiving Thread is killed.\n");
  return NULL;
} 

/* bf_switchd main */
int main(int argc, char *argv[]) {
  int ret = 0;
  int agent_idx = 0;
  char bf_sysfs_fname[128];
  FILE *fd;

  bf_switchd_context_t *switchd_main_ctx = NULL;
  /* Allocate memory to hold switchd configuration and state */
  if ((switchd_main_ctx = malloc(sizeof(bf_switchd_context_t))) == NULL) {
    printf("ERROR: Failed to allocate memory for switchd context\n");
    return -1;
  }
  memset(switchd_main_ctx, 0, sizeof(bf_switchd_context_t));

  setup_coverage_sighandler();

//---------------------------------------------------//
//          Register USR1 and USR2 handlers          //
//---------------------------------------------------//
  struct sigaction sa_usr1;
  sa_usr1.sa_handler=&sigusr1_handler;
  sa_usr1.sa_flags=0;
  if(sigaction(SIGUSR1, &sa_usr1, NULL)!=0) {
    fprintf(stderr, "SIGUSR1 handler registration failed for %ld\n", (long)getpid());
    exit(1);
  }

  struct sigaction sa_usr2;
  sa_usr2.sa_handler=&sigusr2_handler;
  sa_usr2.sa_flags=0;
  if(sigaction(SIGUSR2, &sa_usr2, NULL)!=0) {
    fprintf(stderr, "SIGUSR2 handler registration failed for %ld\n", (long)getpid());
    exit(1);
  }

  /* Parse bf_switchd arguments */
  bf_switchd_parse_options(switchd_main_ctx, argc, argv);

  /* determine if kernel mode packet driver is loaded */
  switch_pci_sysfs_str_get(bf_sysfs_fname,
                           sizeof(bf_sysfs_fname) - sizeof("/dev_add"));
  strncat(bf_sysfs_fname, "/dev_add", sizeof("/dev_add"));
  printf("bf_sysfs_fname %s\n", bf_sysfs_fname);
  fd = fopen(bf_sysfs_fname, "r");
  if (fd != NULL) {
    /* override previous parsing if bf_kpkt KLM was loaded */
    printf("kernel mode packet driver present, forcing kernel_pkt option!\n");
    switchd_main_ctx->kernel_pkt = true;
    fclose(fd);
  }

  ret = bf_switchd_lib_init(switchd_main_ctx);


//-----------------------------------------------------------//
//                                                           //
//                PrintQueue Control Plane                   //
//                                                           //
//-----------------------------------------------------------//
  printf("\n\n\n\n\n\n\n\n-----------------------------------------------------\nPrintQueue Control Plane is Activating\n-----------------------------------------------------\n");
  printf("Program ID: %ld\nUse command 'kill -s USR1 %ld', 'kill -s USR2 %ld' to send signals.\n", getpid(), getpid(), getpid());
  printf("Send USR1 signal to switch on/off query process\n");
  printf("Send USR2 signal to kill query process\n\n");

 // Get session handler and device object
  uint32_t sess_hdl = 0;
  uint32_t status_tmp = 0;

  status_tmp = pipe_mgr_client_init(&sess_hdl);
  if(status_tmp!=0) {
    printf("ERROR: Status code: %u", status_tmp);
    exit(1);
  }

  p4_pd_dev_target_t dev_tgt;
  dev_tgt.device_id = 0;
  dev_tgt.dev_pipe_id = 0xffff;

  uint32_t* handlers = (uint32_t*)malloc(sizeof(uint32_t) * HDL_BUF_SIZE);
  memset(handlers, 0, sizeof(uint32_t) * HDL_BUF_SIZE); 

  for (int i = 0; i < MAX_PORT_NUM; i++){
    highest[i] = 0;
    second_highest[i] = 0;
    wrap[i] = false;
  }
  cell_number = 1 << k;

//------------ read registers --------------------
uint actual_read, value_count, value_total = 0;
struct timeval s_us, e_us[MAX_PORT_NUM], initial_us;
//--------------------------------------------------------------------//
//                                                                    //
//                           Port Setting                             //
//                                                                    //
//--------------------------------------------------------------------//
//Port 1/0
bf_pal_front_port_handle_t port_1_0;
port_1_0.conn_id = 1;
port_1_0.chnl_id = 0;
bf_pm_port_add(dev_tgt.device_id, &port_1_0, BF_SPEED_10G, BF_FEC_TYP_NONE);
bf_pm_pltfm_front_port_eligible_for_autoneg(dev_tgt.device_id, &port_1_0, false);
bf_pm_port_enable(dev_tgt.device_id, &port_1_0);
// Port 3/0
bf_pal_front_port_handle_t port_3_0;
port_3_0.conn_id = 3;
port_3_0.chnl_id = 0;
bf_pm_port_add(dev_tgt.device_id, &port_3_0, BF_SPEED_40G, BF_FEC_TYP_NONE);
bf_pm_pltfm_front_port_eligible_for_autoneg(dev_tgt.device_id, &port_3_0, true);
bf_pm_port_enable(dev_tgt.device_id, &port_3_0);
// Port 5/0
bf_pal_front_port_handle_t port_5_0;
port_5_0.conn_id = 5;
port_5_0.chnl_id = 0;
bf_pm_port_add(dev_tgt.device_id, &port_5_0, BF_SPEED_40G, BF_FEC_TYP_NONE);
bf_pm_pltfm_front_port_eligible_for_autoneg(dev_tgt.device_id, &port_5_0, true);
bf_pm_port_enable(dev_tgt.device_id, &port_5_0);
// Port 2/2
bf_pal_front_port_handle_t port_2_2;
port_2_2.conn_id = 2;
port_2_2.chnl_id = 2;
bf_pm_port_add(dev_tgt.device_id, &port_2_2, BF_SPEED_10G, BF_FEC_TYP_NONE);
bf_pm_pltfm_front_port_eligible_for_autoneg(dev_tgt.device_id, &port_2_2, false);
bf_pm_port_enable(dev_tgt.device_id, &port_2_2);

//--------------------------------------------------------------------//
//                                                                    //
//                     Data Plane Query Support                       //
//                                                                    //
//--------------------------------------------------------------------//
//--------------------------------------------------------------------//
//                       Set Threshold Table                          //
//--------------------------------------------------------------------//
//Read data plane query thresholds from the csv file
//when qdepth is larger than the threshold, trigger data plane query
uint32_t THRESHOLD_FLOW_NUMBER = 1024;
p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t* matches = (p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t*) malloc(sizeof(p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t) * THRESHOLD_FLOW_NUMBER);
p4_pd_printqueue_set_threshold_action_spec_t * actions = (p4_pd_printqueue_set_threshold_action_spec_t *) malloc(sizeof(p4_pd_printqueue_set_threshold_action_spec_t) * THRESHOLD_FLOW_NUMBER);
FILE * f = fopen("./src/ctrl/qdepth_threshold.csv", "r");
char *line = NULL, * ptr;
char *fields[3]; 
size_t len = 0;
ssize_t read;
uint32_t first = 0, i = 0, j = 0;
while ((read = getline(&line, &len, f)) != -1) {
    if (first == 0){ // skip first line
      first = 1;
      continue;
    }
    ptr = strtok (line," ");
    i = 0;
    while (ptr != NULL){
      fields[i] = ptr;
      ptr = strtok(NULL, " ");
      i++;
    }
    // CSV line format: srcIP dstIP threshold 
    // src IP
    ipv4_address_t ip_addr;
    sscanf(fields[0],"%u.%u.%u.%u", &ip_addr.addr.bytes_addr.b1, &ip_addr.addr.bytes_addr.b2, &ip_addr.addr.bytes_addr.b3, &ip_addr.addr.bytes_addr.b4);
    matches[j].ipv4_src_addr = ip_addr.addr.uint32_addr;
    // printf("src IP: %lu, ", matches[j].ipv4_src_addr);
    // dst IP
    sscanf(fields[1],"%u.%u.%u.%u", &ip_addr.addr.bytes_addr.b1, &ip_addr.addr.bytes_addr.b2, &ip_addr.addr.bytes_addr.b3, &ip_addr.addr.bytes_addr.b4);
    matches[j].ipv4_dst_addr = ip_addr.addr.uint32_addr;
    // printf("dst IP: %lu, ", matches[j].ipv4_dst_addr);
    // threshold
    sscanf(fields[2], "%lu", &actions[j].action_flow_threshold);
    // printf("threshold: %lu\n", actions[j].action_flow_threshold);
    j++;
}
free(line);
fclose(f);
printf("Adding %d entries to the qdepth_threshold table\n", j);
// populate table entries
for (i = 0; i < j; i++){
  status_tmp = p4_pd_printqueue_qdepth_alerting_threshold_2_table_add_with_set_threshold(sess_hdl, dev_tgt, &matches[i], &actions[i], &handlers[0]);
  if(status_tmp != 0){
    printf("Error adding table entries - qdepth_alerting_threshold_2!\n");
    return false;
  }
}
free(matches);
free(actions);
printf("Successfully set the qdepth_threshold table\n");

//--------------------------------------------------------------------//
//                        Set Mirror Session                          //
//--------------------------------------------------------------------//
// Set up mirror session to clone packets.
// The cloned packets are sent to cpu as signals
// CPU Port is 192, may be different with devices and pipelines
//---------------------------------------------------------------------
uint32_t sid = 3, CPU_PORT = 192;
p4_pd_mirror_session_info_t * mirror_info = (p4_pd_mirror_session_info_t *) malloc(sizeof(p4_pd_mirror_session_info_t));
memset(mirror_info, 0, sizeof(p4_pd_mirror_session_info_t));
mirror_info->type = PD_MIRROR_TYPE_NORM;
mirror_info->dir = PD_DIR_EGRESS;
mirror_info->id = sid;
mirror_info->egr_port = CPU_PORT;
mirror_info->egr_port_v = true;
mirror_info->int_hdr = (uint32_t *)malloc(sizeof(uint32_t)*4);  // there is memory copy later, allocate space to avoid segment fault
mirror_info->int_hdr_len = 0;
mirror_info->max_pkt_len = 100; // Ether + IPv4 + TCP + Signal Header; avoid buffer overflow
status_tmp = p4_pd_mirror_session_create(sess_hdl, dev_tgt, mirror_info);
if (status_tmp != 0){
  printf("Error! Creating mirror session.\n");
  return false;
}
free(mirror_info->int_hdr);
free(mirror_info);
printf("Successfully enable mirror session.\n");

//---------------------------------------------------------------------//
//                                                                     //
//         Local CPU listens on interface of data plane                //
//                                                                     //
//---------------------------------------------------------------------//
//----------------------------------------------------------------------//
//                Create signal-receiving thread                        //
//----------------------------------------------------------------------//
pthread_t signal_thread;
poll_ready = false;
new_signal = false;
finish_last = true;
p4_pd_printqueue_register_reset_all_highest_bit_r(sess_hdl, dev_tgt);
p4_pd_printqueue_register_reset_all_data_query_lock_r(sess_hdl, dev_tgt);
if( pthread_create(&signal_thread, NULL, &listen_on_interface_thread, NULL) != 0){
  printf("Error: creation of signal-receiving thread failed!\n");
  return false;
}
printf("Signal-receiving thread is successfully created with ID %u.\n", signal_thread);

//--------------------------------------------------------------------//
//                  Set Port Isolation Table                          //
//--------------------------------------------------------------------//
p4_pd_printqueue_get_isolation_id_tb_match_spec_t * port_matches = (p4_pd_printqueue_get_isolation_id_tb_match_spec_t *) malloc(sizeof(p4_pd_printqueue_get_isolation_id_tb_match_spec_t) * MAX_PORT_NUM);
p4_pd_printqueue_get_isolation_id_action_spec_t * port_actions = (p4_pd_printqueue_get_isolation_id_action_spec_t *) malloc(sizeof(p4_pd_printqueue_get_isolation_id_action_spec_t) * MAX_PORT_NUM);
f = fopen("./src/ctrl/port_isolation.csv", "r");
line = NULL, ptr = NULL;
len = 0;
read = 0;
first = 0;
i = 0;
j = 0;
while ((read = getline(&line, &len, f)) != -1) {
    if (first == 0){ // skip first line
      first = 1;
      continue;
    }
    ptr = strtok (line," ");
    i = 0;
    while (ptr != NULL){
      fields[i] = ptr;
      ptr = strtok(NULL, " ");
      i++;
    }
    // CSV line format: Port IsolationID
    sscanf(fields[0], "%u", &port_matches[j].ig_intr_md_for_tm_ucast_egress_port);
    sscanf(fields[1], "%u", &port_actions[j].action_iso_id);
    port_actions[j].action_iso_prefix = port_actions[j].action_iso_id << k;
    port_table[j].port = port_matches[j].ig_intr_md_for_tm_ucast_egress_port;
    port_table[j].isolation_id = port_actions[j].action_iso_id;
    port_table[j].isolation_prefix = port_actions[j].action_iso_prefix;
    printf("idx:%d, port: %d, iso_id: %d, iso_pre: %d\n", j, port_table[j].port, port_table[j].isolation_id, port_table[j].isolation_prefix);
    status_tmp = p4_pd_printqueue_get_isolation_id_tb_table_add_with_get_isolation_id(sess_hdl, dev_tgt, &port_matches[j], &port_actions[j], &handlers[0]);
    if(status_tmp != 0){
      printf("Error adding table entries - port isolation!\n");
      return false;
    }
    j++;
}
port_entry_num = j;
free(line);
fclose(f);
free(port_matches);
free(port_actions);
printf("Adding %d entries to the port isolation table\n", port_entry_num);
printf("Successfully isolate ports\n");
//--------------------------------------------------------------------------//

// Time windows or queue monitor is loaded. Comment one and uncomment the other
// /*--------------------------------------------------------------------*/
// /*                                                                    */
// /*                      Time          Windows                         */
// /*                                                                    */
// /*--------------------------------------------------------------------*/
printf("\n\n-----------------------------------------------------\nTime Windows is Activating\n-----------------------------------------------------\n\n");
uint32_t estimated_retrieve_interval = 0, data_query_start = 0, data_query_num = 0, data_query_end = 0, storage_start = 0, index = 0;
int32_t available_interval = 0;
double reading_ratio = 0.05;
// set second highest bit
p4_pd_printqueue_prepare_TW0_tb_match_spec_t second_highest_matches[MAX_PORT_NUM];
p4_pd_printqueue_prepare_TW0_action_spec_t second_highest_actions[MAX_PORT_NUM];
for (i = 0; i < port_entry_num; i++){
  second_highest_matches[i].PQ_md_isolation_id = port_table[i].isolation_id;
  second_highest_actions[i].action_second_highest = second_highest[i];
  status_tmp = p4_pd_printqueue_prepare_TW0_tb_table_add_with_prepare_TW0(sess_hdl, dev_tgt, &second_highest_matches[i], &second_highest_actions[i], &handlers[0]);
  if(status_tmp != 0){
    printf("Error adding table entries - prepare TW0!\n");
    return false;
  }
}
for (i = 0; i < port_entry_num; i++){
  second_highest[i] = 1; 
}
//--------------------------------------------------------------
// The value of the second highest bit is the NEXT period's
// But the value of the highest bit is the CURRENT period's
//--------------------------------------------------------------
printf("Successfully set the second highest bit\n");
uint64_t retrieve_interval = ((1 << (a * T)) - 1) * (1 << (k + TB0)) / ((1<<a)-1) / 1000 - 100; // us, give a little time ahead to trigger reading
printf("Time window retrieve interval: %ld us\n", retrieve_interval);
//initialize buffer used to store register values
uint8_t buffer[245760];
uint8_t data_query_buffer[245760], data_query_tmp_buffer[245760];
char data_dir[100];
char sig_data_dir[100];
uint32_t delta_time;
memset(buffer, 0, 245760);
memset(data_dir, 0, 100);
uint32_t per_round_count = 0;
while(running_flag){
    gettimeofday(&initial_us, NULL);
    for (i = 0; i < port_entry_num; i ++){
      gettimeofday(&e_us[i], NULL);
    }
    while(loop_flag){
      for (i = 0; i < port_entry_num; i++){
        gettimeofday(&s_us, NULL);
        delta_time = (s_us.tv_sec - e_us[i].tv_sec) * 1000000 + s_us.tv_usec - e_us[i].tv_usec;
        if(delta_time >= retrieve_interval){
          if (i == 0){
            per_round_count = 0;
          }
          second_highest_actions[i].action_second_highest = second_highest[i] << second_highest_shift_bit;
          status_tmp = p4_pd_printqueue_prepare_TW0_tb_table_modify_with_prepare_TW0_by_match_spec(sess_hdl,dev_tgt, &second_highest_matches[i], &second_highest_actions[i]);
          gettimeofday(&e_us[i], NULL);
          if(status_tmp!=0) {
            printf("Error port %d setting second highest bit!\n", port_table[i].port);
            return false;
          }
          second_highest[i] ^= 1;
          // read just recorded TW
          printf("Periodical reading - port: %d, h: %d, sh: %d, iso_id: %d, iso_prefix: %d", port_table[i].port, highest[i], second_highest[i], port_table[i].isolation_id, port_table[i].isolation_prefix);
          index = port_table[i].isolation_prefix + (second_highest[i] << second_highest_shift_bit) + (highest[i] << highest_shift_bit);
          p4_pd_time_windows_register_range_read(sess_hdl, dev_tgt, index, cell_number, 1, &actual_read, buffer, &value_count, 1, T);
          // store the register values
          sprintf(data_dir, "./tw_data/%d/tw_data/%ld_%ld.bin",i, e_us[i].tv_sec, e_us[i].tv_usec);  // e_us is the time after the operation of bit flip, also the start of the reading
          FILE * f = fopen(data_dir, "wb");
          fwrite(buffer, 1, cell_number * 12 * T, f);
          fclose(f);
          memset(buffer, 0, 245760);
          memset(data_dir, 0, 100);
          gettimeofday(&s_us, NULL);
          estimated_retrieve_interval = ( s_us.tv_sec - e_us[i].tv_sec ) * 1000000 + s_us.tv_usec - e_us[i].tv_usec;
          available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + retrieve_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
          printf("\nPort %d, periodiocal poll finishes, it needs: %d us, %d us til next round.\n", port_table[i].port ,estimated_retrieve_interval,available_interval);
          per_round_count += 1;
        }
      }
      gettimeofday(&s_us, NULL);
      if (s_us.tv_sec - initial_us.tv_sec > duration){
          printf("\nTime window retrieve Ends!\n");
          loop_flag = false;
          signal_flag = false;
          break;
        }
      available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + retrieve_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
      if (available_interval < 2000){
        // printf("*");
        continue;
      }
      //-----------------------------------------------------------------------------------//
      //                               Data Plane Query                                    //
      //-----------------------------------------------------------------------------------//
      if (per_round_count == port_entry_num){
        if (!poll_ready && finish_last){
          if (estimated_retrieve_interval && new_signal){
            memset(data_query_buffer, 0, 245760);
            poll_ready = true;
            finish_last = false;
          }
        }
        if (poll_ready && !finish_last){
          // store signal pkt information in the file : [type | enqueue_ts | dequeue_ts]
          memset(sig_data_dir, 0, 100);
          sprintf(sig_data_dir, "./tw_data/%d/signal_data/%ld_%ld.bin", data_signal[data_signal_head].table_idx, data_signal[data_signal_head].ts.tv_sec, data_signal[data_signal_head].ts.tv_usec); 
          printf("Data plane - port %d, h: %d, sh: %d, iso id: %d, iso prefix: %d, table idx: %d, write signal to file: %s.\n", data_signal[data_signal_head].data_port, data_signal[data_signal_head].previous_highest, data_signal[data_signal_head].previous_second_highest, data_signal[data_signal_head].iso_id, data_signal[data_signal_head].isolation_prefix, data_signal[data_signal_head].table_idx, sig_data_dir);
          FILE * f = fopen(sig_data_dir, "wb");
          fwrite(&data_signal[data_signal_head].type, 4, 1, f);
          fwrite(&data_signal[data_signal_head].enqueue_ts, 4, 1, f);
          fwrite(&data_signal[data_signal_head].dequeue_ts, 4, 1, f);
          fclose(f);
          data_query_start = data_signal[data_signal_head].isolation_prefix + (data_signal[data_signal_head].previous_highest << highest_shift_bit) + (data_signal[data_signal_head].previous_second_highest << second_highest_shift_bit);
          data_query_end = data_query_start + cell_number;
          storage_start = 0;
          poll_ready = false;
        }
        if (!poll_ready && !finish_last){
          gettimeofday(&s_us, NULL);
          available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + retrieve_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
          if (available_interval < 5000){
            // printf("x:%d",available_interval);
            continue;
          }      
          data_query_num = floor(((double)available_interval / (double)estimated_retrieve_interval) * reading_ratio * (double)cell_number);
          if (data_query_start + data_query_num >= data_query_end){
            printf(".\n");
            data_query_num = data_query_end - data_query_start;
          }
          if(data_query_num != 0){
            printf("Available interval: %d us. Read %d entries.\n", available_interval, data_query_num );
            memset(data_query_tmp_buffer, 0, 245760);
            p4_pd_time_windows_register_range_read(sess_hdl, dev_tgt, data_query_start, data_query_num, 1, &actual_read, data_query_tmp_buffer, &value_count, 1, T);
            data_query_start += data_query_num;
            printf("✓ reading\n");
            for (int i = 0; i < T; i++){
              memcpy(data_query_buffer + 12 * cell_number * i + storage_start * 4, data_query_tmp_buffer + 12 * data_query_num * i, data_query_num * 4);
              memcpy(data_query_buffer + 12 * cell_number * i + storage_start * 4 + cell_number * 4, data_query_tmp_buffer + 12 * data_query_num * i + data_query_num * 4, data_query_num * 4);
              memcpy(data_query_buffer + 12 * cell_number * i + storage_start * 4 + cell_number * 8, data_query_tmp_buffer + 12 * data_query_num * i + data_query_num * 8, data_query_num * 4);
            }
            storage_start += data_query_num;
            printf("✓ memory copy \n");
          }
          if (data_query_start == data_query_end){
            gettimeofday(&s_us, NULL);
            available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + retrieve_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
            if (available_interval < 2500){
              printf(" W ");
              continue;
            }
            // all registers are read
            sprintf(data_dir, "./tw_data/%d/tw_data/%ld_%ld.bin", data_signal[data_signal_head].table_idx ,data_signal[data_signal_head].ts.tv_sec, data_signal[data_signal_head].ts.tv_usec);  // start of reading
            printf("Port %d, tw store in %s\n", data_signal[data_signal_head].data_port, data_dir);
            FILE * f = fopen(data_dir, "wb");
            fwrite(data_query_buffer, 1, cell_number * 12 * T, f);
            fclose(f);
            memset(data_dir, 0, 100);
            // unlock data plane
            p4_pd_printqueue_register_range_reset_data_query_lock_r(sess_hdl, dev_tgt, data_signal[data_signal_head].iso_id, 1);
            data_signal_head = (data_signal_head + 1) % (MAX_PORT_NUM + 2);
            if (data_signal_head == data_signal_tail){
              printf("Data signal queue is empty\n");
              new_signal = false;
            }
            finish_last = true;
          }
          gettimeofday(&s_us, NULL);
          available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + retrieve_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
          printf("✓ %d us left till next periodical poll\n", available_interval);
        }
        gettimeofday(&s_us, NULL);
        if (s_us.tv_sec - initial_us.tv_sec > duration){
          printf("\nTime window retrieve Ends!\n");
          loop_flag = false;
          signal_flag = false;
        }
      }
    }
}

/*--------------------------------------------------------------------*/
/*                                                                    */
/*                    Queue            Monitor                        */
/*                                                                    */
/*--------------------------------------------------------------------*/
// printf("\n\n-----------------------------------------------------\nQueue Monitor is Activating\n-----------------------------------------------------\n\n"  );
// uint32_t time_pass = 0, index = 0, estimated_retrieve_interval = 0, data_query_start = 0, data_query_num = 0, data_query_end = 0, storage_start = 0;
// int32_t available_interval = 0;
// double reading_ratio = 0.05;
// printf("Queue monitor retrieve interval: %ld us\n", read_interval);

// // set second highest bit
// p4_pd_printqueue_prepare_qm_tb_match_spec_t second_highest_matches[MAX_PORT_NUM];
// p4_pd_printqueue_prepare_qm_action_spec_t second_highest_actions[MAX_PORT_NUM];
// for (i = 0; i < port_entry_num; i++){
//   second_highest_matches[i].PQ_md_isolation_id = port_table[i].isolation_id;
//   second_highest_actions[i].action_second_highest = second_highest[i];
//   status_tmp = p4_pd_printqueue_prepare_qm_tb_table_add_with_prepare_qm(sess_hdl, dev_tgt, &second_highest_matches[i], &second_highest_actions[i], &handlers[0]);
//   if(status_tmp != 0){
//     printf("Error adding table entries - prepare TW0!\n");
//     return false;
//   }
// }
// for (i = 0; i < port_entry_num; i++){
//   second_highest[i] = 1; 
// }
// //initialize buffers used to store register values
// uint8_t buffer[300000];
// uint8_t data_query_buffer[300000], data_query_tmp_buffer[300000];
// char data_dir[100], sig_data_dir[100];
// memset(buffer, 0, 300000);
// memset(data_dir, 0, 100);
// uint32_t per_round_count = 0;
// while(running_flag){
//   gettimeofday(&initial_us, NULL);
//   for (i = 0; i < port_entry_num; i ++){
//       gettimeofday(&e_us[i], NULL);
//   }
//   while(loop_flag){
//       for (i = 0; i < port_entry_num; i++){
//         gettimeofday(&s_us, NULL);
//         time_pass = (s_us.tv_sec - e_us[i].tv_sec) * 1000000 + s_us.tv_usec - e_us[i].tv_usec;
//         if (time_pass >= read_interval){
//           if  (i == 0){
//             per_round_count = 0;
//           }
//           second_highest_actions[i].action_second_highest = second_highest[i] << second_highest_shift_bit_q;
//           status_tmp = p4_pd_printqueue_prepare_qm_tb_table_modify_with_prepare_qm_by_match_spec(sess_hdl, dev_tgt, &second_highest_matches[i], &second_highest_actions[i]);
//           gettimeofday(&e_us[i], NULL);
//           if(status_tmp!=0) {
//             printf("Error setting second highest bit!\n");
//             return false;
//           }
//           second_highest[i] ^= 1;
//           // read and reset just recorded QM
//           printf("Periodical reading - port: %d, h: %d, sh: %d, iso_id: %d, iso_prefix: %d", port_table[i].port, highest[i], second_highest[i], port_table[i].isolation_id, port_table[i].isolation_prefix);
//           index = port_table[i].isolation_prefix + (second_highest[i] << second_highest_shift_bit_q) + (highest[i] << highest_shift_bit_q);
//           p4_pd_queue_monitor_register_range_read(sess_hdl, dev_tgt, index, max_qdepth, 1, &actual_read, buffer, &value_count, 1);
//           // reset registers after read: only store delta data
//           p4_pd_printqueue_register_range_reset_src_ip_r(sess_hdl, dev_tgt, index, max_qdepth);
//           p4_pd_printqueue_register_range_reset_dst_ip_r(sess_hdl, dev_tgt, index, max_qdepth); 
//           p4_pd_printqueue_register_range_reset_seq_array_r(sess_hdl, dev_tgt, index, max_qdepth);
//           // store the register values
//           if (wrap[i]){
//             sprintf(data_dir, "./qm_data/%d/qm_data/%ld_%ld_1.bin",i,e_us[i].tv_sec,e_us[i].tv_usec); // e_us is the time after the operatin of bit flip, also the start of the reading
//             wrap[i] = false;
//           }else{
//             sprintf(data_dir, "./qm_data/%d/qm_data/%ld_%ld_0.bin",i,e_us[i].tv_sec,e_us[i].tv_usec); // e_us is the time after the operatin of bit flip, also the start of the reading
//           }
//           FILE * f = fopen(data_dir, "wb");
//           fwrite(buffer, 1, 300000, f);
//           fclose(f);
//           memset(buffer, 0, 300000);
//           memset(data_dir, 0, 100);
//           gettimeofday(&s_us, NULL);
//           estimated_retrieve_interval = ( s_us.tv_sec - e_us[i].tv_sec ) * 1000000 + s_us.tv_usec - e_us[i].tv_usec;
//           available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + read_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
//           printf("\nPort %d, periodiocal poll finishes, it needs: %d us, %d us til next round.\n", port_table[i].port ,estimated_retrieve_interval,available_interval);
//           per_round_count += 1;
//         }
//       }
//       gettimeofday(&s_us, NULL);
//       if (s_us.tv_sec - initial_us.tv_sec > duration_q){
//           printf("\nQueue Monitor retrieve Ends!\n");
//           loop_flag = false;
//           signal_flag = false;
//           break;
//         }
//       available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + read_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
//       if (available_interval < 2000){
//         // printf("*");
//         continue;
//       }
//       //-----------------------------------------------------------------------------------//
//       //                               Data Plane Query                                    //
//       //-----------------------------------------------------------------------------------//
//       if (per_round_count == port_entry_num){
//         if (!poll_ready && finish_last){
//           if (estimated_retrieve_interval && new_signal){
//             memset(data_query_buffer, 0, 300000);
//             poll_ready = true;
//             finish_last = false;
//           }
//         }
//         if (poll_ready && !finish_last){
//           memset(sig_data_dir, 0, 100);
//           sprintf(sig_data_dir, "./qm_data/%d/signal_data/%ld_%ld.bin", data_signal[data_signal_head].table_idx, data_signal[data_signal_head].ts.tv_sec, data_signal[data_signal_head].ts.tv_usec); 
//           printf("Data plane - port %d, h: %d, sh: %d, iso id: %d, iso prefix: %d, table idx: %d, write signal to file: %s.\n", data_signal[data_signal_head].data_port, data_signal[data_signal_head].previous_highest, data_signal[data_signal_head].previous_second_highest, data_signal[data_signal_head].iso_id, data_signal[data_signal_head].isolation_prefix, data_signal[data_signal_head].table_idx, sig_data_dir);
//           FILE * f = fopen(sig_data_dir, "wb");
//           fwrite(&data_signal[data_signal_head].type, 4, 1, f);
//           fclose(f);
//           data_query_start = data_signal[data_signal_head].isolation_prefix + (data_signal[data_signal_head].previous_highest << highest_shift_bit_q) + (data_signal[data_signal_head].previous_second_highest << second_highest_shift_bit_q);
//           data_query_end = data_query_start + max_qdepth;
//           storage_start = 0;
//           poll_ready = false;
//         }
//         if (!poll_ready && !finish_last){
//           gettimeofday(&s_us, NULL);
//           available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + read_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
//           if (available_interval < 15000){
//             // printf("x");
//             continue;
//           }  
//           data_query_num = floor(((double)available_interval / (double)estimated_retrieve_interval) * reading_ratio * (double)max_qdepth);
//           if (data_query_start + data_query_num >= data_query_end){
//             printf(".\n");
//             data_query_num = data_query_end - data_query_start;
//           }
//           if(data_query_num != 0){
//             printf("Available interval: %d us. Read %d entries.\n", available_interval, data_query_num);
//             memset(data_query_tmp_buffer, 0, 300000);
//             p4_pd_queue_monitor_register_range_read(sess_hdl, dev_tgt, data_query_start, data_query_num, 1, &actual_read, data_query_tmp_buffer, &value_count, 1);
//             p4_pd_printqueue_register_range_reset_src_ip_r(sess_hdl, dev_tgt, data_query_start, data_query_num);
//             p4_pd_printqueue_register_range_reset_dst_ip_r(sess_hdl, dev_tgt, data_query_start, data_query_num); 
//             p4_pd_printqueue_register_range_reset_seq_array_r(sess_hdl, dev_tgt, data_query_start, data_query_num);
//             data_query_start += data_query_num;
//             printf("✓ reading\n");
//             memcpy(data_query_buffer + storage_start * 4, data_query_tmp_buffer, data_query_num * 4);
//             memcpy(data_query_buffer + storage_start * 4 + max_qdepth * 4, data_query_tmp_buffer + data_query_num * 4, data_query_num * 4);
//             memcpy(data_query_buffer + storage_start * 4 + max_qdepth * 8, data_query_tmp_buffer + data_query_num * 8, data_query_num * 4);
//             storage_start += data_query_num;
//             printf("✓ memory copy \n");
//           }
//           if (data_query_start == data_query_end){
//             gettimeofday(&s_us, NULL);
//             available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + read_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
//             if (available_interval < 2500){
//               printf(" W ");
//               continue;
//             }
//             // all registers are read
//             sprintf(data_dir, "./qm_data/%d/qm_data/%ld_%ld_0.bin",data_signal[data_signal_head].table_idx, data_signal[data_signal_head].ts.tv_sec, data_signal[data_signal_head].ts.tv_usec);  // start of reading
//             printf("Port %d, tw store in %s\n", data_signal[data_signal_head].data_port, data_dir);
//             FILE * f = fopen(data_dir, "wb");
//             fwrite(data_query_buffer, 1, 300000, f);
//             fclose(f);
//             memset(data_dir, 0, 100);
//             // unlock data plane
//             p4_pd_printqueue_register_range_reset_data_query_lock_r(sess_hdl, dev_tgt, data_signal[data_signal_head].iso_id, 1);
//             data_signal_head = (data_signal_head + 1) % (MAX_PORT_NUM + 2);
//             if (data_signal_head == data_signal_tail){
//               printf("Data signal queue is empty\n");
//               new_signal = false;
//             }
//             finish_last = true;
//           }
//           gettimeofday(&s_us, NULL);
//           available_interval = e_us[0].tv_sec * 1000000 + e_us[0].tv_usec + read_interval - (s_us.tv_sec * 1000000 + s_us.tv_usec);
//           printf("✓ %d us left till next periodical poll\n", available_interval);
//         }
//         gettimeofday(&s_us, NULL);
//         if (s_us.tv_sec - initial_us.tv_sec > duration_q){
//           printf("\nQueue monitor retrieve Ends!\n");
//           loop_flag = false;
//           signal_flag = false;
//         }
//       }
//   }
// }

//----------------------------------------------------//
//          End of PrintQueue Control Plane           //
//----------------------------------------------------//
  pthread_join(signal_thread, NULL);
  pthread_join(switchd_main_ctx->tmr_t_id, NULL);
  pthread_join(switchd_main_ctx->dma_t_id, NULL);
  pthread_join(switchd_main_ctx->int_t_id, NULL);
  pthread_join(switchd_main_ctx->pkt_t_id, NULL);
  pthread_join(switchd_main_ctx->port_fsm_t_id, NULL);
  pthread_join(switchd_main_ctx->drusim_t_id, NULL);
  pthread_join(switchd_main_ctx->mav_diag_t_id, NULL);
  for (agent_idx = 0; agent_idx < BF_SWITCHD_MAX_AGENTS; agent_idx++) {
    if (switchd_main_ctx->agent_t_id[agent_idx] != 0) {
      pthread_join(switchd_main_ctx->agent_t_id[agent_idx], NULL);
    }
  }

  if (switchd_main_ctx)free(switchd_main_ctx);
  if (handlers) free(handlers);
  return ret;
}
