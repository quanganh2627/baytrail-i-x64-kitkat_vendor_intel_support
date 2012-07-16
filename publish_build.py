#!/usr/bin/env python
# this script publish the flash files
import sys, shutil
import glob
import os
from flashfile import FlashFile

global bldpub

def get_link_path(gl):
    print "gl=",gl
    if os.path.islink(gl):
        print "os path real path = ",os.path.realpath(gl)
        return os.path.realpath(gl)
    else:
        print "No LINK for %s in directory %s"%(os.path.basename(gl),os.path.dirname(gl))
        return "None"

def get_build_options(key, key_type=None, default_value=None):
    try:
        value = os.environ[key]
        if key_type == 'boolean':
            return value.lower() in "true yes".split()
        else:
            return value
    except KeyError:
        if default_value != None:
           return default_value
        else:
           print >>sys.stderr, "Error: environment variable "+key+" not found"
           sys.exit(1)

def init_global(bld):
    global bldpub
    bldpub = get_build_options(key='TARGET_PUBLISH_PATH')

def publish_file(args, src, dest, enforce=True):
    # first glob the src specification
    if enforce:
        error = "error"
    else:
        error = "warning"
    src = src%args
    srcl = glob.glob(src)
    if len(srcl) != 1:
        print >>sys.stderr, error, ", "+src+" did not match exactly one file (matched %d files): %s"%(len(srcl)," ".join(srcl))
        if enforce:
            sys.exit(1)
        else:
            return
    src = srcl[0]
    # then dest (no need to glob)
    dst = dest%args
    # ensure dir are created
    os.system("mkdir -p "+dst)
    # copy
    print "   copy", src, dst
    shutil.copyfile(src, os.path.join(dst, os.path.basename(src)))

def find_ifwis(basedir):
    """ walk the ifwi directory for matching ifwi
    return a dict indexed by boardname, with all the information in ir
    """
    ifwiglob = {"mfld_pr2":"mfld_pr*",
                "mfld_gi":"mfld_gi",
                "mfld_dv10":"mfld_dv*",
                "mfld_tablet_evx":"mfld_tablet_ev*",
                "ctp_pr0":"ctp_*[rv][0v]",
                "ctp_pr1":"ctp_[pv][rv]1",
                "mfld_cdk":"mfld_cdk"}[bld]

    print "look for ifwis in the tree"
    ifwis = {}
    gl = os.path.join(basedir, "device/intel/PRIVATE/fw/ifwi",ifwiglob)
    for ifwidir in glob.glob(gl):
        board = ifwidir.split("/")[-1]
        fwdnx = get_link_path(os.path.join(ifwidir,"dnx_fwr.bin"))
        osdnx = get_link_path(os.path.join(ifwidir,"dnx_osr.bin"))
        ifwi = get_link_path(os.path.join(ifwidir,"ifwi.bin"))
        ifwiversion = os.path.basename(ifwi)
        ifwiversion = os.path.splitext(ifwiversion)[0]
        print "   found ifwi %s for board %s in %s"%(ifwiversion, board, ifwidir)
        if ifwiversion != "None":
            ifwis[board] = dict(ifwiversion = ifwiversion,
                                ifwi = ifwi,
                                fwdnx = fwdnx,
                                osdnx = osdnx)
    return ifwis

def publish_build(basedir, bld, bld_variant, buildnumber):
    bld_supports_droidboot = True # Force to true for jb boot camp (use prebuilt ics droidboot binary)
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    bld_flash_modem = get_build_options(key='FLASH_MODEM', key_type='boolean')

    product_out=os.path.join(basedir,"out/target/product",bld)
    fastboot_dir=os.path.join(basedir,bldpub,"fastboot-images", bld_variant)
    flashfile_dir=os.path.join(basedir,bldpub,"flash_files")
    ota_inputs_dir=os.path.join(basedir,bldpub,"ota_inputs", bld_variant)
    otafile = "%(bld)s-ota-%(buildnumber)s.zip"%locals()
    targetfile = "%(bld)s-target_files-%(buildnumber)s.zip"%locals()

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.bin", fastboot_dir)
    publish_file(locals(), "%(product_out)s/recovery.img", fastboot_dir, enforce=False)
    if bld_supports_droidboot:
        publish_file(locals(), "%(product_out)s/droidboot.img", fastboot_dir, enforce=False)
        publish_file(locals(), "%(product_out)s/droidboot.img.POS.bin", fastboot_dir, enforce=False)
        publish_file(locals(), "%(product_out)s/system.img.gz", fastboot_dir)
    else:
        publish_file(locals(), "%(product_out)s/recovery.img.POS.bin", fastboot_dir, enforce=False)
        publish_file(locals(), "%(product_out)s/system.tar.gz", fastboot_dir)
    publish_file(locals(), "%(product_out)s/installed-files.txt", fastboot_dir, enforce=False)
    publish_file(locals(), "%(product_out)s/%(otafile)s", fastboot_dir, enforce=False)
    if bld_variant.find("user")>=0:
        publish_file(locals(), "%(product_out)s/obj/PACKAGING/target_files_intermediates/%(targetfile)s", ota_inputs_dir, enforce=False)
    ifwis = find_ifwis(basedir)

    f = FlashFile(os.path.join(flashfile_dir,  "build-"+bld_variant,"%(bldx)s-%(bld_variant)s-fastboot-%(buildnumber)s.zip" %locals()))
    if bld_flash_modem:
        f.add_xml_file("flash-nomodem.xml")
    f.xml_header("fastboot", bld, "1")
    f.add_file("KERNEL", os.path.join(fastboot_dir,"boot.bin"), buildnumber)
    if bld_flash_modem:
        f.add_file("MODEM", "%(product_out)s/radio_firmware.bin" %locals(), buildnumber,xml_filter=["flash-nomodem.xml"])
    f.add_file("SYSTEM", os.path.join(fastboot_dir,"system.img.gz"), buildnumber)

    for board, args in ifwis.items():
        f.add_codegroup("FIRWMARE",(("IFWI_"+board.upper(), args["ifwi"], args["ifwiversion"]),
                                 ("FW_DNX_"+board.upper(),  args["fwdnx"], args["ifwiversion"])))
    f.add_command("fastboot flash boot $kernel_file", "Flashing boot")
    if bld_flash_modem:
        f.add_command("fastboot flash radio $modem_file", "Flashing modem", xml_filter=["flash-nomodem.xml"])

    f.add_command("fastboot erase system", "Erasing system")
    for board, args in ifwis.items():
        f.add_command("fastboot flash dnx $fw_dnx_%s_file"%(board.lower()), "Attempt flashing ifwi "+board)
        f.add_command("fastboot flash ifwi $ifwi_%s_file"%(board.lower()), "Attempt flashing ifwi "+board)
    f.add_command("fastboot flash system $system_file", "Flashing system")
    f.add_command("fastboot continue", "Reboot system")
    f.finish()

def publish_blankphone(basedir, bld, buildnumber):
    bld_supports_droidboot = True # Force to true for jb boot camp (use prebuilt ics droidboot binary)
    product_out=os.path.join(basedir,"out/target/product",bld)
    blankphone_dir=os.path.join(basedir,bldpub,"flash_files/blankphone")
    if bld_supports_droidboot:
        recoveryimg = os.path.join(product_out, "droidboot.img.POS.bin")
    else:
        recoveryimg = os.path.join(product_out, "recovery.img.POS.bin")
    ifwis = find_ifwis(basedir)
    for board, args in ifwis.items():
        # build the blankphone flashfile
        f = FlashFile(os.path.join(blankphone_dir, "%(board)s-blankphone.zip"%locals()))
        f.xml_header("system", bld, "1")
        f.add_codegroup("FIRWMARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                 ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                 ("OS_DNX", args["osdnx"], args["ifwiversion"])))
        f.add_codegroup("BOOTLOADER",(("KBOOT", recoveryimg, buildnumber),))
        for i in "system cache config data".split():
            f.add_command("fastboot erase "+i, "erase %s partition"%(i))
        f.finish()

def publish_modem(basedir, bld):
    # environment variables
    board_have_modem=get_build_options(key='BOARD_HAVE_MODEM', key_type='boolean')
    if not board_have_modem:
        print >> sys.stderr, "bld:%s not supported, no modem for this target" % (bld)
        return 0
    modem_src_dir=os.path.join(basedir, get_build_options(key='RADIO_FIRMWARE_DIR'))
    modem_dest_dir=os.path.join(basedir, bldpub, "MODEM")
    shutil.rmtree(modem_dest_dir,ignore_errors=True)
    ignore_files = shutil.ignore_patterns('Android.mk')
    shutil.copytree(modem_src_dir, modem_dest_dir, ignore=ignore_files)

def publish_kernel(basedir, bld, bld_variant):
    product_out=os.path.join(basedir,"out/target/product",bld)
    fastboot_dir=os.path.join(basedir,bldpub,"fastboot-images", bld_variant)

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.bin", fastboot_dir)

if __name__ == '__main__':
    # parse options
    basedir=sys.argv[1]
    bld=sys.argv[2].lower()
    bld_variant=sys.argv[3]
    buildnumber=sys.argv[4]

    init_global(bld)
    bootonly_flashfile = get_build_options(key='FLASHFILE_BOOTONLY', key_type='boolean', default_value=False)

    if bootonly_flashfile:
        if bld_variant not in ["blankphone","modem"]:
            publish_kernel(basedir, bld, bld_variant)
        else:
            print "nothing to do for this target"
    else:
        if bld_variant == "blankphone":
            publish_blankphone(basedir, bld, buildnumber)
        elif bld_variant == "modem":
            publish_modem(basedir, bld)
        else:
            publish_build(basedir, bld, bld_variant, buildnumber)