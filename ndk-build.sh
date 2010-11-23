#!/bin/bash

#
# This script is used internally to re-build the toolchains and NDK.
# This is an engineer's tool... definitely not a production tool. Don't expect it to be
# flawelss... at least at this revision.

# Don't use it blindly and then commit the result... look at the files that have been updated
# and consider carefully what changes really need to be made to the ndk/ and prebuilt/ projects.
#
# You'll want to edit this scripot to your needs. Change the VERSIONs and the PRODUCT as required.
# You may want to remote the 'repo init' for the toolchain... at least after you've pulled the
# toolchain the first time.

SDK=$PWD
TOP=$SDK
TODAY=`date '+%Y%m%d'`
PRODUCT=ivydale
BUILD_OUT=/tmp/Toolchain.$LOGNAME.$TODAY
ANDROID_TOOLCHAIN=`dirname $SDK`/Toolchain
ARCH=x86
#ARCH=arm

# Enable to get verbose output from the sub-commands
# VERBOSE="--verbose"

# If BUILD_NUM_CPUS is not already defined in your environment,
# define it as the double of HOST_NUM_CPUS. This is used to
# run make commands in parallel, as in 'make -j$BUILD_NUM_CPUS'
#
if [ -z "$BUILD_NUM_CPUS" ] ; then
    HOST_NUM_CPUS=`cat /proc/cpuinfo | grep processor | wc -l`
    BUILD_NUM_CPUS=`expr $HOST_NUM_CPUS \* 2`
fi

echo "ANDROID_TOOLCHAIN: $ANDROID_TOOLCHAIN"
echo "BUILD_OUT:         $BUILD_OUT"
echo "SDK:               $SDK"
echo "PRODUCT:           $PRODUCT"
echo "ARCH:              $ARCH"
echo

if [ ! -d $SDK/out/target/product/$PRODUCT ]; then
    echo >&2 Rebuild for $PRODUCT first... or change PRODUCT in $0.
    exit 1
fi

MPFR_VERSION=2.4.1

# BINUTILS_VERSION=2.17
# BINUTILS_VERSION=2.19
# BINUTILS_VERSION=2.20.1
BINUTILS_VERSION=2.20.51

# GDB_VERSION=7.1.x
GDB_VERSION=6.6

# TOOLCHAIN=arm-eabi-4.2.1
# TOOLCHAIN_VERSION=4.2.1
TOOLCHAIN_VERSION=4.5.2
TOOLCHAIN=$ARCH-$TOOLCHAIN_VERSION

export ANDROID_NDK_ROOT=$SDK/ndk
export PATH=$PATH:$ANDROID_NDK_ROOT/build/tools

# Uncomment to pull and patch a new toolchain
mkdir -p $ANDROID_TOOLCHAIN
cd $ANDROID_TOOLCHAIN
if [ ! -d .repo ]; then
    repo init -u git://android.intel.com/manifest -b froyo -m toolchain
    repo sync
fi

# CLEAN
cd $ANDROID_TOOLCHAIN
repo forall -c git clean -d -f -x

# CLEAN
rm -rf $BUILD_OUT
rm -rf /tmp/ndk-releaes
rm -rf /tmp/ndk-toolchain-*
rm -rf /tmp/android-toolchain*
rm -rf /tmp/android-ndk-*

echo
echo "Building: android-8 build/tools/build-ndk-sysroot.sh (ensures that libthread_db.so and other libraries are up to date)"
cd $SDK/ndk
time build/tools/build-ndk-sysroot.sh \
      $VERBOSE \
      --build-out=$SDK/out/target/product/$PRODUCT \
      --platform=android-8 \
      --package \
      --abi=x86 > $SDK/build-ndk-sysroot.log 2>&1
if [ $? -ne 0 ]; then
    echo >&2 "build/tools/build-ndk-sysroot.sh failed. Logfile in $SDK/build-ndk-sysroot.log"
    exit 1
fi

echo
echo "Cleaning: Removing unneeded files"
git clean -d -f -x

echo
echo "Building: build/tools/build-gcc.sh"
time build/tools/build-gcc.sh \
      $VERBOSE \
      --platform=android-8 \
      --gdb-version=$GDB_VERSION \
      --mpfr-version=$MPFR_VERSION \
      --binutils-version=$BINUTILS_VERSION \
      --build-out=$BUILD_OUT \
      -j $BUILD_NUM_CPUS \
      $ANDROID_TOOLCHAIN $SDK/ndk $TOOLCHAIN > $SDK/build/tools/build-gcc.log 2>&1
if [ $? -ne 0 ]; then
    echo >&2 "build/tools/build-gcc.sh failed. Logfile in $SDK/build/tools/build-gcc.log"
    exit 1
fi

echo
echo "Building: build/tools/build-gdbserver.sh"
time build/tools/build-gdbserver.sh \
      $VERBOSE \
      --platform=android-8 \
      --build-out=$BUILD_OUT \
      -j $BUILD_NUM_CPUS \
      $ANDROID_TOOLCHAIN/gdb/gdb-$GDB_VERSION/gdb/gdbserver/ $SDK/ndk $TOOLCHAIN > $SDK/build/tools/build-gdbserver.log 2>&1
if [ $? -ne 0 ]; then
    echo >&2 "build/tools/build-gcc.sh failed. Logfile in $SDK/build/tools/build-gdbserver.log"
    exit 1
fi

echo
echo "Building: /tmp/android-ndk-prebuilt-$TODAY-linux-$ARCH.tar.bz2"
time tar cjf /tmp/android-ndk-prebuilt-$TODAY-linux-$ARCH.tar.bz2 *

echo
echo "Building: build/tools/make-release.sh"
time build/tools/make-release.sh \
      $VERBOSE \
      --prebuilt-prefix=/tmp/android-ndk-prebuilt-$TODAY \
      --release=$TODAY \
      --systems=linux-$ARCH
if [ $? -ne 0 ]; then
    echo >&2 "build/tools/build-ndk-sysroot.sh failed. Logfile in $SDK/build-ndk-sysroot.log"
    exit 1
fi

echo
echo "Building: Installing the updated toolchain"
mkdir -p $SDK/prebuilt/linux-x86/toolchain/i686-linux-android-$TOOLCHAIN_VERSION
cp -r $SDK/ndk/build/prebuilt/linux-x86/x86-$TOOLCHAIN_VERSION/* $SDK/prebuilt/linux-x86/toolchain/i686-linux-android-$TOOLCHAIN_VERSION/.

ls /tmp/ndk-release/android-ndk-$TODAY-linux-$ARCH.zip
ls /tmp/android-ndk-prebuilt-$TODAY-linux-$ARCH.tar.bz2
