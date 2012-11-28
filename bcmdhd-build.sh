#!/bin/bash

TOP=`pwd`
ARCH=x86
LINUXVER=
BOARD=$1
DRIVER=$2
LINUXDIR=${TOP}/hardware/intel/linux-2.6
PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
BCMDHD_4334_SRC_DIR=${TOP}/hardware/broadcom/wlan_driver/bcm4334/open-src/src/dhd/linux
BCMDHD_4335_SRC_DIR=${TOP}/hardware/broadcom/wlan_driver/bcm4335/open-src/src/dhd/linux
MODULE_DEST=${PRODUCT_OUT}/root/lib/modules
TARGET=dhd-cdc-sdmmc-android-intel-jellybean-cfg80211-oob


function exit_on_error {
    if [ "$1" -ne 0 ]; then
        exit 1
    fi
}

get_kernelversion() {
    LINUXVER=`make -C ${LINUXDIR} kernelversion | sed -n 2p`
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

    make ARCH=${ARCH} K_BUILD=${KERNEL_BUILD_DIR} LINUXDIR=${LINUXDIR}/ LINUXVER=${LINUXVER} O=${KERNEL_BUILD_DIR}/ ${TARGET}
    exit_on_error $? quiet

    if [ "$DRIVER" == "bcm4334" ]; then
        cp -f ${BCMDHD_4334_SRC_DIR}/${TARGET}-${LINUXVER}/bcmdhd.ko ${MODULE_DEST}
    elif [ "$DRIVER" == "bcm4335" ]; then
        cp -f ${BCMDHD_4335_SRC_DIR}/${TARGET}-${LINUXVER}/bcmdhd.ko ${MODULE_DEST}
    else
        echo "Should not get there"
    fi

    cd ${TOP}
}

get_kernelversion
make_bcmdhd
exit_on_error $?
exit 0