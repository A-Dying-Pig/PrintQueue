CWD=$(shell pwd)
BUILD= $(CWD)/build


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
	$(SDE)/run_p4_tests.sh -p printqueue -t $(CWD)/src/control/