# usage:
# vendor/intel/support/kernel-build-hack.sh -c mrst_edv && sh start_kernel.sh
# for quick kernel hacking test loop

fastboot flash /tmp/bzImage out/target/product/mrst_edv/kernel_build/arch/x86/boot/bzImage
fastboot flash /tmp/initrd out/target/product/mrst_edv/boot/ramdisk.img
#CMDLINE="init=/init pci=noearly loglevel=4 androidboot.bootmedia=sdcard androidboot.hardware=mrst_edv s0ix_latency=160"
CMDLINE="init=/init pci=noearly console=ttyS0 loglevel=4 androidboot.bootmedia=sdcard androidboot.hardware=mrst_edv s0ix_latency=160"
#CMDLINE="init=/init pci=noearly earlyprintk=mrstkeep console=ttyS0 loglevel=8 androidboot.bootmedia=sdcard androidboot.hardware=mrst_edv s0ix_latency=160"
cat > /tmp/boot.sh<<EOF
kexec -f -x /tmp/bzImage --ramdisk=/tmp/initrd --command-line="$CMDLINE"
EOF
fastboot flash /tmp/boot.sh /tmp/boot.sh
fastboot oem system "sh /tmp/boot.sh"
