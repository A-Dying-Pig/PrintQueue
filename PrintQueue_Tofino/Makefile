BUILD=$(SDE)/pkgsrc/p4-build/
CWD=$(shell pwd)
kernel=false

# compile PrintQueue data plane program
compile: clean
	cd $(BUILD); make -j6; make -j6 install

#configure project before compile
configure:
	cd $(BUILD); $(SDE)/pkgsrc/p4-build/configure --prefix=$(SDE_INSTALL) --with-tofino enable_thrift=yes P4_NAME=printqueue P4_PATH=$(CWD)/src/data/main.p4

distclean:
	cd $(SDE)/pkgsrc/p4-build; make clean; cd $(BUILD); make clean

clean:
	cd $(BUILD); make clean

# run the default control plane program
run: 
	$(SDE)/run_switchd.sh -p printqueue -c config/printqueue.config

# run PrintQueue control plane program
runPQ:
	@if $(kernel); then\
        echo "Enabling kernel mode. Please load bf_kpkt module.";\
		bash run.sh --kernel-pkt;\
	else \
		echo "Enabling non-kernel mode. Please load bf_kdrv module.";\
		bash run.sh;\
    fi

kill:
	killall -w -q bf_switchd

attach:
	tmux attach -t switchd

daemon:
	tmux new  -d -s switchd '${SDE}/run_switchd.sh -p printqueue -c config/printqueue.conf'

# compile PrintQueue control plane program
printqueue:
	gcc -I $$SDE/pkgsrc/p4-build/tofinopd/printqueue/ -I$$SDE_INSTALL/include -I$$SDE/pkgsrc/bf-drivers/include  -I$$SDE/pkgsrc/bf-drivers/bf_switchd -g -O2 -std=gnu99 \
		-L/usr/local/lib -L$$SDE_INSTALL/lib -L$$SDE/pkgsrc/bf-drivers/src -L$$SDE/pkgsrc/bf-drivers/bf_switchd\
	    src/ctrl/PrintQueue.c $$SDE/pkgsrc/p4-build/tofinopd/printqueue/src/pd.c -o PrintQueue \
	    -ldriver -lbfsys -lbfutils -lbf_switchd_lib \
		-lm -ldl -lpthread \
		-ltofinopdfixed_thrift -lthrift

# clean time window register data
clean_tw:
	rm -rf tw_data
	mkdir tw_data
	mkdir -p tw_data/0/tw_data
	mkdir -p tw_data/0/signal_data
	mkdir -p tw_data/1/tw_data
	mkdir -p tw_data/1/signal_data
	mkdir -p tw_data/2/tw_data
	mkdir -p tw_data/2/signal_data
	mkdir -p tw_data/3/tw_data
	mkdir -p tw_data/3/signal_data
	mkdir -p tw_data/4/tw_data
	mkdir -p tw_data/4/signal_data
	mkdir -p tw_data/5/tw_data
	mkdir -p tw_data/5/signal_data
	mkdir -p tw_data/6/tw_data
	mkdir -p tw_data/6/signal_data
	mkdir -p tw_data/7/tw_data
	mkdir -p tw_data/7/signal_data
	mkdir -p tw_data/8/tw_data
	mkdir -p tw_data/8/signal_data
	mkdir -p tw_data/9/tw_data
	mkdir -p tw_data/9/signal_data
	mkdir -p tw_data/10/tw_data
	mkdir -p tw_data/10/signal_data
	mkdir -p tw_data/11/tw_data
	mkdir -p tw_data/11/signal_data
	mkdir -p tw_data/12/tw_data
	mkdir -p tw_data/12/signal_data
	mkdir -p tw_data/13/tw_data
	mkdir -p tw_data/13/signal_data
	mkdir -p tw_data/14/tw_data
	mkdir -p tw_data/14/signal_data
	mkdir -p tw_data/15/tw_data
	mkdir -p tw_data/15/signal_data

# clean queue monitor register data
clean_qm:
	rm -rf qm_data
	mkdir qm_data
	mkdir -p qm_data/0/qm_data
	mkdir -p qm_data/0/signal_data
	mkdir -p qm_data/1/qm_data
	mkdir -p qm_data/1/signal_data
	mkdir -p qm_data/2/qm_data
	mkdir -p qm_data/2/signal_data
	mkdir -p qm_data/3/qm_data
	mkdir -p qm_data/3/signal_data

# load bf_kdrv.ko
kdrv:
	insmod $(SDE_INSTALL)/lib/modules/bf_kdrv.ko intr_mode="msi"

# load bf_kpkt
kpkt:
	insmod $(SDE_INSTALL)/lib/modules/bf_kpkt.ko intr_mode="msi" kpkt_mode=1