import os,sys

class FlashFile:
    """a class to generate a flashfile zip
    """
    def __init__(self, filename, default_flash_file):
        self.filename = filename
        self.xml = {default_flash_file:""}
        self.filenames = []
        self.filenames_dict = {}

    def add_xml_file(self, xmlfilename):
        if not self.xml.has_key(xmlfilename):
            self.xml[xmlfilename] = ""

    def xml_header_in_xml(self, flashtype, platform, flashversion, xml):
        xml +="""\
<?xml version="1.0" encoding="utf-8"?>
<flashfile version="%(flashversion)s">
    <id>%(flashtype)s</id>
    <platform>%(platform)s</platform>"""%locals()
        return xml

    def apply_f_to_all_valid_xml(self,f,xml_filter):
        for filename,xmls in self.xml.items():
            if not len(xml_filter) :
                self.xml[filename]=f(xmls)
            else:
                if filename in xml_filter:
                    self.xml[filename]=f(xmls)

    def xml_header(self, flashtype, platform, flashversion, xml_filter=[]):
        def f(xml):
            return self.xml_header_in_xml(flashtype,platform,flashversion,xml)
        self.apply_f_to_all_valid_xml(f,xml_filter)

    def add_gpflag_in_xml(self, gpflag, xml):
        xml += """
    <gpflag>
        <value>0x%(gpflag)x</value>
    </gpflag>"""%locals()
        return xml

    def add_gpflag(self, gpflag=0x80000045, xml_filter=[]):
        def f(xml):
            return self.add_gpflag_in_xml(gpflag, xml)
        self.apply_f_to_all_valid_xml(f, xml_filter)

    def add_code_group_in_xml(self, type, files, xml):
        xml += '\n        <code_group name="%(type)s">'%locals()
        for filetype, filename, version in files:
            if not os.path.exists(filename):
                raise OSError("file notfound :" +filename)
            self.filenames_dict[filetype.lower()+"_file"] = os.path.basename(filename)
            filenamebase = os.path.basename(filename)
            xml +="""
            <file TYPE="%(filetype)s">
                <name>%(filenamebase)s</name>
                <version>%(version)s</version>
            </file>"""%locals()
            self.filenames.append(filename)
        xml += "</code_group>"
        return xml

    def add_codegroup(self, type, files, xml_filter=[]):
        def f(xml):
            return self.add_code_group_in_xml(type, files, xml)
        self.apply_f_to_all_valid_xml(f,xml_filter)

    def add_file(self, filetype, filename, version,xml_filter=[]):
        self.add_codegroup(filetype, ((filetype, filename, version),),xml_filter=xml_filter)

    def add_command_in_xml(self, command, description, xml, timeout, retry):
        if False: # disabled code in case phoneflashtool is not ready
            for k,v in self.filenames_dict.items():
                command = command.replace("$"+k, v)
        xml += """
        <command>
            <string>%(command)s</string>
            <timeout>%(timeout)s</timeout>
            <retry>%(retry)s</retry>
            <description>%(description)s</description>
        </command>"""%locals()
        return xml

    def add_command(self, command, description, xml_filter=[], timeout=60000, retry=2):
        def f(xml):
            return self.add_command_in_xml( command, description, xml, timeout, retry)
        self.apply_f_to_all_valid_xml(f,xml_filter)

    def finish(self):
        os.system("mkdir -p "+os.path.dirname(self.filename))
        flashxmls = []
        for (flashname,xml) in self.xml.items():
            if xml != "":
                xml += """
</flashfile>"""
                flashxml = os.path.join(os.path.dirname(self.filename),flashname)
                flashxmls.append(flashxml)
                self.filenames.append(flashxml)
                f = open(flashxml,"w")
                f.write(xml)
                f.close()
        if False: # xml file published for debug
            f = open(self.filename+".xml","w")
            f.write(self.xml)
            f.close()
        outzip = self.filename
        if os.path.exists(outzip):
            os.unlink(outzip)
        print "creating flashfile:", outzip
        for fn in self.filenames:
            # -j option for zip is to ignore directories, and just put the file in the root of the zip
            os.system("zip -j %(outzip)s %(fn)s"%locals())
        for flashxml in flashxmls:
            os.unlink(flashxml)
