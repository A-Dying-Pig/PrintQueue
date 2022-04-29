TARGET_CONFIG_FILE="config/printqueue.config"
export PATH=$SDE_INSTALL/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/lib:$SDE_INSTALL/lib:$LD_LIBRARY_PATH


function add_hugepage() {
    sudo sh -c 'echo "#Enable huge pages support for DMA purposes" >> /etc/sysctl.conf'
    sudo sh -c 'echo "vm.nr_hugepages = 128" >> /etc/sysctl.conf'
}

function dma_setup() {
    echo "Setting up DMA Memory Pool"
    hp=$(sudo sysctl -n vm.nr_hugepages)

    if [ $hp -lt 128 ]; then
        if [ $hp -eq 0 ]; then
            add_hugepage
        else
            nl=$(egrep -c vm.nr_hugepages /etc/sysctl.conf)
            if [ $nl -eq 0 ]; then
                add_hugepage
            else
                sudo sed -i 's/vm.nr_hugepages.*/vm.nr_hugepages = 128/' /etc/sysctl.conf
            fi
        fi
        sudo sysctl -p /etc/sysctl.conf
    fi

    if [ ! -d /mnt/huge ]; then
        sudo mkdir /mnt/huge
    fi
    sudo mount -t hugetlbfs nodev /mnt/huge
}

dma_setup

KERNEL_PKT_STR=""
if [ "$1" == "--kernel-pkt" ]; then
    KERNEL_PKT_STR="--kernel-pkt"
fi

# gdb -ex run --args 
./PrintQueue\
	--install-dir $SDE_INSTALL --conf-file $TARGET_CONFIG_FILE --status-port 7777 $KERNEL_PKT_STR