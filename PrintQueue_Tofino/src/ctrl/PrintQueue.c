
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

/* Local includes */
#include "bf_switchd.h"
#include "switch_config.h"
#include "pd/pd.h"

#define PIPE_MGR_SUCCESS 0
#define HDL_BUF_SIZE 100

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
// The main program starts to periodically poll registers when 
// loop_flag = true, stops when loop_flag = false.
//----------------------------------------------------------------------
static bool loop_flag = false;
static void sigusr1_handler(int signum) {
  printf("printqueue: received signal %d, flip loop_flag\n", signum);
  if(loop_flag) {
    loop_flag = false;
  }
  else {
    loop_flag = true;
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
                                      100663297,
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
    int handle_id[] = {100663297, 100663298, 100663299,       // TW0: tts, srcIP, dstIP
                       100663302, 100663303, 100663304,       // TW1: tts, srcIP, dstIP
                       100663307, 100663308, 100663309,       // TW2: tts, srcIP, dstIP
                       100663312, 100663313, 100663314};      // TW3: tts, srcIP, dstIP
                      //  100663317, 100663318, 100663319};

    int handle_id_data_query[] = {100663300, 100663301, 100663302, 
                            100663305, 100663306, 100663307,
                            100663310, 100663311, 100663312,
                            100663315, 100663316, 100663317
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
                                      100663303,
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
    int handle_id[] = {100663303, 100663304,100663305}; // src_ip, dst_ip, seq_num

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
  printf("Program ID: %ld\nUse command 'kill -s USR1 %ld', 'kill -s USR2 %ld' to send signals\n\n", getpid(), getpid(), getpid());

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

//------------ read registers --------------------
uint actual_read, value_count, value_total = 0;
struct timeval s_us, e_us, initial_us;

//--------------------------------------------------------------------//
//                                                                    //
//                           Port Setting                             //
//                                                                    //
//--------------------------------------------------------------------//
// Port 1/0
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

//--------------------------------------------------------------------//
//                                                                    //
//                     Data Plane Query Support                       //
//                                                                    //
//--------------------------------------------------------------------//
//--------------------------------------------------------------------//
//                        Set Mirror Session                          //
//--------------------------------------------------------------------//
// Set up mirror session to clone packets.
// The cloned packets are sent to cpu as signals
// CPU Port is 192, may be different with devices and pipelines
//-----------------------------------------------------------------
uint32_t sid = 3, CPU_PORT = 192;
p4_pd_mirror_session_info_t mirror_info;
mirror_info.type = PD_MIRROR_TYPE_NORM;
mirror_info.dir = PD_DIR_BOTH;
mirror_info.id = sid;
mirror_info.egr_port = CPU_PORT;
mirror_info.egr_port_v = true;
status_tmp = p4_pd_mirror_session_create(sess_hdl, dev_tgt, &mirror_info);
if (status_tmp != 0){
  printf("Error! Creating mirror session.\n");
  return false;
}
printf("Successfully enable mirror session.\n");

//--------------------------------------------------------------------//
//                       Set Threshold Table                          //
//--------------------------------------------------------------------//
//Read data plane query thresholds from the csv file
//when qdepth is larger than the threshold, trigger data plane query
// uint32_t THRESHOLD_FLOW_NUMBER = 1024;
// p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t* matches = (p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t*) malloc(sizeof(p4_pd_printqueue_qdepth_alerting_threshold_2_match_spec_t) * THRESHOLD_FLOW_NUMBER);
// p4_pd_printqueue_set_threshold_action_spec_t * actions = (p4_pd_printqueue_set_threshold_action_spec_t *) malloc(sizeof(p4_pd_printqueue_set_threshold_action_spec_t) * THRESHOLD_FLOW_NUMBER);
// FILE * f = fopen("./src/ctrl/qdepth_threshold.csv", "r");
// char *line = NULL, * ptr;
// char *fields[3]; 
// size_t len = 0;
// ssize_t read;
// uint32_t first = 0, i = 0, j = 0;
// while ((read = getline(&line, &len, f)) != -1) {
//     if (first == 0){ // skip first line
//       first = 1;
//       continue;
//     }
//     ptr = strtok (line," ");
//     i = 0;
//     while (ptr != NULL){
//       fields[i] = ptr;
//       ptr = strtok(NULL, " ");
//       i++;
//     }
//     // CSV line format: srcIP dstIP threshold 
//     // src IP
//     ipv4_address_t ip_addr;
//     sscanf(fields[0],"%u.%u.%u.%u", &ip_addr.addr.bytes_addr.b1, &ip_addr.addr.bytes_addr.b2, &ip_addr.addr.bytes_addr.b3, &ip_addr.addr.bytes_addr.b4);
//     matches[j].ipv4_src_addr = ip_addr.addr.uint32_addr;
//     // printf("src IP: %lu, ", matches[j].ipv4_src_addr);
//     // dst IP
//     sscanf(fields[1],"%u.%u.%u.%u", &ip_addr.addr.bytes_addr.b1, &ip_addr.addr.bytes_addr.b2, &ip_addr.addr.bytes_addr.b3, &ip_addr.addr.bytes_addr.b4);
//     matches[j].ipv4_dst_addr = ip_addr.addr.uint32_addr;
//     // printf("dst IP: %lu, ", matches[j].ipv4_dst_addr);
//     // threshold
//     sscanf(fields[2], "%lu", &actions[j].action_flow_threshold);
//     // printf("threshold: %lu\n", actions[j].action_flow_threshold);
//     j++;
// }
// free(line);
// fclose(f);
// printf("Adding %d entries to the qdepth_threshold table\n", j);
// // populate table entries
// for (i = 0; i < j; i++){
//   status_tmp = p4_pd_printqueue_qdepth_alerting_threshold_2_table_add_with_set_threshold(sess_hdl, dev_tgt, &matches[i], &actions[i], &handlers[0]);
//   if(status_tmp != 0){
//     printf("Error adding table entries - qdepth_alerting_threshold_2!\n");
//     return false;
//   }
// }
// free(matches);
// free(actions);
// printf("Successfully set the qdepth_threshold table\n");

// Time windows or queue monitor is loaded. Comment one and uncomment the other
/*--------------------------------------------------------------------*/
/*                                                                    */
/*                      Time          Windows                         */
/*                                                                    */
/*--------------------------------------------------------------------*/
// printf("-----------------------------------------------------\nTime Windows is Activating\n-----------------------------------------------------\n");
// // -------------------------------------------------------------------//
// //           The following is the configurable parameters             //
// //                Tune them according to your setting                 //
// //--------------------------------------------------------------------//
// // k: the cell number of a single time window: 2^k
// // T: the number of time windows
// // a: compression factor
// // duration: the number of seconds for which the periodical register reading lasts
// uint32_t k = 12, T = 4, a = 2, duration = 2;
// //--------------------------------------------------------------------//
// //--------------------------------------------------------------------//
// uint32_t second_highest = 0, highest = 0, index = 0, cell_number = 1 << k ;
// // set second highest bit
// p4_pd_printqueue_prepare_TW0_action_spec_t action_set_second_highest_bit;
// action_set_second_highest_bit.action_second_highest = second_highest << k;
// status_tmp = p4_pd_printqueue_prepare_TW0_tb_set_default_action_prepare_TW0(sess_hdl,dev_tgt,&action_set_second_highest_bit, &handlers[0]);
// if(status_tmp!=0) {
//   printf("Error setting the second highest bit!\n");
//   return false;
// }
// second_highest = 1;
// printf("Successfully set the second highest bit\n");
// uint64_t retrieve_interval = ((1 << (a * T)) - 1) * (1 << (k + 6)) / ((1<<a)-1) / 1000 - 10; // us, give a little time ahead to trigger reading
// printf("Time window retrieve interval: %ld us\n", retrieve_interval);

// // initialize buffer used to store register values
// uint8_t buffer[245760];
// char data_dir[100];
// uint32_t delta_time;
// memset(buffer, 0, 245760);
// memset(data_dir, 0, 100);
// while(running_flag){
//     gettimeofday(&initial_us, NULL);
//     gettimeofday(&e_us, NULL);
//     while(loop_flag){
//       gettimeofday(&s_us, NULL);
//       delta_time = (s_us.tv_sec - e_us.tv_sec) * 1000000 + s_us.tv_usec - e_us.tv_usec;
//       if(delta_time >= retrieve_interval){
//         action_set_second_highest_bit.action_second_highest = second_highest << k;
//         status_tmp = p4_pd_printqueue_prepare_TW0_tb_set_default_action_prepare_TW0(sess_hdl,dev_tgt,&action_set_second_highest_bit, &handlers[0]);
//         gettimeofday(&e_us, NULL);
//         if(status_tmp!=0) {
//           printf("Error setting second highest bit!\n");
//           return false;
//         }
//         second_highest ^= 1;
//         // read just recorded TW
//         index = second_highest << k;
//         p4_pd_time_windows_register_range_read(sess_hdl, dev_tgt, index, cell_number, 1, &actual_read, buffer, &value_count, 1, T);
//         // store the register values
//         sprintf(data_dir, "./tw_data/%ld_%ld.bin",e_us.tv_sec,e_us.tv_usec);  // e_us is the time after the operatin of bit flip, also the start of the reading
//         FILE * f = fopen(data_dir, "wb");
//         fwrite(buffer, 1, cell_number * 12 * T, f);
//         fclose(f);
//         memset(buffer, 0, 245760);
//         memset(data_dir, 0, 100);
//       }
//       gettimeofday(&s_us, NULL);
//       if (s_us.tv_sec - initial_us.tv_sec > duration){
//           printf("Retrieve Ends!\n");
//           loop_flag = false;
//         }
//     }
// }

/*--------------------------------------------------------------------*/
/*                                                                    */
/*                    Queue            Monitor                        */
/*                                                                    */
/*--------------------------------------------------------------------*/
// printf("-----------------------------------------------------\nQueue Monitor is Activating\n-----------------------------------------------------\n");
// // -------------------------------------------------------------------//
// //           The following is the configurable parameters             //
// //                Tune them according to your setting                 //
// //--------------------------------------------------------------------//
// // k: the depth of the stack (data structure) is 2^k
// // max_qdepth: the maximum qdepth number, must be smaller than 2^k
// // read_interval: the number of microseconds which is the reading interval
// // duration: the number of seconds for which the periodical register reading lasts
// uint32_t k = 15, max_qdepth = 25000, read_interval = 100000, duration = 2;
// //--------------------------------------------------------------------//
// //--------------------------------------------------------------------//
// uint32_t second_highest = 0, highest = 0, time_pass, index;
// printf("Queue monitor retrieve interval: %ld us\n", read_interval);
// // set second highest bit
// p4_pd_printqueue_check_stack_action_spec_t action_set_second_highest_bit;
// action_set_second_highest_bit.action_second_highest = second_highest << k;
// status_tmp = p4_pd_printqueue_check_stack_tb_set_default_action_check_stack(sess_hdl,dev_tgt,&action_set_second_highest_bit, &handlers[0]);
// if(status_tmp!=0) {
//   printf("Error setting the second highest bit!\n");
//   return false;
// }
// second_highest = 1;
// printf("Successfully set the second highest bit\n");

// //initialize buffers used to store register values
// uint8_t buffer[300000];
// char data_path[100];
// memset(buffer, 0, 300000);
// memset(data_path, 0, 100);
// while(running_flag){
//   gettimeofday(&initial_us, NULL);
//   gettimeofday(&e_us, NULL);
//   while(loop_flag){
//       gettimeofday(&s_us, NULL);
//       time_pass = (s_us.tv_sec - e_us.tv_sec) * 1000000 + s_us.tv_usec - e_us.tv_usec;
//       if (time_pass >= read_interval){
//         action_set_second_highest_bit.action_second_highest = second_highest << k;
//         status_tmp = p4_pd_printqueue_check_stack_tb_set_default_action_check_stack(sess_hdl,dev_tgt,&action_set_second_highest_bit, &handlers[0]);
//         gettimeofday(&e_us, NULL);
//         if(status_tmp!=0) {
//           printf("Error setting second highest bit!\n");
//           return false;
//         }
//         second_highest ^= 1;
//         // read and reset just recorded QM
//         index = second_highest << k;
//         p4_pd_queue_monitor_register_range_read(sess_hdl, dev_tgt, index, max_qdepth, 1, &actual_read, buffer, &value_count, 1);
//         p4_pd_printqueue_register_range_reset_src_ip_r(sess_hdl, dev_tgt, index, max_qdepth);  // reset registers after read: only store delta data
//         // store the register values
//         sprintf(data_path, "./qm_data/%ld_%ld.bin",e_us.tv_sec,e_us.tv_usec); // e_us is the time after the operatin of bit flip, also the start of the reading
//         FILE * f = fopen(data_path, "wb");
//         fwrite(buffer, 1, 300000, f);
//         fclose(f);
//         memset(buffer, 0, 300000);
//         memset(data_path, 0, 100);
//       }
//       gettimeofday(&s_us, NULL);
//       if (s_us.tv_sec - initial_us.tv_sec > duration){
//         printf("Retrieve Ends!\n");
//         loop_flag = false;
//       }
//   }
// }


//----------------------------------------------------//
//          End of PrintQueue Control Plane           //
//----------------------------------------------------//
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

  if (switchd_main_ctx) free(switchd_main_ctx);
  if (handlers) free(handlers);
  return ret;
}
