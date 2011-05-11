#!/bin/bash

DATE=`date "+%Y.%m%d.%H%M"`
TOP=`dirname $0`

ANDROID_DIR=/tmp/${DATE}

if [[ ! -z $1 ]] && [[ -d $1 ]]; then
    SOURCE_DIR=$1
else
    SOURCE_DIR=${ANDROID_PRODUCT_OUT}
fi

if [[ -z ${SOURCE_DIR} ]]; then
    echo "This tool need to be executed in Android build environment"
    exit 1;
fi

BOOT_BIN=android/boot/boot.bin
SYSTEM_ZIP=android/system/system.zip
IFWI_BIN=android/firmware/ifwi_firmware.bin
DNX_BIN=android/firmware/dnx_firmware.bin
RADIO_BIN=android/firmware/radio_firmware.bin

BOOT_BUILD_TAG=${SOURCE_DIR}/boot/build_tag
SYSTEM_BUILD_TAG=${SOURCE_DIR}/system/etc/build_tag

DEST=${SOURCE_DIR}/ota_update-$TARGET_PRODUCT-$DATE.iso

function init () {
    if [[ ! -f $TOP/content.list ]]; then
        echo "The content.list not found under $0"
        echo "boot.bin and system/ under $SOURCE_DIR"
        echo "will be released."
        BOOT=$SOURCE_DIR/boot.bin
        SYSTEM=$SOURCE_DIR/system
        IFWI_FW=$SOURCE_DIR/ifwi_firmware.bin
        DNX_FW=$SOURCE_DIR/dnx_firmware.bin
    else
        source $TOP/content.list
    fi

    mkdir -p ${ANDROID_DIR}/{`dirname ${BOOT_BIN}`,`dirname ${SYSTEM_ZIP}`,`dirname ${IFWI_BIN}`,`dirname ${RADIO_BIN}`}
}

function gen_md5sum () {
    md5sum -b $1 | awk '{print $1}' > $1.md5
}

function script_append () {
    echo "$1" >> $setup_script;
}

function process_build_result () {
    setup_script=${ANDROID_DIR}/setup.sh
    touch $setup_script && chmod 744 $setup_script
    script_append "#!/bin/sh"
    script_append "# Package name: `basename $DEST`"
    script_append "# Build by `whoami`, `date`"
    script_append ""
    script_append "TOP=\`dirname \$0\`"

    if [[ -f ${BOOT} ]]; then
        cp ${BOOT} ${ANDROID_DIR}/${BOOT_BIN}
        cp ${BOOT_BUILD_TAG} `dirname ${ANDROID_DIR}/${BOOT_BIN}`

        if [[ -f ${ANDROID_DIR}/${BOOT_BIN} ]]; then
            gen_md5sum ${ANDROID_DIR}/${BOOT_BIN}
            script_append "# update boot partition"
            script_append "update_osip --update 0 --image \$TOP/${BOOT_BIN}"
        fi
    fi

    if [[ -d ${SYSTEM} ]]; then
        echo "Generate system.zip, this will take dozens of seconds..."
        # jar cfM $system_zip -C $SYSTEM .
        cp ${SYSTEM_BUILD_TAG} `dirname ${ANDROID_DIR}/$SYSTEM_ZIP}`
        pushd ${SYSTEM}; zip ${ANDROID_DIR}/${SYSTEM_ZIP} -r `ls`; popd

        if [[ -f ${ANDROID_DIR}/${SYSTEM_ZIP} ]]; then
            gen_md5sum ${ANDROID_DIR}/${SYSTEM_ZIP}
            script_append "# update system partition"
            script_append "unzip -o \$TOP/${SYSTEM_ZIP} -d /mnt/system/"
            script_append "# workaround for the executable privlidge missed"
            script_append "# during unzip ${SYSTEM_ZIP}"
            script_append "chmod +x /mnt/system/bin/* /mnt/system/xbin/*"
        fi
    fi

    if [[ -f ${IFWI_FW} ]]; then
        cp ${IFWI_FW} ${ANDROID_DIR}/${IFWI_BIN}
        if [[ -f ${DNX_FW} ]]; then
            cp ${DNX_FW} ${ANDROID_DIR}/${DNX_BIN}
            if [[ -f ${ANDROID_DIR}/${IFWI_BIN} ]]; then
                if [[ -f ${ANDROID_DIR}/${DNX_BIN} ]]; then
                    gen_md5sum ${ANDROID_DIR}/${IFWI_BIN}
                    gen_md5sum ${ANDROID_DIR}/${DNX_BIN}
                    script_append "# update IFWI(SCU) firmware"
                    script_append "# loadfw \$TOP/${IFWI_BIN}"
                fi
            fi
        fi
    fi

    if [[ -f $RADIO_FW ]]; then
        cp $RADIO_FW ${ANDROID_DIR}/${RADIO_BIN}

        if [[ -f ${ANDROID_DIR}/${RADIO_BIN} ]]; then
            gen_md5sum ${ANDROID_DIR}/${RADIO_BIN}
            #script_append "# update radio firmware"
            #script_append "# TODO: burn \$TOP/${RADIO_BIN}..."
            script_append "if [ -f /sbin/loadfw_modem.sh ]; then"
            script_append "    loadfw_modem.sh \$TOP/${RADIO_BIN}"
	    script_append "fi"
        fi
    fi

    chmod 544 $setup_script
}

# main () {
    init $TOP
    process_build_result

    echo "Generate ISO image..."
    mkisofs -v -l -r -J \
            -input-charset utf-8 -V android-${TARGET_PRODUCT} -o $DEST ${ANDROID_DIR}
    chmod 644 $DEST
    # Clean temporary file
    if [[ -d ${ANDROID_DIR} ]]; then
        rm -rf ${ANDROID_DIR};
    fi
# }
