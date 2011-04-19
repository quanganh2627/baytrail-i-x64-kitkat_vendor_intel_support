#!/bin/bash
# build nand boot for android

if [ $# -ne 2 ]; then
    echo "Usage: $0 target-name bootstub out"
    echo "target-name = ivydale"
    echo "out = filename of output file"
    exit 1
fi

BZIMAGE=out/target/product/$1/boot/kernel
INITRD=out/target/product/$1/boot/ramdisk.img
CMDLINE=out/target/product/$1/boot/cmdline
BOOTSTUB=vendor/intel/support/bootstub
TEMP=out/target/product/$1/tmp
TARG=out/target/product/$1
OUT=$2

if [ "$1" == "mfld_cdk" ] || [ "$1" == "mfld_pr1" ] ;then
            SILICON=1;
    else
            SILICON=0;
    fi

if [ ! -e ${BZIMAGE} ]; then
    echo "error: bzImage file ${BZIMAGE} does not exist"
    exit 1
fi

if [ ! -e ${INTIRD} ]; then
    echo "error: ramdisk.img file ${INTRD} does not exist"
    exit 1
fi

if [ ! -e ${CMDLINE} ]; then
    echo "error: cmdline file ${CMDLINE} does not exist"
    exit 1
fi

if [ ! -e ${BOOTSTUB} ]; then
    echo "error: bootstub file ${BOOTSTUB} does not exist"
    exit 1
fi

if [ -e "${OUT}" ]; then
    echo "${OUT} exists, remove the old one"
    rm -f ${OUT}
fi

if [ ! -e "${TEMP}" ]; then
    mkdir ${TEMP}
fi

echo "Creating image \`${OUT}'for FSTK stitching..."

rm -f ${TEMP}/boot.unsigned
./vendor/intel/support/stitch.sh ${CMDLINE} ${BOOTSTUB} ${BZIMAGE} ${INITRD} 0 ${SILICON} ${TEMP}/boot.unsigned
cp -f ${TEMP}/boot.unsigned ${TARG}

if [ "0" -ne "$?" ]; then
    echo "error running nand.sh"
    exit 1
fi
TOP=`pwd`
# stitch kboot
cd device/intel/PRIVATE/lfstk
./gen-os.sh ${TOP}/${TEMP}/boot.unsigned ${TOP}/${OUT} PAYLOADOS.XML
cd  $TOP

# clean up
echo "Done."
