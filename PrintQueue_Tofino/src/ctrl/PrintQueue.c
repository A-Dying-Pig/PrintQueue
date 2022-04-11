
/*************************************************************************
	> File Name: PrintQueue.c
	> Author: Yiran Lei
	> Mail: yiranlei.yiranlei@gmail.com
	> Created Time: Tue 18 Jan 2022
    > Description: Data plane (Tofino) control interfaces for PrintQueue
 ************************************************************************/


/* Standard includes */
#include <stdio.h>
#include <string.h>
#include <getopt.h>
#include <signal.h>
#include <sys/time.h>
#include <unistd.h>


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

static bool loop_flag = false;
static void sigusr1_handler(int signum) {
  printf("printqueue: bf_switchd:received signal %d\n", signum);
  if(loop_flag) {
    loop_flag = false;
  }
  else {
    loop_flag = true;
  }
}

static bool running_flag = true;
static void sigusr2_handler(int signum) {
  printf("printqueue: bf_switchd:received signal %d\n", signum);
  if(running_flag) {
    running_flag = false;
  }
  else {
    running_flag = true;
  }
}

p4_pd_status_t
p4_pd_printqueue_register_range_read
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
    int handle_id[] = {100663297, 100663298, 100663299, 
                       100663302, 100663303, 100663304, 
                       100663307, 100663308, 100663309, 
                       100663312, 100663313, 100663314};
                      //  100663317, 100663318, 100663319};
    uint total = 0;
    for (int rn = 0; rn < T * 3; rn ++){
        /* Perform the query. */
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


//----------------------------------------------------
//  PrintQueue Control Plane
//---------------------------------------------------
  printf("-----------------------------------------------------\nPrintQueue Control Plane is Activating\n-----------------------------------------------------\n");
  printf("pid: %ld\n", getpid());

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
struct timeval s_us, e_us, initial_us, last_us;

//--------------------------------------------------------------------
//
//                  Time          Window
//
//------------------------------------------------------------------- 
// set half bit
// uint16_t half = 0, k = 12;
// p4_pd_printqueue_prepare_TW0_action_spec_t action_set_half;
// action_set_half.action_half = half << k;
// status_tmp = p4_pd_printqueue_prepare_TW0_tb_set_default_action_prepare_TW0(sess_hdl,dev_tgt,&action_set_half, &handlers[0]);
// if(status_tmp!=0) {
//   printf("Error setting half bit!\n");
//   return false;
// }
// half = 1;
// printf("Successfully set first half bit!\n");
// uint index, cell_number = 1 << k, T = 4, a = 2;
// uint64_t retrieve_interval = ((1 << (a * T)) - 1) * (1 << (k + 6)) / ((1<<a)-1) / 1000 - 12000; // us 6000
// printf("Retrieve interval: %ld\n", retrieve_interval);

// // reading register of TW
// uint8_t buffer[245760];
// char data_dir[100];
// long duration = 2; // 2s
// uint32_t delta_time;
// while(running_flag){
//     gettimeofday(&initial_us, NULL);
//     while(loop_flag){
//       gettimeofday(&s_us, NULL);
//       delta_time = (s_us.tv_sec - e_us.tv_sec) * 1000000 + s_us.tv_usec - e_us.tv_usec;
//       if(delta_time >= retrieve_interval){
//         memset(buffer, 0, 245760);
//         memset(data_dir, 0, 100);
//         index = half << k;
//         p4_pd_printqueue_register_range_read(sess_hdl, dev_tgt, index, cell_number, 1, &actual_read, buffer, &value_count, 1, T);
//         action_set_half.action_half = half << k;
//         status_tmp = p4_pd_printqueue_prepare_TW0_tb_set_default_action_prepare_TW0(sess_hdl,dev_tgt,&action_set_half, &handlers[0]);
//         if(status_tmp!=0) {
//           printf("Error setting half bit!\n");
//           return false;
//         }
//         half ^= 1;
//         sprintf(data_dir, "./tw_data/%ld_%ld.bin",s_us.tv_sec,s_us.tv_usec);
//         FILE * f = fopen(data_dir, "wb");
//         fwrite(buffer, 1, cell_number * 12 * T, f);
//         fclose(f);
//         gettimeofday(&e_us, NULL);
//         if (e_us.tv_sec - initial_us.tv_sec > duration){
//           printf("Retrieve Ends!\n", retrieve_interval);
//           loop_flag = false;
//         }
//       }
//     }
// }


//--------------------------------------------------------------------
//
//                  Queue            Monitor
//
//------------------------------------------------------------------- 
// reading register of QM
uint32_t reading_qdepth_interval = 1000, threshold = 8000, re_read = 500000, duration = 4, time_pass; 
uint32_t qdepth[2], enqueue_ts[2];
uint8_t src_ip[200000];
uint8_t dst_ip[200000];
char data_path[100];
gettimeofday(&s_us, NULL);
gettimeofday(&last_us, NULL);
while(running_flag){
  gettimeofday(&initial_us, NULL);
  while(loop_flag){
      gettimeofday(&e_us, NULL);
      time_pass = (e_us.tv_sec - s_us.tv_sec) * 1000000 + e_us.tv_usec - s_us.tv_usec;
      if (time_pass > reading_qdepth_interval){
        p4_pd_printqueue_register_read_qdepth_r(sess_hdl, dev_tgt, 0, 1, qdepth ,&value_count);
        // printf("queue length: %d, %d, value_read: %d\n", qdepth[0], qdepth[1], value_count);
        time_pass = (e_us.tv_sec - last_us.tv_sec) * 1000000 + e_us.tv_usec - last_us.tv_usec;
        if (qdepth[1] > threshold && time_pass >= re_read){
          // read and store stack
          p4_pd_printqueue_register_read_QM_enqueue_ts_r(sess_hdl, dev_tgt, 0, 1, enqueue_ts, &value_count);
          // printf("enqueue ts: %d, queue length: %d, reading stack from data plane\n",enqueue_ts[1], qdepth[1]);
          p4_pd_printqueue_register_range_read_QM_src_ip_r(sess_hdl, dev_tgt, 0,  25000, 1, &actual_read, (uint32_t *)src_ip, &value_count);
          p4_pd_printqueue_register_range_read_QM_dst_ip_r(sess_hdl, dev_tgt, 0,  25000, 1, &actual_read, (uint32_t *)dst_ip, &value_count);

          sprintf(data_path, "./qm_data/%ld_%ld.bin",e_us.tv_sec,e_us.tv_usec);
          FILE * f = fopen(data_path, "wb");
          fwrite(&qdepth[1], 1, 4, f);
          fwrite(&enqueue_ts[1], 1, 4, f);
          fwrite(src_ip, 1, 200000, f);
          fwrite(dst_ip, 1, 200000, f);
          fclose(f);
          gettimeofday(&last_us, NULL);
        }
        gettimeofday(&s_us, NULL);
      }
      gettimeofday(&e_us, NULL);
      if (e_us.tv_sec - initial_us.tv_sec > duration){
        printf("Retrieve Ends!\n");
        loop_flag = false;
      }
  }
}


//----------------------------------------------------
// End of PrintQueue Control Plane
//---------------------------------------------------
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
