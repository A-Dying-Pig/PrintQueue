BUILD=$(SDE)/pkgsrc/p4-build/
CWD=$(shell pwd)

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
	bash run.sh

kill:
	killall -w -q bf_switchd

attach:
	tmux attach -t switchd

daemon:
	tmux new  -d -s switchd '${SDE}/run_switchd.sh -p printqueue -c config/printqueue.conf'

# compile PrintQueue control plane program
printqueue: src/ctrl/PrintQueue.c
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

# clean queue monitor register data
clean_qm:
	rm -rf qm_data
	mkdir qm_data