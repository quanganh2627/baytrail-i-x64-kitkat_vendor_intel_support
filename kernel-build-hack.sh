#!/bin/bash

#
# File descriptor 3 will output the the original stderr of the
# invoked shell. We do this so that a function can directly exit on failure...
# but still output its failure message.
exec 3>&2


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

init_variables() {
    local custom_board=$1

    TOOLCHAIN=$TOP/prebuilt/linux-x86/toolchain/i686-unknown-linux-gnu-4.2.1/bin
    export PATH=$TOOLCHAIN:$PATH
    if [ -z "$CROSS_COMPILE" ];then
        export CROSS_COMPILE=i686-unknown-linux-gnu-
    fi
    export ARCH=x86

    if [ -z "${custom_board}" ]; then
        echo "No custom board specified"
        exit_on_error 2
    fi

    case "${custom_board}" in
    generic_x86 | vbox )
        VENDOR=""
        BOARD=generic_x86
        PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
        ;;
    mrst_ref | ivydale | mrst_edv)
        VENDOR=intel
        BOARD=${custom_board}
        PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
        ;;
    *)
        echo "Unknown board specified \"${custom_board}\""
        exit_on_error 2
        ;;
    esac
}

make_kernel() {
    local custom_board=${1}
    local _config_file=""

    cd ${TOP}/hardware/intel/linux
    _config_file=i386_${custom_board}_android_defconfig

    if [ -z "$_preserve_kernel_config" ]; then
        rm -f .config
    fi
    if [ "$_clean" ]; then
        make mrproper
    fi
    if [ ! -e .config ]; then
        echo "Fetching a kernel .config file for ${_config_file}"

        make ${_config_file}
        exit_on_error $? quiet
    fi

    # Check .config to see if we get what we expect
    awk 'NR>4' arch/x86/configs/$_config_file | grep -v '^#' > /tmp/build.$$.1.tmp
    awk 'NR>4' .config | grep -v '^#' > /tmp/build.$$.2.tmp
    diff /tmp/build.$$.1.tmp /tmp/build.$$.2.tmp > /dev/null
    if [ $? -ne 0 ]; then
        echo >&3
        echo >&3 "WARNING: The .config file does not match the"
        echo -n >&3 "   reference config file $_config_file..."
    fi

    if [ arch/x86/configs/${_config_file} -nt .config ]; then
        echo >&3
        echo -n >&3 "WARNING: ${_config_file} is newer than .config..."
    fi

    make -j${_jobs} bzImage
    exit_on_error $? quiet

    mkdir -p ${PRODUCT_OUT}
    cp arch/x86/boot/bzImage ${PRODUCT_OUT}/.
    exit_on_error $? quiet

    case "${custom_board}" in
    mrst_ref | ivydale | mrst_edv)
        make_modules ${custom_board}
        exit_on_error $? quiet
        ;;
    generic_x86 | vbox)
        ;;
    esac


    cd ${TOP}
}

make_modules() {
    local custom_board=${1}
    local MODULE_SRC=${PRODUCT_OUT}/kernel_modules
    local MODULE_DEST=${PRODUCT_OUT}/system/lib/modules

    echo "  Making driver modules..."

    rm -fr ${MODULE_SRC}
    rm -fr ${MODULE_DEST}

    if [ ! -d ${MODULE_SRC} ]; then
        mkdir -p ${MODULE_SRC}
    fi
    if [ ! -d ${MODULE_DEST} ]; then
        mkdir -p ${MODULE_DEST}
    fi

    make -j${_jobs} modules
    exit_on_error $? quiet

    make -j${_jobs} modules_install \
        INSTALL_MOD_STRIP=--strip-unneeded INSTALL_MOD_PATH=${MODULE_SRC}
    exit_on_error $? quiet

    find ${MODULE_SRC} -name *.ko -exec cp -vf {} ${MODULE_DEST} \;
    exit_on_error $? quiet
}


usage() {
    echo "Usage: $0 [-c custom_board] [-j jobs]"

    echo ""
    echo " -c [generic_x86|vbox|mrst_ref|ivydale|mrst_edv]"
    echo "                          custom board (target platform)"
    echo " -j [jobs]                # of jobs to run simultaneously.  0=automatic"
    echo " -K                       preserve kernel .config file"
    echo " -k                       build kernel only"
    echo " -t                       testtool build"
    echo " -C                       clean first"
}

main() {
    local custom_board=

    while getopts Kc:j:kthC opt
    do
        case "${opt}" in
        h)
            usage
            exit 0
            ;;
        c)
            custom_board=${OPTARG}
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
        ?)
            echo "Unknown option"
            usage
            exit 0
            ;;
        esac
    done

    init_variables "$custom_board"

    make_kernel ${custom_board} 
    exit_on_error $?

        exit 0

}

main $*
