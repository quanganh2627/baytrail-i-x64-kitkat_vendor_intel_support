#!/bin/bash

#
# File descriptor 3 will output the the original stderr of the
# invoked shell. We do this so that a function can directly exit on failure...
# but still output its failure message.
exec 3>&2
exec 2>&1


function exit_on_error {
    if [ "$1" -ne 0 ]; then
        exit 1
    fi
}



# defaults
TOP=`pwd`
_jobs="`grep -c processor /proc/cpuinfo`"
_kernel_only=0
_test=0
_clean=""
_logfile_prefix=`date "+build.%Y%m%d%H%M"`
_nnn=0
_logfile=""
_preserve_kernel_config=""
_menuconfig="false"
_config_file_type=android

init_variables() {
    local custom_board=$1

    if [ -z "${TARGET_TOOLS_PREFIX}" ]; then
        echo >&3 "Warning: TARGET_TOOLS_PREFIX was not set."
	TARGET_TOOLS_PREFIX=$TOP/prebuilt/linux-x86/toolchain/i686-android-linux-4.4.3/bin/i686-android-linux-
    fi
    if [ -z "${CCACHE_TOOLS_PREFIX}" ]; then
        echo >&3 "Warning: CCACHE_TOOLS_PREFIX was not set."
	CCACHE_TOOLS_DIR=$TOP/prebuilt/linux-x86/ccache
    fi
    export PATH="`dirname ${TARGET_TOOLS_PREFIX}`:$PATH"
    if [ -z "$CROSS_COMPILE" ];then
        export CROSS_COMPILE="`basename ${TARGET_TOOLS_PREFIX}`"
    fi
    if [ ! -z ${USE_CCACHE} ]; then
	export PATH="${CCACHE_TOOLS_DIR}:$PATH"
        export CROSS_COMPILE="ccache $CROSS_COMPILE"
    fi
    export ARCH=i386
    echo >&3 "ARCH: $ARCH"
    echo >&3 "CROSS_COMPILE: $CROSS_COMPILE"
    echo >&3 "PATH: $PATH"

    if [ -z "${custom_board}" ]; then
        echo "No custom board specified"
        exit_on_error 2
    fi

    case "${custom_board}" in
    generic_x86 | vbox )
        VENDOR=""
        BOARD=generic_x86
        ;;
    mrst_ref | ivydale | mrst_edv | crossroads | mfld_cdk | mfld_pr1)
        VENDOR=intel
        BOARD=${custom_board}
        ;;
    *)
        echo "Unknown board specified \"${custom_board}\""
        exit_on_error 2
        ;;
    esac

    PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
    KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
}

make_compat() {
    echo "  Making wl12xx compat wireless"
    local COMPAT_SRC_DIR=$TOP/hardware/intel/PRIVATE/tiwl1283/wl12xx-compat/
    local MODULE_DEST_TMP=${PRODUCT_OUT}/compat_modules
    local MODULE_DEST=${PRODUCT_OUT}/root/lib/modules

    cd ${COMPAT_SRC_DIR}

    make ARCH=${ARCH} KLIB=${MODULE_DEST_TMP} KLIB_BUILD=${KERNEL_BUILD_DIR} 
    exit_on_error $? quiet

    mkdir -p ${MODULE_DEST_TMP};
    make ARCH=${ARCH} INSTALL_MOD_STRIP=--strip-unneeded KLIB=${MODULE_DEST_TMP} KLIB_BUILD=${KERNEL_BUILD_DIR} install-modules
    exit_on_error $? quiet

    find ${MODULE_DEST_TMP} -name *.ko -exec cp -vf {} ${MODULE_DEST} \;
    exit_on_error $? quiet

    cd ${TOP}
}

usage() {
    echo "Usage: $0 [-c custom_board] [-j jobs]"

    echo ""
    echo " -c [generic_x86|vbox|mrst_ref|ivydale|mrst_edv|crossroads|mfld_cdk|mfld_pr1]"
    echo "                          custom board (target platform)"
    echo " -j [jobs]                # of jobs to run simultaneously.  0=automatic"
    echo " -K                       Build a kboot kernel"
    echo " -k                       build kernel only"
    echo " -t                       testtool build"
    echo " -C                       clean first"
}

main() {
    local custom_board_list="vbox mrst_ref ivydale mrst_edv crossroads mfld_cdk mfld_pr1"

    while getopts Kc:j:kthCm opt
    do
        case "${opt}" in
        K)
            _config_file_type=kboot
            ;;
        h)
            usage
            exit 0
            ;;
        c)
            custom_board_list="${OPTARG}"
            ;;
        j)
            if [ ${OPTARG} -gt 0 ]; then
                _jobs=${OPTARG}
            else
                _jobs=`grep processor /proc/cpuinfo|wc -l`
            fi
            ;;
        k)
            _kernel_only=1
            echo >&3 "Kernel will be built but will not be placed in a boot image."
            ;;
        t)
            export TARGET_BUILD_VARIANT=tests
            _test=1
            ;;
        C)
            _clean=1
            ;;
        m)
            _menuconfig=true
            ;;
        ?)
            echo "Unknown option"
            usage
            exit 0
            ;;
        esac
    done

    for custom_board in $custom_board_list
    do
        echo >&3 
        echo >&3 "Building kernel for $custom_board"
        echo >&3 "---------------------------------"
        init_variables "$custom_board"
        make_compat ${custom_board} 
        exit_on_error $?
    done
    exit 0
}

main $*
