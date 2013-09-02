#!/usr/bin/env python
# this script publish the flash files
import sys
import shutil
import glob
import os
import json
import zipfile
import re
from flashfile import FlashFile
from subprocess import Popen, PIPE

bldpub = None
ifwi_external_dir = "prebuilts/intel/vendor/intel/fw/prebuilts/ifwi"
ifwi_private_dir = "vendor/intel/fw/PRIVATE/ifwi"


def get_link_path(gl):
    if os.path.islink(gl):
        return os.path.realpath(gl)
    elif os.path.exists(gl):
        return os.path.realpath(gl)
    else:
        print "No file for %s in directory %s" % (os.path.basename(gl),
                                                  os.path.dirname(gl))
        return "None"


def get_build_options(key, key_type=None, default_value=None):
    try:
        value = os.environ[key]
        if key_type == 'boolean':
            return value.lower() in "true yes".split()
        else:
            return value
    except KeyError:
        if default_value is not None:
            return default_value
        else:
            print >> sys.stderr, "Error: environment variable " + key + \
                " not found"
            sys.exit(1)


def init_global():
    global bldpub
    bldpub = get_build_options(key='TARGET_PUBLISH_PATH')


def publish_file_without_formatting(src, dst, enforce=True):
    if enforce:
        error = "error"
    else:
        error = "warning"
    # first glob the src specification
    srcl = glob.glob(src)
    if len(srcl) != 1:
        print >> sys.stderr, error, ", " + src + \
            " did not match exactly one file (matched %d files): %s" % (
                len(srcl), " ".join(srcl))
        if enforce:
            sys.exit(1)
        else:
            return
    src = srcl[0]
    # ensure dir are created
    os.system("mkdir -p " + dst)
    # copy
    print "   copy", src, dst
    shutil.copyfile(src, os.path.join(dst, os.path.basename(src)))


def publish_file(args, src, dest, enforce=True):
    return publish_file_without_formatting(src % args, dest % args,
                                           enforce=enforce)


def find_stitched_ifwis(basedir, board_soc, ifwi_base_dir):
    ifwis = {}

    gl = os.path.join(basedir, ifwi_base_dir, "ifwi*")
    for ifwidir in glob.glob(gl):
        if os.path.exists(os.path.join(basedir, ifwi_private_dir, board_soc, "dnx")):
            dnxdir = os.path.join(basedir, ifwi_private_dir, board_soc, "dnx")
        else:
            dnxdir = os.path.join(basedir, ifwi_external_dir, "dnx")

        ifwi_name = os.path.splitext(os.path.basename(ifwidir))[0]
        board_name = ifwi_name.replace("ifwi_", "")
        with open(os.path.join(os.path.dirname(ifwidir), "version"), "r") as fo:
            ifwiversion = fo.readline()[:-1]
            print "\tfound Stitched ifwi %s version:%s in %s" % (ifwi_name, ifwiversion, ifwidir)
            ifwis[board_name] = dict(ifwiversion=ifwiversion,
                                     ifwi=ifwidir,
                                     fwdnx=get_link_path(os.path.join(dnxdir, "dnx_fwr.bin")),
                                     osdnx=get_link_path(os.path.join(dnxdir, "dnx_osr.bin")),
                                     softfuse=get_link_path(os.path.join(ifwidir, "soft_fuse.bin")),
                                     xxrdnx=get_link_path(os.path.join(dnxdir, "dnx_xxr.bin")))
    return ifwis


def find_ifwis(basedir, board_soc):

    ifwi_out_dir = os.path.join('out/target/product', bld, 'ifwi')
    if os.path.exists(os.path.join(basedir, ifwi_out_dir, 'version')):
        """ Stitched ifwi availlable. Prebuilt ifwi remain in the legacy path"""
        return find_stitched_ifwis(basedir, board_soc, ifwi_out_dir)
    """ walk the ifwi directory for matching ifwi
    return a dict indexed by boardname, with all the information in it"""
    ifwis = {}
    if os.path.exists(os.path.join(basedir, ifwi_private_dir)):
        ifwi_base_dir = ifwi_private_dir
    else:
        ifwi_base_dir = ifwi_external_dir
    # IFWI for Merrifield/Moorefield VP, HVP and SLE are not published
    # Filter on _vp, _vp_next, _hvp, _hvp_next, _sle, _sle_next
    isvirtualplatorm = re.match('.*_(vp|hvp|sle)($|\s|_next($|\s))', bld_prod)
    if not(isvirtualplatorm):
        ifwiglobs = {"redhookbay": "ctp_pr[23] ctp_pr3.1 ctp_vv2 ctp_vv3",
                     "redhookbay_next": "ctp_pr[23] ctp_pr3.1 ctp_vv2 ctp_vv3",
                     "ctp7160": "vb_vv_b0_b1",
                     "ctpscalelt": "ctp_vv2/CTPSCALELT",
                     "saltbay_lnp": "saltbay_pr1 saltbay_pr1/DBG saltbay_pr1/PSH",
                     "saltbay_pr1": "saltbay_pr1 saltbay_pr1/DBG saltbay_pr1/PSH",
                     "saltbay_pr1_next": "saltbay_pr1 saltbay_pr1/DBG saltbay_pr1/PSH",
                     "baylake": "baytrail/byt_t",
                     "baylake_next": "baytrail/byt_t",
                     "byt_t_ffrd10": "baytrail/byt_t",
                     "byt_t_ffrd8": "baytrail/byt_t",
                     "byt_m_crb": "baytrail/byt_m",
                     }[bld_prod]

        print "look for ifwis in the tree for %s" % bld_prod

        for ifwiglob in ifwiglobs.split(" "):
            gl = os.path.join(basedir, ifwi_base_dir, ifwiglob)
            base_ifwi = ifwiglob.split("/")[0]
            for ifwidir in glob.glob(gl):
                # When the ifwi directory is placed within a subdir, we shall
                # take the subdir in the board name
                nameindex = 0 - ifwiglob.count('/') - 1
                board = ifwidir.split("/")[nameindex]
                for idx in range(nameindex + 1, 0):
                    board = board + '_' + ifwidir.split("/")[idx]

                if glob.glob(os.path.join(ifwidir, "capsule.bin")):
                    ifwi = get_link_path(os.path.join(ifwidir, "dediprog.bin"))
                    capsule = get_link_path(os.path.join(ifwidir, "capsule.bin"))
                else:
                    fwdnx = get_link_path(os.path.join(ifwidir, "dnx_fwr.bin"))
                    osdnx = get_link_path(os.path.join(ifwidir, "dnx_osr.bin"))
                    softfuse = get_link_path(os.path.join(ifwidir, "soft_fuse.bin"))
                    xxrdnx = get_link_path(os.path.join(ifwidir, "dnx_xxr.bin"))
                    ifwi = get_link_path(os.path.join(ifwidir, "ifwi.bin"))
                ifwiversion = os.path.basename(ifwi)
                ifwiversion = os.path.splitext(ifwiversion)[0]
                print "   found ifwi %s for board %s in %s" % (ifwiversion, board, ifwidir)
                if ifwiversion != "None":
                    if glob.glob(os.path.join(ifwidir, "capsule.bin")):
                        ifwis[board] = dict(ifwiversion=ifwiversion,
                                            ifwi=ifwi,
                                            capsule=capsule,
                                            softfuse="None",
                                            xxrdnx="None")
                    else:
                        fwdnx = get_link_path(os.path.join(
                            ifwidir, "dnx_fwr.bin"))
                        osdnx = get_link_path(os.path.join(
                            ifwidir, "dnx_osr.bin"))
                        softfuse = get_link_path(os.path.join(
                            ifwidir, "soft_fuse.bin"))
                        xxrdnx = get_link_path(os.path.join(
                            ifwidir, "dnx_xxr.bin"))
                        ifwi = get_link_path(os.path.join(ifwidir, "ifwi.bin"))
                    ifwiversion = os.path.basename(ifwi)
                    ifwiversion = os.path.splitext(ifwiversion)[0]
                    print "   found ifwi %s for board %s in %s" % (ifwiversion, board, ifwidir)
                    if ifwiversion is not None:
                        if glob.glob(os.path.join(ifwidir, "capsule.bin")):
                            ifwis[board] = dict(ifwiversion=ifwiversion,
                                                ifwi=ifwi,
                                                capsule=capsule,
                                                softfuse="None",
                                                xxrdnx="None")
                        else:
                            ifwis[board] = dict(ifwiversion=ifwiversion,
                                                ifwi=ifwi,
                                                fwdnx=fwdnx,
                                                osdnx=osdnx,
                                                softfuse=softfuse,
                                                xxrdnx=xxrdnx)
                ulpmc = get_build_options(key='ULPMC_BINARY')
                if glob.glob(ulpmc):
                    ifwis[board]["ulpmc"] = ulpmc
    return ifwis


def get_publish_conf():
    res = get_build_options(key='PUBLISH_CONF', default_value=42)
    if res == 42:
        return None
    else:
        return json.loads(res)


def do_we_publish_bld_variant(bld_variant):
    r = get_publish_conf()
    if r is not None:
        return bld_variant in r
    else:
        return True


def do_we_publish_extra_build(bld_variant, extra_build):
    """do_we_publish_bld_variant(bld_variant)
    must be True"""
    r = get_publish_conf()
    if r is not None:
        return extra_build in r[bld_variant]
    else:
        return True


def publish_build(basedir, bld, bld_variant, bld_prod, buildnumber, board_soc):
    board = ""
    bld_supports_droidboot = get_build_options(key='TARGET_USE_DROIDBOOT', key_type='boolean')
    bld_supports_ota_flashfile = not(get_build_options(key='FLASHFILE_NO_OTA', key_type='boolean'))
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    bldModemDicosrc = get_build_options(key='FLASH_MODEM_DICO')
    bld_flash_modem = get_build_options(key='FLASH_MODEM', key_type='boolean')
    bld_skip_nvm = get_build_options(key='SKIP_NVM', key_type='boolean')
    publish_ota_target_files = do_we_publish_extra_build(bld_variant, 'ota_target_files')
    publish_system_img = do_we_publish_extra_build(bld_variant, 'system_img')
    publish_full_ota = do_we_publish_extra_build(bld_variant, 'full_ota')
    publish_full_ota_flashfile = do_we_publish_extra_build(bld_variant, 'full_ota_flashfile')
    board_modem_flashless = get_build_options(key='BOARD_MODEM_FLASHLESS', key_type='boolean')
    sparse_disabled = get_build_options(key='SPARSE_DISABLED', key_type='boolean')
    if bld_flash_modem:
        bldModemDico = dict(item.split(':') for item in bldModemDicosrc.split(','))

    product_out = os.path.join(basedir, "out/target/product", bld)
    fastboot_dir = os.path.join(basedir, bldpub, "fastboot-images", bld_variant)
    flashfile_dir = os.path.join(basedir, bldpub, "flash_files")
    ota_inputs_dir = os.path.join(basedir, bldpub, "ota_inputs", bld_variant)
    otafile = "%(bld_prod)s-ota-%(buildnumber)s.zip" % locals()
    targetfile = "%(bld_prod)s-target_files-%(buildnumber)s.zip" % locals()

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.img", fastboot_dir)
    publish_file(locals(), "%(product_out)s/recovery.img", fastboot_dir, enforce=False)
    system_img_path_in_out = None
    if not bld_skip_nvm:
        publish_file(locals(), "%(product_out)s/system/etc/firmware/modem/modem_nvm.zip", fastboot_dir, enforce=False)
    if bld_flash_modem and not board_modem_flashless:
        for files in os.listdir(product_out + "/obj/ETC/modem_version_intermediates/"):
            if files.endswith(".txt"):
                print "publishing " + files
                publish_file(locals(), "%(product_out)s/obj/ETC/modem_version_intermediates/" + files, fastboot_dir, enforce=False)
    if bld_supports_droidboot:
        publish_file(locals(), "%(product_out)s/droidboot.img", fastboot_dir, enforce=False)
        publish_file(locals(), "%(product_out)s/droidboot.img.POS.bin", fastboot_dir, enforce=False)
        if sparse_disabled:
            system_img_path_in_out = os.path.join(product_out, "system.img.gz")
        else:
            system_img_path_in_out = os.path.join(product_out, "system.img")
    else:
        publish_file(locals(), "%(product_out)s/recovery.img.POS.bin", fastboot_dir, enforce=False)
        system_img_path_in_out = os.path.join(product_out, "system.tar.gz")
    if publish_system_img:
        publish_file_without_formatting(system_img_path_in_out, fastboot_dir)
    publish_file(locals(), "%(product_out)s/installed-files.txt", fastboot_dir, enforce=False)
    otafile_path_in_out = os.path.join(product_out, otafile)
    if publish_full_ota:
        publish_file_without_formatting(otafile_path_in_out, fastboot_dir, enforce=False)
    if bld_variant.find("user") >= 0 and publish_ota_target_files:
        publish_file(locals(), "%(product_out)s/obj/PACKAGING/target_files_intermediates/%(targetfile)s", ota_inputs_dir, enforce=False)
    ifwis = find_ifwis(basedir, board_soc)

    if bld_flash_modem:
        f = FlashFile(os.path.join(flashfile_dir,  "build-" + bld_variant, "%(bldx)s-%(bld_variant)s-fastboot-%(buildnumber)s.zip" % locals()), "no-modem-reflash.xml")
        # if we have different modem, prepare a flash file for each one
        if len(bldModemDico) > 1 and not board_modem_flashless:
            for board, modem in bldModemDico.iteritems():
                xmlFileName = "flash-%s-%s.xml" % (board, modem)
                f.add_xml_file(xmlFileName)
        # if not, use a single flash.xml
        else:
            f.add_xml_file("flash.xml")
    else:
        f = FlashFile(os.path.join(flashfile_dir,  "build-" + bld_variant, "%(bldx)s-%(bld_variant)s-fastboot-%(buildnumber)s.zip" % locals()), "flash.xml")

    f.xml_header("fastboot", bld, "1")
    f.add_file("KERNEL", os.path.join(fastboot_dir, "boot.img"), buildnumber)
    f.add_file("RECOVERY", os.path.join(fastboot_dir, "recovery.img"), buildnumber)
    if bld_flash_modem:
        if board_modem_flashless:
            publish_file(locals(), "%(product_out)s/system/etc/firmware/modem/modem_flashless.zip", fastboot_dir, enforce=False)
            f.add_file("MODEM", os.path.join(fastboot_dir, "modem_flashless.zip"), buildnumber)
        else:
            for board, modem in bldModemDico.iteritems():
                # if we have different modems, declare them in their respective flash file
                if len(bldModemDico) > 1:
                    f.add_file("MODEM", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s.bin" % locals(), buildnumber, xml_filter=["flash-%s-%s.xml" % (board, modem)])
                    modemsrc = "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin"
                    modemsrcl = glob.glob(modemsrc)
                    if len(modemsrcl) == 1:
                        f.add_file("MODEM_DEBUG", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin" % locals(), buildnumber, xml_filter=["flash-%s-%s.xml" % (board, modem)])
                # if not, declare it in the flash.xml file
                else:
                    f.add_file("MODEM", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s.bin" % locals(), buildnumber, xml_filter=["flash.xml"])
                    modem_src_dir = os.path.join(product_out, "obj/ETC/modem_intermediates/")
                    modemsrc = modem_src_dir + "/radio_firmware_" + modem + "_debug.bin"
                    modemsrcl = glob.glob(modemsrc)
                    print modemsrc + " len %d" % (len(modemsrcl),)
                    if len(modemsrcl) == 1:
                        f.add_file("MODEM_DEBUG", "%(product_out)s/obj/ETC/modem_intermediates/radio_firmware_%(modem)s_debug.bin" % locals(), buildnumber, xml_filter=["flash.xml"])

        if not bld_skip_nvm:
            f.add_file("MODEM_NVM", os.path.join(fastboot_dir, "modem_nvm.zip"), buildnumber)

    if bld_supports_droidboot:
        f.add_file("FASTBOOT", os.path.join(fastboot_dir, "droidboot.img"), buildnumber)
    # the system_img is optionally published, therefore
    # we use the one that is in out to be included in the flashfile
    f.add_file("SYSTEM", system_img_path_in_out, buildnumber)

    for board, args in ifwis.items():
        if "ulpmc" in args:
            f.add_codegroup("ULPMC", (("ULPMC", args["ulpmc"], args["ifwiversion"]),))
        if "capsule" in args:
            f.add_codegroup("CAPSULE", (("CAPSULE_" + board.upper(), args["capsule"], args["ifwiversion"]),))
        else:
            f.add_codegroup("FIRMWARE", (("IFWI_" + board.upper(), args["ifwi"], args["ifwiversion"]),
                                        ("FW_DNX_" + board.upper(),  args["fwdnx"], args["ifwiversion"])))

    f.add_buildproperties("%(product_out)s/system/build.prop" % locals())

    if bld_supports_droidboot:
        f.add_command("fastboot flash fastboot $fastboot_file", "Flashing fastboot")

    f.add_command("fastboot flash recovery $recovery_file", "Flashing recovery")

    for board, args in ifwis.items():
        if not "capsule" in args:
            f.add_command("fastboot flash dnx $fw_dnx_%s_file" % (board.lower(),), "Attempt flashing ifwi " + board)
            f.add_command("fastboot flash ifwi $ifwi_%s_file" % (board.lower(),), "Attempt flashing ifwi " + board)
        elif bld == "byt_m_crb":
            f.add_command("fastboot flash capsule $capsule_%s_file"%(board.lower()), "Flashing capsule")
        if "ulpmc" in args:
            f.add_command("fastboot flash ulpmc $ulpmc_file", "Flashing ulpmc", mandatory=0)

    f.add_command("fastboot erase cache", "Erasing cache")
    f.add_command("fastboot erase system", "Erasing system")
    if bld == "byt_m_crb":
        system_flash_timeout = 700000
    else:
        system_flash_timeout = 300000
    f.add_command("fastboot flash system $system_file", "Flashing system", timeout=system_flash_timeout)
    f.add_command("fastboot flash boot $kernel_file", "Flashing boot")

    if bld_flash_modem:
        # if we have different modems, insert flash command in respective flash file
        if len(bldModemDico) > 1:
            for board, modem in bldModemDico.iteritems():
                f.add_command("fastboot flash radio $modem_file", "Flashing modem", xml_filter=["flash-%s-%s.xml" % (board, modem)])
        # if not, insert flash command in the flash.xml file
        else:
            f.add_command("fastboot flash radio $modem_file", "Flashing modem", xml_filter=["flash.xml"], timeout=220000)
        if not bld_skip_nvm:
            f.add_command("fastboot flash /tmp/modem_nvm.zip $modem_nvm_file", "Flashing modem nvm", xml_filter=["flash.xml"], timeout=220000)
            f.add_command("fastboot oem nvm apply /tmp/modem_nvm.zip", "Applying modem nvm", xml_filter=["flash.xml"], timeout=220000)
    f.add_command("fastboot continue", "Reboot system")

    # build the flash-capsule.xml
    for board, args in ifwis.items():
        if "capsule" in args:
            f.add_xml_file("flash-capsule.xml")
            f_capsule = ["flash-capsule.xml"]
            f.xml_header("fastboot", bld, "1", xml_filter=f_capsule)
            f.add_codegroup("CAPSULE", (("CAPSULE_" + board.upper(), args["capsule"], args["ifwiversion"]),), xml_filter=f_capsule)
            f.add_buildproperties("%(product_out)s/system/build.prop" % locals(), xml_filter=f_capsule)
            f.add_command("fastboot flash capsule $capsule_%s_file" % (board.lower(),), "Attempt flashing ifwi " + board, xml_filter=f_capsule)
            f.add_command("fastboot continue", "Reboot", xml_filter=f_capsule)

    f.finish()

    # build the ota flashfile
    if bld_supports_ota_flashfile and publish_full_ota_flashfile:
        f = FlashFile(os.path.join(flashfile_dir, "build-" + bld_variant, "%(bldx)s-%(bld_variant)s-ota-%(buildnumber)s.zip" % locals()), "flash.xml")
        f.xml_header("ota", bld, "1")
        # the ofafile is optionally published, therefore
        # we use the one that is in out to be included in the flashfile
        f.add_file("OTA", otafile_path_in_out, buildnumber)
        f.add_buildproperties("%(product_out)s/system/build.prop" % locals())
        f.add_command("adb root", "As root user")
        f.add_command("adb shell rm /cache/recovery/update/*", "Clean cache")
        f.add_command("adb shell rm /cache/ota.zip", "Clean ota.zip")
        if bld == "byt_m_crb":
            ota_push_timeout = 1000000
        else:
            ota_push_timeout = 300000
        f.add_command("adb push $ota_file /cache/ota.zip", "Pushing update", timeout=ota_push_timeout)
        f.add_command("adb shell am startservice -a com.intel.ota.OtaUpdate -e LOCATION /cache/ota.zip", "Trigger os update")
        f.finish()


def publish_blankphone(basedir, bld, buildnumber, board_soc):
    bld_supports_droidboot = get_build_options(key='TARGET_USE_DROIDBOOT', key_type='boolean')
    bldx = get_build_options(key='GENERIC_TARGET_NAME')
    product_out = os.path.join(basedir, "out/target/product", bld)
    blankphone_dir = os.path.join(basedir, bldpub, "flash_files/blankphone")
    partition_filename = "partition.tbl"
    partition_file = os.path.join(product_out, partition_filename)
    if bld_supports_droidboot:
        recoveryimg = os.path.join(product_out, "droidboot.img.POS.bin")
    else:
        recoveryimg = os.path.join(product_out, "recovery.img.POS.bin")
    ifwis = find_ifwis(basedir, board_soc)
    for board, args in ifwis.items():
        # build the blankphone flashfile
        f = FlashFile(os.path.join(blankphone_dir, "%(board)s-blankphone.zip" % locals()), "flash.xml")
        f.add_xml_file("flash-EraseFactory.xml")

        default_files = f.xml.keys()

        if args["softfuse"] != "None":
            softfuse_files = ["flash-softfuse.xml", "flash-softfuse-EraseFactory.xml"]
            for softfuse_f in softfuse_files:
                f.add_xml_file(softfuse_f)

            f.xml_header("system", bld, "1")
            f.add_gpflag(0x80000245, xml_filter=softfuse_files)
            f.add_gpflag(0x80000145, xml_filter=default_files)
        else:
            if bld == "byt_t_ffrd10" or bld == "baylake" or bld == "byt_t_ffrd8":
                f.xml_header("fastboot_dnx", bld, "1")
            elif "capsule" in args:
                f.xml_header("fastboot", bld, "1")
            else:
                f.xml_header("system", bld, "1")
                f.add_gpflag(0x80000045, xml_filter=default_files)

        if "capsule" in args:
            default_ifwi = (("CAPSULE", args["capsule"], args["ifwiversion"]),
                            ("DEDIPROG",  args["ifwi"], args["ifwiversion"]),)
        else:
            default_ifwi = (("IFWI", args["ifwi"], args["ifwiversion"]),
                            ("FW_DNX",  args["fwdnx"], args["ifwiversion"]),
                            ("OS_DNX", args["osdnx"], args["ifwiversion"]))

        ifwis_dict = {}
        for xml_file in f.xml.keys():
            ifwis_dict[xml_file] = default_ifwi

        if args["xxrdnx"] != "None":
            xxrdnx = ("XXR_DNX", args["xxrdnx"], args["ifwiversion"])
            for xml_file in f.xml.keys():
                ifwis_dict[xml_file] += (xxrdnx,)

        if args["softfuse"] != "None":
            softfuse = ("SOFTFUSE", args["softfuse"], args["ifwiversion"])
            for xml_file in softfuse_files:
                ifwis_dict[xml_file] += (softfuse,)

        for xml_file in f.xml.keys():
            f.add_codegroup("FIRMWARE", ifwis_dict[xml_file], xml_filter=[xml_file])

        if "capsule" in args:
            fastboot_dir = os.path.join(basedir, bldpub, "fastboot-images", bld_variant)
            f.add_file("FASTBOOT", os.path.join(product_out, "droidboot.img"), buildnumber)
            f.add_file("KERNEL", os.path.join(product_out, "recovery.img"), buildnumber)
            f.add_file("RECOVERY", os.path.join(product_out, "boot.img"), buildnumber)
            f.add_file("INSTALLER", "device/intel/baytrail/installer.cmd", buildnumber)
        else:
            f.add_codegroup("BOOTLOADER", (("KBOOT", recoveryimg, buildnumber),))

        f.add_codegroup("CONFIG", (("PARTITION_TABLE", partition_file, buildnumber),))

        f.add_buildproperties("%(product_out)s/system/build.prop" % locals())

        if "capsule" in args:
            if bld == "byt_t_ffrd10" or bld == "baylake" or bld == "byt_t_ffrd8":
                f.add_command("fastboot boot $fastboot_file", "Downloading fastboot image")
                f.add_command("fastboot continue", "Booting on fastboot image")
                f.add_command("sleep", "Sleep 25 seconds", timeout=25000)
            f.add_command("fastboot oem write_osip_header", "Writing OSIP header")
            if bld == "byt_m_crb":
                f.add_command("fastboot flash boot $fastboot_file", "Flashing boot")
                f.add_command("fastboot flash recovery $fastboot_file", "Flashing recovery")
            else:
                f.add_command("fastboot flash boot $kernel_file", "Flashing boot")
                f.add_command("fastboot flash recovery $recovery_file", "Flashing recovery")
            f.add_command("fastboot flash fastboot $fastboot_file", "Flashing fastboot")

        f.add_command("fastboot oem start_partitioning", "Start partitioning")
        f.add_command("fastboot flash /tmp/%s $partition_table_file" % (partition_filename,), "Push partition table on device")
        f.add_command("fastboot oem partition /tmp/%s" % (partition_filename,), "Apply partition on device")

        if bld == "byt_m_crb":
            tag = "flash.xml -EraseFactory"
        else:
            tag = "-EraseFactory"

        xml_tag_list = [i for i in f.xml.keys() if tag in i]
        f.add_command("fastboot erase %s" % ("factory",), "erase %s partition" % ("factory",), xml_filter=xml_tag_list)

        for i in "system cache config logs spare data".split():
            f.add_command("fastboot erase " + i, "erase %s partition" % (i,))
        f.add_command("fastboot oem stop_partitioning", "Stop partitioning")

        fru_configs = get_build_options(key='FRU_CONFIGS')
        if os.path.exists(fru_configs):
            f.add_xml_file("flash-fru.xml")
            fru = ["flash-fru.xml"]
            f.xml_header("fastboot", bld, "1", xml_filter=fru)

            if bld_prod not in ["saltbay_lnp","saltbay_pr1"]:
                token_filename = "token.bin"
                stub_token = os.path.join(product_out, token_filename)
                # create a token with dummy data to make phone flash tool happy
                os.system("echo 'dummy token' > " + stub_token)
                f.add_codegroup("TOKEN", (("SECURE_TOKEN", stub_token, buildnumber),))
                f.add_command("fastboot flash token $secure_token_file", "Push secure token on device", xml_filter=fru)
            f.add_command("fastboot oem fru set $fru_value", "Flash FRU value on device", xml_filter=fru)
            f.add_command("popup", "Please turn off the board and update AOBs according to the new FRU value", xml_filter=fru)
            f.add_raw_file(fru_configs, xml_filter=fru)

        if not "capsule" in args:
            # Creation of a "flash IFWI only" xml
            flash_IFWI = "flash-IFWI-only.xml"
            f.add_xml_file(flash_IFWI)
            f.xml_header("system", bld, "1", xml_filter=[flash_IFWI])
            f.add_gpflag(0x80000142, xml_filter=[flash_IFWI])
            f.add_codegroup("FIRMWARE", default_ifwi, xml_filter=[flash_IFWI])

        # Create a dedicated flash file for buildbot
        # Use EraseFactory for redhookbay if it exists.
        # Use flash.xml for all other
        # Make sure indentation lines up
        if bld == "redhookbay":
                if not f.copy_xml_file("flash-EraseFactory.xml", "flash-buildbot.xml"):
                    f.copy_xml_file("flash.xml", "flash-buildbot.xml")
        else:
                f.copy_xml_file("flash.xml", "flash-buildbot.xml")
        f.finish()


def publish_modem(basedir, bld):
    # environment variables
    board_have_modem = get_build_options(key='BOARD_HAVE_MODEM', key_type='boolean')
    bld_skip_nvm = get_build_options(key='SKIP_NVM', key_type='boolean')
    if not board_have_modem:
        print >> sys.stderr, "bld:%s not supported, no modem for this target" % (bld,)
        return 0

    bldModemDicosrc = get_build_options(key='FLASH_MODEM_DICO')
    bldModemDico = dict(item.split(':') for item in bldModemDicosrc.split(','))

    modem_dest_dir = os.path.join(basedir, bldpub, "MODEM/")
    shutil.rmtree(modem_dest_dir, ignore_errors=True)
    ignore_files = shutil.ignore_patterns('Android.mk', '.git')

    product_out = os.path.join(basedir, "out/target/product", bld)
    modem_out_dir = os.path.join(product_out, "system/etc/firmware/modem/")
    modem_src_dir = os.path.join(product_out, "obj/ETC/modem_intermediates/")
    modem_version_src_dir = os.path.join(product_out, "obj/ETC/modem_version_intermediates/")

    board_modem_flashless = get_build_options(key='BOARD_MODEM_FLASHLESS', key_type='boolean')

    if board_modem_flashless:
        publish_file(locals(), modem_out_dir + "modem_flashless.zip", modem_dest_dir)
    else:
        for board, modem in bldModemDico.iteritems():
            publish_file(locals(), modem_src_dir + "radio_firmware_" + modem + ".bin", modem_dest_dir + modem)
            publish_file(locals(), modem_src_dir + "radio_firmware_" + modem + "_debug.bin", modem_dest_dir + modem, enforce=False)
            for files in os.listdir(modem_version_src_dir):
                if files.endswith(".txt"):
                    publish_file(locals(), modem_version_src_dir + files, modem_dest_dir + modem)

    if not bld_skip_nvm:
        publish_file(locals(), modem_out_dir + "modem_nvm.zip", modem_dest_dir)


def publish_kernel(basedir, bld, bld_variant):
    product_out = os.path.join(basedir, "out/target/product", bld)
    fastboot_dir = os.path.join(basedir, bldpub, "fastboot-images", bld_variant)

    print "publishing fastboot images"
    # everything is already ready in product out directory, just publish it
    publish_file(locals(), "%(product_out)s/boot.img", fastboot_dir)


def generateAllowedPrebuiltsList(customer):
    """return a list of private paths that:
       - belong to bsp-priv manifest group
       - and have customer annotation <customer>_external='bin'"""
    # we need to specify a group in the repo forall command due to following repo behavior:
    # if a project doesn't have the searched annotation, it is included in the list of repo projects to process
    cmd = "repo forall -g bsp-priv -a %s_external=bin -c 'echo $REPO_PATH'" % (customer,)
    p = Popen(cmd, stdout=PIPE, close_fds=True, shell=True)
    allowedPrebuiltsList, _ = p.communicate()
    # As /PRIVATE/ has been replaced by /prebuilts/<ref_product>/ in prebuilts dir,
    # we need to update regexp accordingly.
    # allowedPrebuilts are only directory path:
    # to avoid /my/path/to/diraaa/dirb/file1 matching
    # /my/path/to/dira, we add a trailing '/' to the path.
    return [allowedPrebuilts.replace("/PRIVATE/", "/prebuilts/[^/]+/") + '/' for allowedPrebuilts in allowedPrebuiltsList.splitlines()]


def publish_stitched_ifwi(basedir, ifwis, board_soc, z):

    def write_ifwi_bin(board, fn, arcname):
        arcname = os.path.join(ifwi_external_dir, board, arcname)
        print fn.replace(basedir, ""), "->", arcname
        z.write(fn, arcname)

    def find_sibling_file(fn, _type, possibilities):
        dn = os.path.dirname(fn)
        for glform in possibilities:
            glform = os.path.join(dn, *glform)
            gl = glob.glob(glform)
            print >> sys.stderr, "\npath:", gl, glform
            if len(gl) == 1:
                return gl[0]
        print >> sys.stderr, "unable to find %s for external release" % (_type,)
        print >> sys.stderr, "please put the file in:"
        print >> sys.stderr, possibilities
        sys.exit(1)

    if ifwis:
        for k, v in ifwis.items():
            write_ifwi_bin(k, v["ifwi"], "ifwi.bin")
            v["androidmk"] = find_sibling_file(v["ifwi"], "Android.mk",
                                                [("", "Android.mk")])
            write_ifwi_bin(k, v["androidmk"], "Android.mk")

            v["version"] = find_sibling_file(v["ifwi"], "version",
                                             [("", "version")])
            write_ifwi_bin(k, v["version"], "version")

            if "fwdnx" in v:
                write_ifwi_bin("dnx", v["fwdnx"], "dnx_fwr.bin")
            if "osdnx" in v:
                write_ifwi_bin("dnx", v["osdnx"], "dnx_osr.bin")
            if "capsule" in v:
                write_ifwi_bin(k, v["capsule"], "capsule.bin")
                v["capsule"] = find_sibling_file(v["capsule"], "prod capsule",
                                                 [("PROD", "*EXT.cap")])
                write_ifwi_bin(k, v["capsule"], "capsule-prod.bin")
        commonandroidmk = find_sibling_file(v["fwdnx"], "external_Android.mk",
                                            [("..", "..", "common", "external_Android.mk"),
                                             ("..", "..", "..", "common", "external_Android.mk"),
                                             ("..", "..", "..", "..", "common", "external_Android.mk")])
        write_ifwi_bin("common", commonandroidmk, "Android.mk")
    z.close()


def publish_external(basedir, bld, bld_variant, board_soc):
    os.system("mkdir -p " + os.path.join(basedir, bldpub))
    product_out = os.path.join(basedir, "out/target/product", bld)
    prebuilts_out = os.path.join(product_out, "prebuilts/intel")
    prebuilts_pub = os.path.join(basedir, bldpub, "prebuilts.zip")
    # white_list contains the list of regular expression
    # matching the PRIVATE folders whose we want to publish binary.
    # We use 'generic' customer config to generate white list
    white_list = generateAllowedPrebuiltsList("g")
    # Need to append the top level generated makefile that includes all prebuilt makefiles
    white_list.append(os.path.relpath(os.path.join(prebuilts_out, "Android.mk"), product_out))
    white_list = re.compile("(%s)" % ("|".join(white_list)),)
    if os.path.exists(prebuilts_out):
        z = zipfile.ZipFile(prebuilts_pub, "w")
        # automatic prebuilt publication
        for root, dirs, files in os.walk(prebuilts_out):
            for f in files:
                filename = os.path.join(root, f)
                arcname = filename.replace(product_out, "")
                if white_list.search(arcname):
                    z.write(filename, arcname)
                    print arcname

        # IFWI publication
        ifwis = find_ifwis(basedir, board_soc)

        if os.path.exists(os.path.join(basedir, 'out/target/product', bld, 'ifwi/version')):
            return publish_stitched_ifwi(basedir, ifwis, board_soc, z)

        def write_ifwi_bin(board, fn, arcname):
            arcname = os.path.join(ifwi_external_dir, board, arcname)
            print fn.replace(basedir, ""), "->", arcname
            z.write(fn, arcname)

        def find_sibling_file(fn, _type, possibilities):
            dn = os.path.dirname(fn)
            for glform in possibilities:
                glform = os.path.join(dn, *glform)
                gl = glob.glob(glform)
                if len(gl) == 1:
                    return gl[0]
            print >> sys.stderr, "unable to find %s for external release" % (_type,)
            print >> sys.stderr, "please put the file in:"
            print >> sys.stderr, possibilities
            sys.exit(1)
        if ifwis:
            for k, v in ifwis.items():
                write_ifwi_bin(k, v["ifwi"], "ifwi.bin")
                v["ifwi"] = find_sibling_file(v["ifwi"], "prod ifwi",
                                              [("PROD", "*CRAK_PROD.bin"),
                                               ("..", "PROD", "*CRAK_PROD.bin"),
                                               ("PROD", "*EXT.bin")]
                                              )
                v["androidmk"] = find_sibling_file(v["ifwi"], "Android.mk",
                                                   [("..", "Android.mk"),
                                                    ("..", "..", "Android.mk"),
                                                    ("..", "..", "..", "Android.mk")]
                                                   )
                if "fwdnx" in v:
                    write_ifwi_bin(k, v["fwdnx"], "dnx_fwr.bin")
                if "osdnx" in v:
                    write_ifwi_bin(k, v["osdnx"], "dnx_osr.bin")
                if "capsule" in v:
                    write_ifwi_bin(k, v["capsule"], "capsule.bin")
                    v["capsule"] = find_sibling_file(v["capsule"], "prod capsule",
                                                     [("PROD", "*EXT.cap")])
                    write_ifwi_bin(k, v["capsule"], "capsule-prod.bin")
                write_ifwi_bin(k, v["ifwi"], "ifwi-prod.bin")
                write_ifwi_bin(k, v["androidmk"], "Android.mk")
            commonandroidmk = find_sibling_file(v["ifwi"], "external_Android.mk",
                                                [("..", "..", "..", "common", "external_Android.mk"),
                                                 ("..", "..", "..", "..", "common", "external_Android.mk")])
            write_ifwi_bin("common", commonandroidmk, "Android.mk")
        z.close()
if __name__ == '__main__':
    # parse options
    basedir = sys.argv[1]
    bld_prod = sys.argv[2].lower()
    bld = sys.argv[3].lower()
    bld_variant = sys.argv[4]
    buildnumber = sys.argv[5]
    board_soc = sys.argv[6]

    init_global()
    bootonly_flashfile = get_build_options(key='FLASHFILE_BOOTONLY', key_type='boolean', default_value=False)

    if bootonly_flashfile:
        if bld_variant not in ["blankphone", "modem"]:
            publish_kernel(basedir, bld, bld_variant)
        else:
            print "nothing to do for this target"
    else:
        if bld_variant == "blankphone":
            publish_blankphone(basedir, bld, buildnumber, board_soc)
        elif bld_variant == "modem":
            publish_modem(basedir, bld)
        else:
            external_release = get_build_options(key='EXTERNAL_BINARIES', key_type='boolean', default_value=not bootonly_flashfile)
            if external_release:
                publish_external(basedir, bld, bld_variant, board_soc)
            if do_we_publish_bld_variant(bld_variant):
                publish_build(basedir, bld, bld_variant, bld_prod, buildnumber, board_soc)
