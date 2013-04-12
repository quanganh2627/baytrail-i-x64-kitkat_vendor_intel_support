#!/bin/bash

TOP=`pwd`
ARCH=x86
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

make_bcmdhd() {
    if [ "$DRIVER" == "" ]; then
        echo "No driver specified. Nothing to do"
        exit 1
    elif [ "$DRIVER" == "bcm43241" ]; then
         cd $BCMDHD_4334_SRC_DIR
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

    make ARCH=${ARCH} -C ${KERNEL_BUILD_DIR}/ M=$PWD CONFIG_BCMDHD=m CONFIG_${DRIVER^^}=y

    exit_on_error $? quiet

    if [ "$DRIVER" == "bcm43241" ]; then
        cp -f ${BCMDHD_4334_SRC_DIR}/bcmdhd.ko ${MODULE_DEST}/${DRIVER}.ko
    elif [ "$DRIVER" == "bcm4334" ]; then
        cp -f ${BCMDHD_4334_SRC_DIR}/bcmdhd.ko ${MODULE_DEST}/${DRIVER}.ko
    elif [ "$DRIVER" == "bcm4335" ]; then
        cp -f ${BCMDHD_4335_SRC_DIR}/bcmdhd.ko ${MODULE_DEST}/${DRIVER}.ko
    else
        echo "Should not get there"
    fi

    cd ${TOP}
}

make_bcmdhd
exit_on_error $?
exit 0
