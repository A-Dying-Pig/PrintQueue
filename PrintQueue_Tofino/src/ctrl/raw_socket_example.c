#define _GNU_SOURCE

#include <stdio.h>
#include <string.h>
#include <getopt.h>
#include <signal.h>

#include "bf_switchd.h"
#include "switch_config.h"

#define RCV_BUF_SIZE 256
#define CONFIG_BUF_SIZE 100
#define HDL_BUF_SIZE 100
#include <pipe_mgr/pipe_mgr_intf.h>
#include <unistd.h>
#include <sys/time.h> 
#include <net/if.h>
#include <sys/socket.h>
#include <linux/if_packet.h>
#include <linux/if_ether.h>
#include <arpa/inet.h>
#include <sys/ioctl.h>
#include <net/ethernet.h>

#include <pthread.h>
#include <sched.h>
#include <sys/resource.h> 
#include <x86intrin.h>


static void setup_coverage_sighandler() {
  struct sigaction new_action;
  /* setup signal hander */
  new_action.sa_handler = coverage_handler;
  sigemptyset(&new_action.sa_mask);
  new_action.sa_flags = 0;

  sigaction(SIGKILL, &new_action, NULL);
  sigaction(SIGTERM, &new_action, NULL);
  sigaction(SIGQUIT, &new_action, NULL);
  sigaction(SIGINT, &new_action, NULL);
}

static bool sleep_before = true;
static bool loop_flag = false;
static void sigusr1_handler(int signum) {
  printf("bf_switchd:received signal %d\n", signum);
  sleep_before = false;
  if(loop_flag) {
    loop_flag = false;
  }
  else {
    loop_flag = true;
  }
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
  }

  /* Parse bf_switchd arguments */
  bf_switchd_parse_options(switchd_main_ctx, argc, argv);

  /* determine if kernel mode packet driver is loaded */
  switch_pci_sysfs_str_get(bf_sysfs_fname,
                           sizeof(bf_sysfs_fname) - sizeof("/dev_add"));
  strncat(bf_sysfs_fname,
          "/dev_add",
          sizeof(bf_sysfs_fname) - 1 - strlen(bf_sysfs_fname));
  printf("bf_sysfs_fname %s\n", bf_sysfs_fname);
  fd = fopen(bf_sysfs_fname, "r");
  if (fd != NULL) {
    /* override previous parsing if bf_kpkt KLM was loaded */
    printf("kernel mode packet driver present, forcing kernel_pkt option!\n");
    switchd_main_ctx->kernel_pkt = true;
    fclose(fd);
  }

  ret = bf_switchd_lib_init(switchd_main_ctx);

  ////////////////////////////////////////////////////////////////////////////////////
  printf("Send USR1 signal to trigger local control [PID: %ld]\n", (long)getpid());
  while(sleep_before) {
    usleep(100000);
  }

  // pthread_t thread;
  // thread = pthread_self();
  // cpu_set_t cpuset;
  // CPU_ZERO(&cpuset);
  // // 0~7
  // CPU_SET(2, &cpuset);
  // int s = pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
  // if (s != 0)
  //   printf("Failed to set pthread affinity\n");

  // s = pthread_getaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
  // if (s != 0)
  //   printf("Failed to get pthread affinity\n");
  // printf("The mask contains: \n");
  // for(int i = 0; i<CPU_SETSIZE; i++)
  //     if(CPU_ISSET(i, &cpuset))
  //       printf("CPU %d\n", i);

  struct sched_param params;
  // Higher priority threads preempt lower ones
  params.sched_priority = sched_get_priority_max(SCHED_FIFO);
  if (pthread_setschedparam(pthread_self(), SCHED_FIFO, &params) != 0) {
    printf("Failed to set priority");
  }

  // Get session handler and device object
  uint32_t sess_hdl = 0;
  uint32_t status_tmp = 0;
  status_tmp = pipe_mgr_init();
  if(status_tmp!=0) {
    printf("ERROR: Status code: %u", status_tmp);
    exit(1);
  }
  status_tmp = pipe_mgr_client_init(&sess_hdl);
  if(status_tmp!=0) {
    printf("ERROR: Status code: %u", status_tmp);
    exit(1);
  }
  dev_target_t pipe_mgr_dev_tgt;
  pipe_mgr_dev_tgt.device_id = 0;
  pipe_mgr_dev_tgt.dev_pipe_id = 0xffff;

  uint32_t* handlers = (uint32_t*)malloc(sizeof(uint32_t) * HDL_BUF_SIZE);
  memset(handlers, 0, sizeof(uint32_t) * HDL_BUF_SIZE);  
  ////////////////////////////////////////////
  printf("====== Initialization ======\n");

  struct timeval start, end, interval; 
  gettimeofday(&start, NULL);
  // if(!pd_initialize(sess_hdl, pipe_mgr_dev_tgt)) {
  //   printf("Failed initialization.\n");
  // }
  if(!pd_initialize(sess_hdl, pipe_mgr_dev_tgt, handlers)) {
    printf("Failed initialization.\n");
  }
  gettimeofday(&end, NULL);
  timersub(&end, &start, &interval);
  printf("Execution time spent for initialize: %ld.%06ld\n", (long int)interval.tv_sec, (long int)interval.tv_usec);

  // printf("Number of entries to initialize: %d\n", num);
  // if(!pi_execute(configs, num, sess_hdl, pipe_mgr_dev_tgt)) {
  //   printf("Failed execution!");
  // }

  ///////////////////////////////////////////
  printf("Configure raw socket...\n");
  // Raw sockets
  int sockfd_rcv;
  // Send only
  // if ((sockfd_rcv = socket(AF_PACKET, SOCK_RAW, IPPROTO_RAW)) == -1) {
  // ETH_P_IP(0x8000), ETH_P_ARP(0x0806), ETH_P_8021Q(0x8100)
  if ((sockfd_rcv = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL))) == -1) {
    perror("Fail to open the raw socket.");
  }
  struct ifreq ifr;
  memset(&ifr, 0, sizeof(struct ifreq));
  strncpy(ifr.ifr_name, "bf_pci0", IFNAMSIZ-1);
  if (ioctl(sockfd_rcv, SIOCGIFINDEX, &ifr) < 0) {
    perror("SIOCGIFINDEX failed.");
    exit(1);
  }

  // Promisc, so that even if Ethernet interface filters frames (MAC addr unmatch, broadcast...)
  struct packet_mreq mreq = {0};
  mreq.mr_ifindex = ifr.ifr_ifindex;
  mreq.mr_type = PACKET_MR_PROMISC;
  if (setsockopt(sockfd_rcv, SOL_PACKET, PACKET_ADD_MEMBERSHIP, &mreq, sizeof(mreq)) == -1) {
      perror("setsockopt");
      exit(1);
  }

  struct sockaddr_ll addr = {0};
  addr.sll_family = AF_PACKET;
  addr.sll_ifindex = ifr.ifr_ifindex;
  // Match previous
  addr.sll_protocol = htons(ETH_P_ALL);
  if (bind(sockfd_rcv, (struct sockaddr*)&addr, sizeof(addr)) == -1) {
    perror("Bind failed");
    exit(1);
  }
  char rcv_buf[RCV_BUF_SIZE];
  // struct sockaddr src_addr;
  // socklen_t src_len = sizeof(src_addr);
  //////////////////////////////////////////
  printf("======================\n");
  printf("Start runtime looping....\n");
  // int pkt_index = 0;
  // struct rusage r_usage_begin, r_usage_end; 
  // unsigned long long rdtsc_begin, rdtsc_end; 
  FILE *fp;
  fp = fopen("./measurement", "w+");
  while(loop_flag) {
    // int ret = recvfrom(sockfd_rcv, &rcv_buf, RCV_BUF_SIZE-1, 0, &src_addr, (socklen_t *)&src_len);
    int n = recvfrom(sockfd_rcv, &rcv_buf, RCV_BUF_SIZE-1, 0, NULL, NULL);
    if(n < 0) {
      printf("Failed to receive\n");
      continue;
    }
    // getrusage(RUSAGE_SELF,&r_usage_begin);
    gettimeofday(&start, NULL);
    // rdtsc_begin = __rdtsc();
    // Ethernet II header 14 bytes
    // if(!pd_dialogue(sess_hdl, pipe_mgr_dev_tgt, rcv_buf)) {
    //   printf("Failed dialogue.\n");
    // }
    if(!pd_dialogue(sess_hdl, pipe_mgr_dev_tgt, rcv_buf, handlers)) {
      printf("Failed dialogue.\n");
    }
    // rdtsc_end = __rdtsc();
    gettimeofday(&end, NULL);
    // getrusage(RUSAGE_SELF,&r_usage_end);
    timersub(&end, &start, &interval);
    fprintf(fp, "%ld.%06ld\n", (long int)interval.tv_sec, (long int)interval.tv_usec);
    printf("=>Dialogue time: %ld.%06ld\n", (long int)interval.tv_sec, (long int)interval.tv_usec);
    // printf("=>[%d]: %ld.%06ld\n", pkt_index, (long int)interval.tv_sec, (long int)interval.tv_usec);
    // pkt_index ++;
  }
  fclose(fp);
  printf("End control program...\n");
  ////////////////////////////////////////////////////////////////////////////////////
  printf("Joining the child threads before exit...\n");
  pthread_join(switchd_main_ctx->tmr_t_id, NULL);
  pthread_join(switchd_main_ctx->dma_t_id, NULL);
  pthread_join(switchd_main_ctx->int_t_id, NULL);
  pthread_join(switchd_main_ctx->pkt_t_id, NULL);
  pthread_join(switchd_main_ctx->port_fsm_t_id, NULL);
  pthread_join(switchd_main_ctx->drusim_t_id, NULL);
  pthread_join(switchd_main_ctx->accton_diag_t_id, NULL);
  for (agent_idx = 0; agent_idx < BF_SWITCHD_MAX_AGENTS; agent_idx++) {
    if (switchd_main_ctx->agent_t_id[agent_idx] != 0) {
      pthread_join(switchd_main_ctx->agent_t_id[agent_idx], NULL);
    }
  }

  if (switchd_main_ctx) free(switchd_main_ctx);
  if (handlers) free(handlers);

  return ret;
}
