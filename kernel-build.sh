#!/bin/bash

#
# File descriptor 6 will output the the original stderr of the
# invoked shell. We do this so that a function can directly exit on failure...
# but still output its failure message.
if [ -e /proc/self/fd/6 ] ; then
    echo "The 6th file descriptor is already open"
    echo "Change redirections in (readlink -f $0)"
    exit 1
fi
exec 6>&2
exec 2>&1


function exit_on_error {
    if [ "$1" -ne 0 ]; then
        exit 1
    fi
}



# defaults
TOP=`pwd`
# Default the -j factor to a bit less than the number of CPUs
if [ -n "$MAKEFLAGS" ] ; then
    # Avoid setting the number of jobs in recursive make
    _jobs=0
elif [ -e /proc/cpuinfo ] ; then
    _jobs=`grep -c processor /proc/cpuinfo`
    _jobs=$(($_jobs * 2 * 8 / 10))
elif [ -e /usr/sbin/sysctl ] ; then
    _jobs=`/usr/sbin/sysctl -n hw.ncpu`
    _jobs=$(($_jobs * 2 * 8 / 10))
else
    _jobs=1
    echo "WARNING: Unavailable to determine the number of CPUs, defaulting to ${_jobs} job."
fi
_kernel_only=0
_test=0
_clean=""
_logfile_prefix=`date "+build.%Y%m%d%H%M"`
_nnn=0
_logfile=""
_preserve_kernel_config=""
_menuconfig="false"
_soc_type="mfld"
_host_os=`uname -s | tr '[:upper:]' '[:lower:]'`

init_variables() {
    local custom_board=$1

    if [ -z "${TARGET_TOOLS_PREFIX}" ]; then
        echo >&6 "Warning: TARGET_TOOLS_PREFIX was not set."
        TARGET_TOOLS_PREFIX="$TOP/prebuilts/gcc/${_host_os}/x86/i686-linux-android-4.6/bin/i686-linux-android-"

    fi
    if [ -z "${CCACHE_TOOLS_PREFIX}" ]; then
        echo >&6 "Warning: CCACHE_TOOLS_PREFIX was not set."
        CCACHE_TOOLS_DIR=$TOP/prebuilts/misc/${_host_os}-x86/ccache
    fi
    export PATH="`dirname ${TARGET_TOOLS_PREFIX}`:$PATH"

    # force using minigzip instead of gzip to build bzimage
    export PATH="$TOP/vendor/intel/support:$PATH"

    if [ -z "$CROSS_COMPILE" ];then
        export CROSS_COMPILE="`basename ${TARGET_TOOLS_PREFIX}`"
    fi
    if [ ! -z ${USE_CCACHE} ]; then
        export PATH="${CCACHE_TOOLS_DIR}:$PATH"
        export CROSS_COMPILE="ccache $CROSS_COMPILE"
    fi
    export ARCH=i386
    echo >&6 "ARCH: $ARCH"
    echo >&6 "CROSS_COMPILE: $CROSS_COMPILE"
    echo >&6 "PATH: $PATH"

    if [ -z "${custom_board}" ]; then
        echo "No custom board specified"
        exit_on_error 2
    fi

    case "${custom_board}" in
    generic_x86 | vbox )
        VENDOR=""
        BOARD=generic_x86
        _soc_type="vbox"
        ;;
    mfld_cdk | mfld_pr2 | mfld_gi | mfld_dv10 | mfld_tablet_evx)
        VENDOR=intel
        BOARD=${custom_board}
       _soc_type="mfld"
        ;;
    ctp_pr0 | ctp_pr1 )
        VENDOR=intel
        BOARD=${custom_board}
        _soc_type="ctp"
        ;;
    mrfl_vp | mrfl_hvp | mrfl_sle )
        VENDOR=intel
        BOARD=${custom_board}
        _soc_type="mrfl"
        ;;
    *)
        echo "Unknown board specified \"${custom_board}\""
        exit_on_error 2
        ;;
    esac

    BOARD_CONFIG_DIR=${TOP}/vendor/intel/${BOARD}

    PRODUCT_OUT=${TOP}/out/target/product/${BOARD}
    KERNEL_FILE=${PRODUCT_OUT}/kernel
    KERNEL_SRC_DIR=${TOP}/hardware/intel/linux-2.6
    if [ "$DIFFCONFIGS" != "kboot" ]; then
        KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
    else
        KERNEL_BUILD_DIR=${PRODUCT_OUT}/kboot/kernel_build
    fi
}

make_kernel() {
    local custom_board=${1}
    local KMAKEFLAGS=("ARCH=${ARCH}" "O=${KERNEL_BUILD_DIR}" "ANDROID_TOOLCHAIN_FLAGS=-mno-android")
    local njobs=""
    if [ "${_jobs}" != 0 ] ; then
      njobs="-j${_jobs}"
    fi
    mkdir -p ${KERNEL_BUILD_DIR}

    cd $KERNEL_SRC_DIR

    if [ -z "$_preserve_kernel_config" ]; then
        rm -f ${KERNEL_BUILD_DIR}/.config
    fi
    if [ "$_clean" ]; then
        make "${KMAKEFLAGS[@]}" mrproper
    fi
    if [ ! -e ${KERNEL_BUILD_DIR}/.config ]; then
        echo "making kernel ${KERNEL_BUILD_DIR}/.config file"
        cp arch/x86/configs/i386_${_soc_type}_defconfig ${KERNEL_BUILD_DIR}/.config
        diffconfigs="${custom_board} ${DIFFCONFIGS}"
        echo ${diffconfigs}
        for diffconfig in ${diffconfigs}
        do
            if [ -f $BOARD_CONFIG_DIR/${diffconfig}_diffconfig ]
            then
                echo apply $diffconfig
                cat $BOARD_CONFIG_DIR/${diffconfig}_diffconfig >> ${KERNEL_BUILD_DIR}/.config
            fi
        done
        if [ -f user_diffconfig ]
        then
            echo apply user_diffconfig
            cat user_diffconfig >> ${KERNEL_BUILD_DIR}/.config
        fi
        make V=1 "${KMAKEFLAGS[@]}" defoldconfig
        exit_on_error $? quiet
    fi
    if "$_menuconfig" ; then
        cp ${KERNEL_BUILD_DIR}/.config ${KERNEL_BUILD_DIR}/.config.saved
        make "${KMAKEFLAGS[@]}" menuconfig
        diff -up  ${KERNEL_BUILD_DIR}/.config.saved ${KERNEL_BUILD_DIR}/.config |grep CONFIG_ |grep -v '@@'| grep + |sed 's/^+//' >>user_diffconfig
        rm ${KERNEL_BUILD_DIR}/.config.saved
        echo =========
        echo
        echo `pwd`/user_diffconfig modified accordingly. You can save your modifications to the appropriate config file
        echo
        echo =========
    fi

    make "${KMAKEFLAGS[@]}" ${njobs} bzImage
    exit_on_error $? quiet

    mkdir -p `dirname ${KERNEL_FILE}`
    cp ${KERNEL_BUILD_DIR}/arch/x86/boot/bzImage ${KERNEL_FILE}
    exit_on_error $? quiet

    case "${custom_board}" in
    mfld_cdk | mfld_pr2 | mfld_gi | mfld_dv10 | mfld_tablet_evx | ctp_pr0 | ctp_pr1 | mrfl_vp | mrfl_hvp | mrfl_sle)
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
    if [ "$DIFFCONFIGS" != "kboot" ]; then
        local MODULE_DEST=${PRODUCT_OUT}/root/lib/modules
    else
        local MODULE_DEST=${PRODUCT_OUT}/kboot/root/lib/modules
    fi

    echo "  Making driver modules..."

    rm -fr ${MODULE_SRC}
    rm -fr ${MODULE_DEST}

    if [ ! -d ${MODULE_SRC} ]; then
        mkdir -p ${MODULE_SRC}
    fi
    if [ ! -d ${MODULE_DEST} ]; then
        mkdir -p ${MODULE_DEST}
    fi

    make "${KMAKEFLAGS[@]}" ${njobs} modules
    exit_on_error $? quiet

    make "${KMAKEFLAGS[@]}" ${njobs} modules_install \
        INSTALL_MOD_STRIP=--strip-unneeded INSTALL_MOD_PATH=${MODULE_SRC}
    exit_on_error $? quiet

    find ${MODULE_SRC} -name *.ko -exec cp -vf {} ${MODULE_DEST} \;
    exit_on_error $? quiet
}


# Build a kernel module from source that is not in the kernel build directory
make_module_external() {
    local custom_board=${1}
    local KMAKEFLAGS=("ARCH=${ARCH}" "O=${KERNEL_BUILD_DIR}" "ANDROID_TOOLCHAIN_FLAGS=-mno-android")

    cd $KERNEL_SRC_DIR

    if [ ! -d `dirname ${KERNEL_FILE}` ]; then
        echo >&6 "The kernel must be built first. Directory not found: `dirname ${KERNEL_FILE}`"
        exit 1
    fi

    case "${custom_board}" in
    mfld_cdk | mfld_pr2 | mfld_gi | mfld_dv10 | mfld_tablet_evx | ctp_pr0 | ctp_pr1 | mrfl_vp | mrfl_hvp | mrfl_sle)
        make_module_external_fcn ${custom_board}
        exit_on_error $? quiet
        ;;
    generic_x86 | vbox)
        ;;
    esac

    cd ${TOP}
}

make_module_external_fcn() {
    local custom_board=${1}
    local MODULE_SRC=${PRODUCT_OUT}/kernel_modules
    local MODULE_DEST=${PRODUCT_OUT}/root/lib/modules
    local KMAKEFLAGS=("ARCH=${ARCH}" "O=${KERNEL_BUILD_DIR}" "ANDROID_TOOLCHAIN_FLAGS=-mno-android")
    local modules_name=""
    local modules_file=""
    local njobs=""
    if [ "${_jobs}" != 0 ] ; then
      njobs="-j${_jobs}"
    fi
    echo "  Making driver modules from external source directory..."

    make "${KMAKEFLAGS[@]}" ${njobs} M=${TOP}/${EXTERNAL_MODULE_DIRECTORY} modules
    exit_on_error $? quiet

    modules_file=${TOP}/${EXTERNAL_MODULE_DIRECTORY}/`basename ${EXTERNAL_MODULE_DIRECTORY}`.list

    make "${KMAKEFLAGS[@]}" ${njobs} M=${TOP}/${EXTERNAL_MODULE_DIRECTORY} modules_install \
        INSTALL_MOD_STRIP=--strip-unneeded INSTALL_MOD_PATH=${MODULE_SRC} \
        | tee $modules_file
    exit_on_error $? quiet

    modules_name=`cat $modules_file | grep -o -e "[a-zA-Z0-9_\.\-]*.ko"`
    rm -f $modules_file

    for module in $modules_name
    do
        find ${MODULE_SRC} -name ${module} -exec cp -vf {} ${MODULE_DEST} \;
        exit_on_error $? quiet
    done
}



usage() {
    echo "Usage: $0 <options>..."
    echo ""
    echo " -c [generic_x86|vbox|mfld_cdk|mfld_pr2|mfld_gi|mfld_dv10|mfld_tablet_evx|ctp_pr0|ctp_pr1|mrfl_vp|mrfl_hvp|mrfl_sle]"
    echo "                          custom board (target platform)"
    echo " -j [jobs]                # of jobs to run simultaneously.  0=automatic"
    echo " -K                       Build a kboot kernel"
    echo " -k                       build kernel only"
    echo " -t                       testtool build"
    echo " -v                       verbose (V=1) build"
    echo " -C                       clean first"
    echo " -M                       external module source directory"
}

main() {
    local custom_board_list="vbox mfld_cdk mfld_pr2 mfld_gi mfld_dv10 mfld_tablet_evx ctp_pr0 ctp_pr1 mrfl_vp mrfl_hvp mrfl_sle"

    while getopts vM:Kc:j:kthCmo: opt
    do
        case "${opt}" in
        v)
            VERBOSE="V=1"
            ;;
        K)
            DIFFCONFIGS="kboot"
            ;;
        h)
            usage
            exit 0
            ;;
        M)
            EXTERNAL_MODULE_DIRECTORY="${OPTARG}"
            ;;
        c)
            custom_board_list="${OPTARG}"
            ;;
        j)
            if [ ${OPTARG} -gt 0 ]; then
                _jobs=${OPTARG}
            else
                # Default the -j factor to a bit less than the number of CPUs
                if [ -e /proc/cpuinfo ] ; then
                    _jobs=`grep -c processor /proc/cpuinfo`
                    _jobs=$(($_jobs * 2 * 8 / 10))
                elif [ -e /usr/sbin/sysctl ] ; then
                    _jobs=`/usr/sbin/sysctl -n hw.ncpu`
                    _jobs=$(($_jobs * 2 * 8 / 10))
                else
                    _jobs=1
                    echo "WARNING: Unavailable to determine the number of CPUs, defaulting to ${_jobs} job."
                fi
            fi
            ;;
        k)
            _kernel_only=1
            echo >&6 "Kernel will be built but will not be placed in a boot image."
            ;;
        t)
            export TARGET_BUILD_VARIANT=tests
            _test=1
            ;;
        C)
            _clean=1
            ;;
        o)
            if [ "x${OPTARG}" == "xmenuconfig" ]
            then
                    _menuconfig=true
            fi
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
        init_variables "$custom_board"

        if [ "$EXTERNAL_MODULE_DIRECTORY" ]; then
            echo >&6
            echo >&6 "Building external module for $custom_board"
            echo >&6 "------------------------------------------------"
            make_module_external ${custom_board}
            continue
        fi

        echo >&6
        echo >&6 "Building kernel for $custom_board"
        echo >&6 "---------------------------------"
        make_kernel ${custom_board} 
        exit_on_error $?
    done
    exit 0
}

main $*
