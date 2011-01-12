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
        TARGET_TOOLS_PREFIX=${TOP}/prebuilt/linux-x86/toolchain/i686-unknown-linux-gnu-4.2.1/bin/i686-unknown-linux-gnu-
    fi
    export PATH="`dirname ${TARGET_TOOLS_PREFIX}`:$PATH"
    if [ -z "$CROSS_COMPILE" ];then
        export CROSS_COMPILE="`basename ${TARGET_TOOLS_PREFIX}`"
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
    KERNEL_FILE=${PRODUCT_OUT}/bzImage
    KERNEL_SRC_DIR=${TOP}/hardware/intel/linux-2.6
    if [ "$_config_file_type" != "kboot" ]; then
        KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
    else
        KERNEL_BUILD_DIR=${PRODUCT_OUT}/kboot/kernel_build
    fi
}

make_kernel() {
    local custom_board=${1}
    local _config_file=""
    local KMAKEFLAGS="ARCH=${ARCH} V=1 O=${KERNEL_BUILD_DIR}"
    mkdir -p ${KERNEL_BUILD_DIR}

    cd $KERNEL_SRC_DIR
    _config_file=i386_${custom_board}_android_defconfig

    if [ -z "$_preserve_kernel_config" ]; then
        rm -f ${KERNEL_BUILD_DIR}/.config
    fi
    if [ "$_clean" ]; then
        make $KMAKEFLAGS mrproper
    fi
    if [ ! -e ${KERNEL_BUILD_DIR}/.config ]; then
        echo "Fetching a kernel .config file for ${_config_file}"

        make $KMAKEFLAGS ${_config_file}
        exit_on_error $? quiet
    fi
    if "$_menuconfig" ; then
        make $KMAKEFLAGS menuconfig
        cp ${KERNEL_BUILD_DIR}/.config arch/x86/configs/$_config_file
    fi

    # Check .config to see if we get what we expect
    awk 'NR>4' arch/x86/configs/$_config_file |
        grep -v '^#' > /tmp/build.$$.1.tmp
    awk 'NR>4' ${KERNEL_BUILD_DIR}/.config |
        grep -v '^#' > /tmp/build.$$.2.tmp
    diff /tmp/build.$$.1.tmp /tmp/build.$$.2.tmp > /dev/null
    if [ $? -ne 0 ]; then
        echo >&3
        echo >&3 "WARNING: The .config file does not match the"
        echo -n >&3 "   reference config file $_config_file..."
    fi

    if [ arch/x86/configs/${_config_file} -nt ${KERNEL_BUILD_DIR}/.config ]; then
        echo >&3
        echo -n >&3 "WARNING: ${_config_file} is newer than .config..."
    fi

    make $KMAKEFLAGS -j${_jobs} bzImage
    exit_on_error $? quiet

    mkdir -p `dirname ${KERNEL_FILE}`
    cp ${KERNEL_BUILD_DIR}/arch/x86/boot/bzImage ${KERNEL_FILE}
    exit_on_error $? quiet

    if [ "$_config_file_type" != "kboot" ]; then
        case "${custom_board}" in
        mrst_ref | ivydale | mrst_edv | crossroads | mfld_cdk | mfld_pr1)
            make_modules ${custom_board}
            exit_on_error $? quiet
            ;;
        generic_x86 | vbox)
            ;;
        esac
    fi

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

    make $KMAKEFLAGS -j${_jobs} modules
    exit_on_error $? quiet

    make $KMAKEFLAGS -j${_jobs} modules_install \
        INSTALL_MOD_STRIP=--strip-unneeded INSTALL_MOD_PATH=${MODULE_SRC}
    exit_on_error $? quiet

    find ${MODULE_SRC} -name *.ko -exec cp -vf {} ${MODULE_DEST} \;
    exit_on_error $? quiet
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
        make_kernel ${custom_board} 
        exit_on_error $?
    done
    exit 0
}

main $*
