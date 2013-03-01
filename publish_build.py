#!/usr/bin/env python
# this script publish the flash files
import sys, shutil
import glob
import os
import json
import zipfile
import re
from flashfile import FlashFile

bldpub = None
ifwi_external_dir = "prebuilts/intel/device/intel/prebuilts/fw/ifwi"
ifwi_private_dir = "device/intel/PRIVATE/fw/ifwi"

def get_link_path(gl):
    print "gl=",gl
    if os.path.islink(gl):
        print "os path real path = ",os.path.realpath(gl)
        return os.path.realpath(gl)
    elif os.path.exists(gl):
        print "No LINK but file exist for %s in directory %s"%(os.path.basename(gl),os.path.dirname(gl))
        return os.path.realpath(gl)
    else:
        print "No file for %s in directory %s"%(os.path.basename(gl),os.path.dirname(gl))
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

def publish_file_without_formatting(src,dst,enforce=True):
    if enforce:
        error = "error"
    else:
        error = "warning"
    # first glob the src specification
    srcl = glob.glob(src)
    if len(srcl) != 1:
        print >>sys.stderr, error, ", "+src+" did not match exactly one file (matched %d files): %s"%(len(srcl)," ".join(srcl))
        if enforce:
            sys.exit(1)
        else:
            return
    src = srcl[0]
    # ensure dir are created
    os.system("mkdir -p "+dst)
    # copy
    print "   copy", src, dst
    shutil.copyfile(src, os.path.join(dst, os.path.basename(src)))

def publish_file(args, src, dest, enforce=True):
    return publish_file_without_formatting(src%args,dest%args,
                                           enforce=enforce)

def find_ifwis(basedir):
    """ walk the ifwi directory for matching ifwi
    return a dict indexed by boardname, with all the information in ir
    """
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    ifwis = {}
    if os.path.exists(os.path.join(basedir, ifwi_private_dir)):
        ifwi_base_dir = ifwi_private_dir
    else:
        ifwi_base_dir = ifwi_external_dir
    # IFWI for Merrifield VP and HVP are not published
    if bld_prod not in ["mrfl_vp","mrfl_hvp"]:
        ifwiglobs = {"blackbay":"mfld_pr*",
                    "lexington":"mfld_gi*",
                    "salitpa":"salitpa",
                    "yukkabeach":"yukkabeach",
                    "victoriabay":"victoriabay vb_pr1",
                    "redhookbay":"ctp_pr[23] ctp_vv2",
                    "ctpscaleht":"ctp_vv2/CTPSCALEHT",
                    "ctpscalelt":"ctp_vv2/CTPSCALELT",
                    "merr_vv":"merr_vv0",
                    "bodegabay":"bodegabay*",
                    "baylake":"baylake*"}[bld_prod]

        print "look for ifwis in the tree for %s"%bld_prod
        for ifwiglob in ifwiglobs.split(" "):
            gl = os.path.join(basedir, ifwi_base_dir,ifwiglob)
            for ifwidir in glob.glob(gl):
                # When the ifwi directory is placed within a subdir, we shall
                # take the subdir in the board name
                nameindex = 0 - ifwiglob.count('/') - 1
                board = ifwidir.split("/")[nameindex]
                for idx in range(nameindex+1, 0):
                    board = board + '_' + ifwidir.split("/")[idx]
                fwdnx = get_link_path(os.path.join(ifwidir,"dnx_fwr.bin"))
                osdnx = get_link_path(os.path.join(ifwidir,"dnx_osr.bin"))
                softfuse = get_link_path(os.path.join(ifwidir,"soft_fuse.bin"))
                xxrdnx = get_link_path(os.path.join(ifwidir,"dnx_xxr.bin"))
                ifwi = get_link_path(os.path.join(ifwidir,"ifwi.bin"))
                ifwiversion = os.path.basename(ifwi)
                ifwiversion = os.path.splitext(ifwiversion)[0]
                print "   found ifwi %s for board %s in %s"%(ifwiversion, board, ifwidir)
                if ifwiversion != "None":
                    ifwis[board] = dict(ifwiversion = ifwiversion,
                                        ifwi = ifwi,
                                        fwdnx = fwdnx,
                                        osdnx = osdnx,
                                        softfuse = softfuse,
                                        xxrdnx = xxrdnx)
    return ifwis

def get_publish_conf():
    res=get_build_options(key='PUBLISH_CONF', default_value=42)
    if res == 42:
        return None
    else:
        return json.loads(res)

def do_we_publish_bld_variant(bld_variant):
    r = get_publish_conf()
    if r != None:
        return bld_variant in r
    else:
        return True

def do_we_publish_extra_build(bld_variant,extra_build):
    """do_we_publish_bld_variant(bld_variant)
    must be True"""
    r = get_publish_conf()
    if r != None:
        return extra_build in r[bld_variant]
    else:
        return True

def publish_build(basedir, bld, bld_variant, bld_prod, buildnumber):
    bld_supports_droidboot = get_build_options(key='TARGET_USE_DROIDBOOT', key_type='boolean')
    bld_supports_ota_flashfile = not(get_build_options(key='FLASHFILE_NO_OTA', key_type='boolean'))
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    bldModemDicosrc= get_build_options(key='FLASH_MODEM_DICO')
    bld_flash_modem = get_build_options(key='FLASH_MODEM', key_type='boolean')
    bld_skip_nvm = get_build_options(key='SKIP_NVM', key_type='boolean')
    publish_ota_target_files = do_we_publish_extra_build(bld_variant,'ota_target_files')
    publish_system_img = do_we_publish_extra_build(bld_variant, 'system_img')
    publish_full_ota = do_we_publish_extra_build(bld_variant, 'full_ota')
    publish_full_ota_flashfile = do_we_publish_extra_build(bld_variant, 'full_ota_flashfile')
    if bld_flash_modem:
        bldModemDico=dict(item.split(':') for item in bldModemDicosrc.split(','))

    product_out=os.path.join(basedir,"out/target/product",bld)
    fastboot_dir=os.path.join(basedir,bldpub,"fastboot-images", bld_variant)
    flashfile_dir=os.path.join(basedir,bldpub,"flash_files")
    ota_inputs_dir=os.path.join(basedir,bldpub,"ota_inputs", bld_variant)
    otafile = "%(bld_prod)s-ota-%(buildnumber)s.zip"%locals()
    targetfile = "%(bld_prod)s-target_files-%(buildnumber)s.zip"%locals()

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.bin", fastboot_dir)
    publish_file(locals(), "%(product_out)s/recovery.img", fastboot_dir, enforce=False)
    system_img_path_in_out = None
    if bld_skip_nvm == False:
       publish_file(locals(), "%(product_out)s/system/etc/firmware/modem/modem_nvm.zip", fastboot_dir, enforce=False)
    if bld_flash_modem:
        for files in os.listdir(product_out + "/obj/ETC/modem_version_intermediates/"):
            if files.endswith(".txt"):
                print "publishing "+files
                publish_file(locals(),"%(product_out)s/obj/ETC/modem_version_intermediates/"+ files , fastboot_dir, enforce=False)
    if bld_supports_droidboot:
        publish_file(locals(), "%(product_out)s/droidboot.img", fastboot_dir, enforce=False)
        publish_file(locals(), "%(product_out)s/droidboot.img.POS.bin", fastboot_dir, enforce=False)
        system_img_path_in_out = os.path.join(product_out,"system.img.gz")
    else:
        publish_file(locals(), "%(product_out)s/recovery.img.POS.bin", fastboot_dir, enforce=False)
        system_img_path_in_out = os.path.join(product_out,"system.tar.gz")
    if publish_system_img:
        publish_file_without_formatting(system_img_path_in_out, fastboot_dir)
    publish_file(locals(), "%(product_out)s/installed-files.txt", fastboot_dir, enforce=False)
    otafile_path_in_out = os.path.join(product_out,otafile)
    if publish_full_ota:
        publish_file_without_formatting(otafile_path_in_out, fastboot_dir, enforce=False)
    if bld_variant.find("user")>=0 and publish_ota_target_files:
        publish_file(locals(), "%(product_out)s/obj/PACKAGING/target_files_intermediates/%(targetfile)s", ota_inputs_dir, enforce=False)
    ifwis = find_ifwis(basedir)


    if bld_flash_modem:
        f = FlashFile(os.path.join(flashfile_dir,  "build-"+bld_variant,"%(bldx)s-%(bld_variant)s-fastboot-%(buildnumber)s.zip" %locals()),"no-modem-reflash.xml")
        # if we have different modem, prepare a flash file for each one
        if len(bldModemDico) > 1:
             for board, modem in bldModemDico.iteritems():
                 xmlFileName="flash-%s-%s.xml" %(board,modem)
                 f.add_xml_file(xmlFileName)
        # if not, use a single flash.xml
        else:
             f.add_xml_file("flash.xml")
    else:
        f = FlashFile(os.path.join(flashfile_dir,  "build-"+bld_variant,"%(bldx)s-%(bld_variant)s-fastboot-%(buildnumber)s.zip" %locals()),"flash.xml")

    f.xml_header("fastboot", bld, "1")
    f.add_file("KERNEL", os.path.join(fastboot_dir,"boot.bin"), buildnumber)
    f.add_file("RECOVERY", os.path.join(fastboot_dir,"recovery.img"), buildnumber)
    if bld_flash_modem:
        for board, modem in bldModemDico.iteritems():
            # if we have different modems, declare them in their respective flash file
            if len(bldModemDico) > 1:
                f.add_file("MODEM", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s.bin" %locals(), buildnumber,xml_filter=["flash-%s-%s.xml"%(board,modem)])
                modemsrc="%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin"
                modemsrcl=glob.glob(modemsrc)
                if len(modemsrcl) == 1:
                     f.add_file("MODEM_DEBUG", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin" %locals(), buildnumber,xml_filter=["flash-%s-%s.xml"%(board,modem)])
            # if not, declare it in the flash.xml file
            else:
                f.add_file("MODEM", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s.bin" %locals(), buildnumber,xml_filter=["flash.xml"])
		modem_src_dir=os.path.join(product_out, "obj/ETC/modem_intermediates/")
                modemsrc=modem_src_dir + "/radio_firmware_" + modem +"_debug.bin"
                modemsrcl=glob.glob(modemsrc)
                print modemsrc + " len %d"%(len(modemsrcl))
                if len(modemsrcl) == 1:
                     f.add_file("MODEM_DEBUG", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin" %locals(), buildnumber,xml_filter=["flash.xml"])

        if bld_skip_nvm == False:
           f.add_file("MODEM_NVM", os.path.join(fastboot_dir,"modem_nvm.zip"), buildnumber)

    if bld_supports_droidboot:
        f.add_file("FASTBOOT", os.path.join(fastboot_dir,"droidboot.img"), buildnumber)
    #the system_img is optionally published, therefore
    #we use the one that is in out to be included in the flashfile
    f.add_file("SYSTEM", system_img_path_in_out, buildnumber)

    for board, args in ifwis.items():
        f.add_codegroup("FIRMWARE",(("IFWI_"+board.upper(), args["ifwi"], args["ifwiversion"]),
                                 ("FW_DNX_"+board.upper(),  args["fwdnx"], args["ifwiversion"])))
    f.add_command("fastboot flash boot $kernel_file", "Flashing boot")
    f.add_command("fastboot flash recovery $recovery_file", "Flashing recovery")
    if bld_flash_modem:
        # if we have different modems, insert flash command in respective flash file
        if len(bldModemDico) > 1:
            for board, modem in bldModemDico.iteritems():
                f.add_command("fastboot flash radio $modem_file", "Flashing modem", xml_filter=["flash-%s-%s.xml"%(board,modem)])
        # if not, insert flash command in the flash.xml file
        else:
            f.add_command("fastboot flash radio $modem_file", "Flashing modem", xml_filter=["flash.xml"],timeout=120000)
        if bld_skip_nvm == False:
           f.add_command("fastboot flash /tmp/modem_nvm.zip $modem_nvm_file", "Flashing modem nvm", xml_filter=["flash.xml"],timeout=120000)
           f.add_command("fastboot oem nvm applyzip /tmp/modem_nvm.zip", "Applying modem nvm", xml_filter=["flash.xml"],timeout=120000)

    if bld_supports_droidboot:
        f.add_command("fastboot flash fastboot $fastboot_file", "Flashing fastboot")
        #f.add_command("fastboot flash boot $recovery_file", "Flashing recovery in kboot")

    for board, args in ifwis.items():
        f.add_command("fastboot flash dnx $fw_dnx_%s_file"%(board.lower()), "Attempt flashing ifwi "+board)
        f.add_command("fastboot flash ifwi $ifwi_%s_file"%(board.lower()), "Attempt flashing ifwi "+board)
    f.add_command("fastboot erase cache", "Erasing cache")
    f.add_command("fastboot erase system", "Erasing system")
    f.add_command("fastboot flash system $system_file", "Flashing system", timeout=300000)
    f.add_command("fastboot continue", "Reboot system")
    f.finish()

    # build the ota flashfile
    if bld_supports_ota_flashfile and publish_full_ota_flashfile:
        f = FlashFile(os.path.join(flashfile_dir, "build-"+bld_variant,"%(bldx)s-%(bld_variant)s-ota-%(buildnumber)s.zip" %locals()), "flash.xml")
        f.xml_header("ota", bld, "1")
        #the ofafile is optionally published, therefore
        #we use the one that is in out to be included in the flashfile
        f.add_file("OTA", otafile_path_in_out, buildnumber)
        f.add_command("adb root", "As root user")
        f.add_command("adb shell rm /cache/recovery/update/*", "Clean cache")
        f.add_command("adb shell rm /cache/ota.zip", "Clean ota.zip")
        f.add_command("adb push $ota_file /cache/ota.zip", "Pushing update", timeout=300000)
        f.add_command("adb shell am startservice -a com.intel.ota.OtaUpdate -e LOCATION /cache/ota.zip", "Trigger os update")
        f.finish()

def publish_blankphone(basedir, bld, buildnumber):
    bld_supports_droidboot = get_build_options(key='TARGET_USE_DROIDBOOT', key_type='boolean')
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    product_out=os.path.join(basedir,"out/target/product",bld)
    blankphone_dir=os.path.join(basedir,bldpub,"flash_files/blankphone")
    partition_filename="partition.tbl"
    partition_file=os.path.join(product_out, partition_filename)
    if bld_supports_droidboot:
        recoveryimg = os.path.join(product_out, "droidboot.img.POS.bin")
    else:
        recoveryimg = os.path.join(product_out, "recovery.img.POS.bin")
    ifwis = find_ifwis(basedir)
    for board, args in ifwis.items():
        # build the blankphone flashfile
        f = FlashFile(os.path.join(blankphone_dir, "%(board)s-blankphone.zip"%locals()), "flash.xml")
        f.add_xml_file("flash-noEraseFactory.xml")

        if args["softfuse"] != "None":
            f.add_xml_file("flash-softfuse.xml")
            f.add_xml_file("flash-softfuse-noEraseFactory.xml")

            f.xml_header("system", bld, "1")
            f.add_gpflag(0x80000245, xml_filter=["flash-softfuse.xml","flash-softfuse-noEraseFactory.xml"])
            f.add_gpflag(0x80000145, xml_filter=["flash.xml","flash-noEraseFactory.xml"])
        else:
            f.xml_header("system", bld, "1")
            f.add_gpflag(0x80000045, xml_filter=["flash.xml"])
        if args["softfuse"] != "None" and args["xxrdnx"] != "None":
            f.add_codegroup("FIRMWARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"]),
                                        ("SOFTFUSE", args["softfuse"], args["ifwiversion"]),
                                        ("XXR_DNX", args["xxrdnx"], args["ifwiversion"])),
                                         xml_filter=["flash-softfuse.xml","flash-softfuse-noEraseFactory.xml"])
            f.add_codegroup("FIRMWARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"]),
                                        ("XXR_DNX", args["xxrdnx"], args["ifwiversion"])),
                                         xml_filter=["flash.xml","flash-noEraseFactory.xml"])
        elif args["softfuse"] != "None" and args["xxrdnx"] == "None":
            f.add_codegroup("FIRMWARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"]),
                                        ("SOFTFUSE", args["softfuse"], args["ifwiversion"])),
                                         xml_filter=["flash-softfuse.xml","flash-softfuse-noEraseFactory.xml"])
            f.add_codegroup("FIRMWARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"])),
                                         xml_filter=["flash.xml","flash-noEraseFactory.xml"])
        elif args["xxrdnx"] != "None":
            f.add_codegroup("FIRWMARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"]),
                                        ("XXR_DNX", args["xxrdnx"], args["ifwiversion"])))
        else:
            f.add_codegroup("FIRMWARE",(("IFWI", args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                                        ("OS_DNX", args["osdnx"], args["ifwiversion"])))
        f.add_codegroup("BOOTLOADER",(("KBOOT", recoveryimg, buildnumber),))

        f.add_codegroup("CONFIG",(("PARTITION_TABLE", partition_file, buildnumber),))
        f.add_command("fastboot oem start_partitioning", "Start partitioning")
        f.add_command("fastboot flash /tmp/%s $partition_table_file" % (partition_filename), "Push partition table on device")
        f.add_command("fastboot oem partition /tmp/%s" % (partition_filename), "Apply partition on device")
        if args["softfuse"] != "None":
            f.add_command("fastboot erase %s"%("factory"), "erase %s partition"%("factory"), xml_filter=["flash.xml","flash-softfuse.xml"])
        else:
            f.add_command("fastboot erase %s"%("factory"), "erase %s partition"%("factory"), xml_filter=["flash.xml"])

        for i in "system cache config logs spare data".split():
            f.add_command("fastboot erase "+i, "erase %s partition"%(i))
        f.add_command("fastboot oem stop_partitioning", "Stop partitioning")
        f.finish()

def publish_modem(basedir, bld):
    # environment variables
    board_have_modem=get_build_options(key='BOARD_HAVE_MODEM', key_type='boolean')
    if not board_have_modem:
        print >> sys.stderr, "bld:%s not supported, no modem for this target" % (bld)
        return 0

    bldModemDicosrc= get_build_options(key='FLASH_MODEM_DICO')
    bldModemDico=dict(item.split(':') for item in bldModemDicosrc.split(','))

    modem_dest_dir=os.path.join(basedir, bldpub, "MODEM/")
    shutil.rmtree(modem_dest_dir,ignore_errors=True)
    ignore_files = shutil.ignore_patterns('Android.mk', '.git')

    product_out=os.path.join(basedir,"out/target/product",bld)
    modem_out_dir=os.path.join(product_out, "system/etc/firmware/modem/")
    modem_src_dir=os.path.join(product_out, "obj/ETC/modem_intermediates/")
    modem_version_src_dir=os.path.join(product_out, "obj/ETC/modem_version_intermediates/")

    for board, modem in bldModemDico.iteritems():
        publish_file(locals(), modem_src_dir + "radio_firmware_" + modem + ".bin", modem_dest_dir + modem)
        publish_file(locals(), modem_src_dir + "radio_firmware_" + modem + "_debug.bin", modem_dest_dir + modem, enforce=False)
        for files in os.listdir(modem_version_src_dir):
            if files.endswith(".txt"):
                publish_file(locals(), modem_version_src_dir + files , modem_dest_dir + modem)

    publish_file(locals(), modem_out_dir + "modem_nvm.zip", modem_dest_dir)

def publish_kernel(basedir, bld, bld_variant):
    product_out=os.path.join(basedir,"out/target/product",bld)
    fastboot_dir=os.path.join(basedir,bldpub,"fastboot-images", bld_variant)

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.bin", fastboot_dir)

def publish_external(basedir, bld, bld_variant):
    os.system("mkdir -p "+os.path.join(basedir,bldpub))
    product_out=os.path.join(basedir,"out/target/product",bld)
    prebuilts_out = os.path.join(product_out,"prebuilts/intel")
    prebuilts_pub = os.path.join(basedir,bldpub,"prebuilts.zip")
    white_list_fn = ".repo/manifests/external_binaries_whitelist"
    white_list = []
    # external_binaries_white_list is a simple text file containing a list of regular expression
    # matching the PRIVATE folders whose we want to publish binary
    try:
        with open(white_list_fn,"r") as f:
            for line in f:
                if not line.startswith("#"):
                    # as /PRIVATE/ has been replaced by /prebuilts/<ref_product>/ in prebuilts dir,
                    # we need to update regexp accordingly
                    white_list.append(line.strip().replace("/PRIVATE/","/prebuilts/[^/]+/"))
    except IOError:
        print "WARNING: unable to publish external: no white list file found!",white_list_fn
    white_list = re.compile("(%s)"%("|".join(white_list)))
    if os.path.exists(prebuilts_out):
        z = zipfile.ZipFile(prebuilts_pub, "w")
        # automatic prebuilt publication
        for root, dirs, files in os.walk(prebuilts_out):
            for f in files:
                filename = os.path.join(root, f)
                arcname = filename.replace(product_out,"")
                if white_list.search(arcname):
                    z.write(filename, arcname)
                    print arcname

        # IFWI publication
        ifwis = find_ifwis(basedir)
        def write_ifwi_bin(board, fn, arcname):
            arcname = os.path.join(ifwi_external_dir, board, arcname)
            print fn.replace(basedir,""),"->", arcname
            z.write(fn, arcname)
        def find_sibling_file(fn, _type, possibilities):
            dn = os.path.dirname(fn)
            for glform in possibilities:
                glform = os.path.join(dn, *glform)
                gl = glob.glob(glform)
                if len(gl)==1:
                    return gl[0]
            print >>sys.stderr, "unable to find %s for external release"%(_type)
            print >>sys.stderr, "please put the file in:"
            print >>sys.stderr, possibilities
            sys.exit(1)
        for k, v in ifwis.items():
            write_ifwi_bin(k, v["ifwi"], "ifwi.bin")
            v["ifwi"] = find_sibling_file(v["ifwi"], "prod ifwi",
                                          [("PROD", "*CRAK_PROD.bin"),
                                           ("..", "PROD", "*CRAK_PROD.bin")]
                                          )
            v["androidmk"] = find_sibling_file(v["ifwi"], "Android.mk",
                                               [("..", "..", "Android.mk"),
                                                ("..", "..", "..", "Android.mk")])
            write_ifwi_bin(k, v["fwdnx"], "dnx_fwr.bin")
            write_ifwi_bin(k, v["osdnx"], "dnx_osr.bin")
            write_ifwi_bin(k, v["ifwi"], "ifwi-prod.bin")
            write_ifwi_bin(k, v["androidmk"], "Android.mk")
        commonandroidmk = find_sibling_file(v["ifwi"], "Android.mk",
                                            [("..", "..", "..","common","Android.mk"),
                                            ("..", "..", "..", "..","common","Android.mk")])
        write_ifwi_bin("common", commonandroidmk, "Android.mk")
        z.close()
if __name__ == '__main__':
    # parse options
    basedir=sys.argv[1]
    bld_prod=sys.argv[2].lower()
    bld=sys.argv[3].lower()
    bld_variant=sys.argv[4]
    buildnumber=sys.argv[5]

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
            external_release = get_build_options(key='EXTERNAL_BINARIES', key_type='boolean', default_value=not bootonly_flashfile)
            if external_release:
                publish_external(basedir, bld, bld_variant)
            if do_we_publish_bld_variant(bld_variant):
                publish_build(basedir, bld, bld_variant, bld_prod, buildnumber)
