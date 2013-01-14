#!/bin/bash

TOP=`pwd`
ARCH=x86
LINUXVER=
BOARD=$1
DRIVER=$2
PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
BCMDHD_4334_SRC_DIR=${TOP}/hardware/broadcom/wlan_driver/bcm4334/src
BCMDHD_4335_SRC_DIR=${TOP}/hardware/broadcom/wlan_driver/bcm4335/src
MODULE_DEST=${PRODUCT_OUT}/root/lib/modules
TARGET=dhd-cdc-sdmmc-android-intel-jellybean-cfg80211-oob


function exit_on_error {
    if [ "$1" -ne 0 ]; then
        exit 1
    fi
}

get_kernelversion() {
    LINUXVER=`make -C ${TOP}/${KERNEL_SRC_DIR} kernelversion | sed -n 2p`
    echo "LINUXVER detected <$LINUXVER>"
}

make_bcmdhd() {
    if [ "$DRIVER" == "" ]; then
        echo "No driver specified. Nothing to do"
        exit 1
    elif [ "$DRIVER" == "bcm4334" ]; then
         cd $BCMDHD_4334_SRC_DIR
    elif [ "$DRIVER" == "bcm4335" ]; then
         cd $BCMDHD_4335_SRC_DIR
    else
         echo "Invalid driver specified <${DRIVER}>. Stop!"
         exit 1
    fi

    echo "Making driver <${DRIVER}> for <${BOARD}>"
    echo "----------------------------------------"

    make ARCH=${ARCH} -C ${KERNEL_BUILD_DIR}/ M=$PWD CONFIG_BCMDHD=m

    exit_on_error $? quiet

    if [ "$DRIVER" == "bcm4334" ]; then
        cp -f ${BCMDHD_4334_SRC_DIR}/bcmdhd.ko ${MODULE_DEST}
    elif [ "$DRIVER" == "bcm4335" ]; then
        cp -f ${BCMDHD_4335_SRC_DIR}/bcmdhd.ko ${MODULE_DEST}
    else
        echo "Should not get there"
    fi

    cd ${TOP}
}

get_kernelversion
make_bcmdhd
exit_on_error $?
exit 0
