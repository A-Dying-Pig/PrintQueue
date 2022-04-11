BUILD=$(SDE)/pkgsrc/p4-build/
CWD=$(shell pwd)

compile: clean
	cd $(BUILD); make -j6; make -j6 install

distclean:
	cd $(SDE)/pkgsrc/p4-build; make clean; cd $(BUILD); make clean

clean:
	cd $(BUILD); make clean

run: 
	$(SDE)/run_switchd.sh -p printqueue -c config/printqueue.config

kill:
	killall -w -q bf_switchd

attach:
	tmux attach -t switchd

daemon:
	tmux new  -d -s switchd '${SDE}/run_switchd.sh -p printqueue -c config/printqueue.conf'

configure:
	cd $(BUILD); $(SDE)/pkgsrc/p4-build/configure --prefix=$(SDE_INSTALL) --with-tofino enable_thrift=yes P4_NAME=printqueue P4_PATH=$(CWD)/src/data/main.p4

populate:
	$(SDE)/run_p4_tests.sh -p printqueue -t $(CWD)/src/control/ipv4_routing 

read:
	$(SDE)/run_p4_tests.sh -p printqueue -t $(CWD)/src/control/read_flip

printqueue: src/ctrl/PrintQueue.c
	gcc -I $$SDE/pkgsrc/p4-build/tofinopd/printqueue/ -I$$SDE_INSTALL/include -I$$SDE/pkgsrc/bf-drivers/include  -I$$SDE/pkgsrc/bf-drivers/bf_switchd -g -O2 -std=gnu99 \
		-L/usr/local/lib -L$$SDE_INSTALL/lib -L$$SDE/pkgsrc/bf-drivers/src -L$$SDE/pkgsrc/bf-drivers/bf_switchd\
	    src/ctrl/PrintQueue.c $$SDE/pkgsrc/p4-build/tofinopd/printqueue/src/pd.c -o PrintQueue \
	    -ldriver -lbfsys -lbfutils -lbf_switchd_lib \
		-lm -ldl -lpthread \
		-ltofinopdfixed_thrift -lthrift

runPQ:
	bash run.sh

clean_tw:
	rm -rf tw_data
	mkdir tw_data

clean_qm:
	rm -rf qm_data
	mkdir qm_data