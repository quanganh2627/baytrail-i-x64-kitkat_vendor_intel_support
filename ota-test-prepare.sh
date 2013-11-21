#!/bin/bash

set -e

export PROD_KEY_DIR=device/intel/common/testkeys/production-test/
export NEW_DB_KEY=$PROD_KEY_DIR/DB

pushd $ANDROID_BUILD_TOP &> /dev/null

function sign_tfp {
    ./build/tools/releasetools/sign_target_files_apks  \
            --default_key_mapping $PROD_KEY_DIR \
            --key_mapping uefi_bios_db_key=$NEW_DB_KEY \
            --kmodule_key $NEW_DB_KEY \
            --binary_bootimages boot,recovery,fastboot \
            --mkbootimg_args "--signsize 256  --signexec \"vendor/intel/support/getsignature.sh $NEW_DB_KEY.pk8\"" \
            $1 $2
}

function build_provimg {
    ./bootable/iago/tools/provision_from_target_files \
            --mkbootimg_args "--signsize 256  --signexec \"vendor/intel/support/getsignature.sh $NEW_DB_KEY.pk8\"" \
            --ota_update $1 $2 $3
}

rm -rf ota/
mkdir ota/

echo "Cleaning source tree"
make installclean &> /dev/null

echo "Building source software version A"
make -j12 target-files-package &> ota/make-A.log
cp $OUT/obj/PACKAGING/target_files_intermediates/$TARGET_PRODUCT-target_files*.zip ota/tfp-A-testkey.zip

echo "Regenerating UEFI Binaries to create artificial deltas"
cd external/gummiboot
./generate-prebuilts.sh &> $ANDROID_BUILD_TOP/ota/gummiboot.log
cd $ANDROID_BUILD_TOP

cd external/uefi_shim
./generate-prebuilts.sh &> $ANDROID_BUILD_TOP/ota/shim.log
cd $ANDROID_BUILD_TOP

echo "Cleaning source tree"
make installclean &> /dev/null

echo "Building target software version B"
make -j12 target-files-package &> ota/make-B.log
cp $OUT/obj/PACKAGING/target_files_intermediates/$TARGET_PRODUCT-target_files*.zip ota/tfp-B-testkey.zip

echo "Re-signing target-files-packages"
sign_tfp ota/tfp-A-testkey.zip ota/tfp-A.zip
sign_tfp ota/tfp-B-testkey.zip ota/tfp-B.zip

echo "Generating check scripts"
./vendor/intel/support/ota-sums.py ota/tfp-A.zip > ota/check-A.sh
chmod +x ota/check-A.sh
./vendor/intel/support/ota-sums.py ota/tfp-B.zip > ota/check-B.sh
chmod +x ota/check-B.sh

echo "Building OTA update packages"
./build/tools/releasetools/ota_from_target_files ota/tfp-A.zip ota/ota-A.zip
./build/tools/releasetools/ota_from_target_files ota/tfp-B.zip ota/ota-B.zip
./build/tools/releasetools/ota_from_target_files -i ota/tfp-A.zip ota/tfp-B.zip ota/ota-A-B.zip

echo "Building provisioning media"
build_provimg ota/ota-A.zip ota/tfp-A.zip ota/prov-A.img
build_provimg ota/ota-B.zip ota/tfp-B.zip ota/prov-B.img

popd

echo "OTA preparations complete!"
