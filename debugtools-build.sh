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

    if [ -z "$kernel_build_64bit" -a -z "$CROSS_COMPILE" ];then
        export CROSS_COMPILE="`basename ${TARGET_TOOLS_PREFIX}`"
        if [ ! -z ${USE_CCACHE} ]; then
            export PATH="${CCACHE_TOOLS_DIR}:$PATH"
            export CROSS_COMPILE="ccache $CROSS_COMPILE"
        fi
    fi

    if [ -z "$kernel_build_64bit" ]; then
        export ARCH=i386
	KERNEL_BUILD_FLAGS="ANDROID_TOOLCHAIN_FLAGS=-mno-android"
    else
        export ARCH=x86_64
	KERNEL_BUILD_FLAGS="ANDROID_TOOLCHAIN_FLAGS="
    fi

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
    ctp_pr0 | ctp_pr1 | ctp_nomodem )
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
    KERNEL_BUILD_DIR=${PRODUCT_OUT}/kernel_build
}

# Build a kernel module from source that is not in the kernel build directory
make_module_external() {
    local custom_board=${1}

    cd $KERNEL_SRC_DIR

    if [ ! -d `dirname ${KERNEL_FILE}` ]; then
        echo >&6 "The kernel must be built first. Directory not found: `dirname ${KERNEL_FILE}`"
        exit 1
    fi

    case "${custom_board}" in
    mfld_cdk | mfld_pr2 | mfld_gi | mfld_dv10 | mfld_tablet_evx | ctp_pr0 | ctp_pr1 | ctp_nomodem | mrfl_vp | mrfl_hvp | mrfl_sle)
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
    local KMAKEFLAGS=("ARCH=${ARCH}" "O=${KERNEL_BUILD_DIR}" "${KERNEL_BUILD_FLAGS}" "CUSTOM_BOARD=${custom_board}")
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

    make ${njobs} M=${TOP}/${EXTERNAL_MODULE_DIRECTORY} clean
}



usage() {
    echo "Usage: $0 <options>..."
    echo ""
    echo " -c [generic_x86|vbox|mfld_cdk|mfld_pr2|mfld_gi|mfld_dv10|mfld_tablet_evx|ctp_pr0|ctp_pr1|ctp_nomodem|mrfl_vp|mrfl_hvp|mrfl_sle]"
    echo "                          custom board (target platform)"
    echo " -j [jobs]                # of jobs to run simultaneously.  0=automatic"
    echo " -K                       Build a kboot kernel"
    echo " -k                       build kernel only"
    echo " -t                       testtool build"
    echo " -v                       verbose (V=1) build"
    echo " -C                       clean first"
    echo " -M                       external module source directory"
    echo " -B                       Build a 64bit kernel"
}

main() {
    local custom_board_list="vbox mfld_cdk mfld_pr2 mfld_gi mfld_dv10 mfld_tablet_evx ctp_pr0 ctp_pr1 ctp_nomodem mrfl_vp mrfl_hvp mrfl_sle"

    while getopts vBM:Kc:j:kthCm opt
    do
        case "${opt}" in
        v)
            VERBOSE="V=1"
            ;;
        B)
            kernel_build_64bit=1
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
    done
    exit 0
}

main $*
