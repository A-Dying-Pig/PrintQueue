TARGET_CONFIG_FILE="config/printqueue.config"
export PATH=$SDE_INSTALL/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/lib:$SDE_INSTALL/lib:$LD_LIBRARY_PATH
./PrintQueue\
	--install-dir $SDE_INSTALL --conf-file $TARGET_CONFIG_FILE --status-port 7777