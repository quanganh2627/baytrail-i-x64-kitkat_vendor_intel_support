#!/usr/bin/env python

import os
import json
from optparse import OptionParser

# main Class to generate xml file from json configuration file
class FlashFileXml:

    def __init__(self, config, platform):
        self.xmlfile = os.path.join(options.directory, config['filename'])
        self.flist = []
        flashtype = config['flashtype']
        self.xml = """\
<?xml version="1.0" encoding="utf-8"?>
<flashfile version="1.0">
    <id>%(flashtype)s</id>
    <platform>%(platform)s</platform>""" % locals()

    def add_file(self, filetype, filename, version):
        if filename in self.flist:
            return

        self.xml += '\n        <code_group name="%(filetype)s">' % locals()
        self.xml += """
            <file TYPE="%(filetype)s">
                <name>%(filename)s</name>
                <version>%(version)s</version>
            </file>""" % locals()
        self.xml += "\n        </code_group>"
        self.flist.append(filename)

    def add_buildproperties(self, buildprop):
        if not os.path.isfile(buildprop):
            return
        self.xml += '\n        <buildproperties>'
        with open(buildprop, 'r') as f:
            for line in f.readlines():
                if not line.startswith("#") and line.count("=") == 1:
                    prop = line.strip().split("=")[0]
                    value = line.strip().split("=")[1]
                    self.xml += '\n            <property name="%(prop)s" value="%(value)s"/>' % locals()
        self.xml += '\n        </buildproperties>'

    def add_command(self, command, description, (timeout, retry, mandatory)):
        command = ' '.join(command)
        self.xml += """
        <command>
            <string>%(command)s</string>
            <timeout>%(timeout)s</timeout>
            <retry>%(retry)s</retry>
            <description>%(description)s</description>
            <mandatory>%(mandatory)s</mandatory>
        </command>""" % locals()

    def parse_command(self, commands):
        for cmd in commands:
            if cmd['type'] in ['fflash', 'fboot', 'apush']:
                fname = os.path.basename(t2f[cmd['target']])
                shortname = fname.split('.')[0]
                self.add_file(shortname, fname, options.btag)
                cmd['pftname'] = '$' + shortname + '_file'

        for cmd in commands:
            params = (cmd.get('timeout', '60000'), cmd.get('retry', '2'), cmd.get('mandatory', '1'))

            if cmd['type'] == 'prop':
                self.add_buildproperties(t2f[cmd['target']])
                continue
            elif cmd['type'] == 'fflash':
                desc = cmd.get('desc', 'Flashing ' + cmd['partition'] + ' image')
                command = ['fastboot', 'flash', cmd['partition'], cmd['pftname']]
            elif cmd['type'] == 'ferase':
                desc = cmd.get('desc', 'Erase ' + cmd['partition'] + ' partition')
                command = ['fastboot', 'erase', cmd['partition']]
            elif cmd['type'] == 'fboot':
                desc = cmd.get('desc', 'Uploading fastboot image.')
                command = ['fastboot', 'boot', cmd['pftname']]
            elif cmd['type'] == 'foem':
                desc = cmd.get('desc', 'fastboot oem ' + cmd['arg'])
                command = ['fastboot', 'oem', cmd['arg']]
            elif cmd['type'] == 'fcontinue':
                desc = cmd.get('desc', 'Rebooting now.')
                command = ['fastboot', 'continue']
            elif cmd['type'] == 'sleep':
                desc = cmd.get('desc', 'Sleep for ' + str(int(params[0]) / 1000) + ' seconds.')
                command = ['sleep']
            elif cmd['type'] == 'adb':
                desc = cmd.get('desc', 'adb ' + cmd['arg'])
                command = ['adb', cmd['arg']]
            elif cmd['type'] == 'apush':
                desc = cmd.get('desc', 'Push ' + cmd['dest'])
                command = ['adb', 'push', cmd['pftname'], cmd['dest']]
            else:
                continue
            self.add_command(command, desc, params)

    def finish(self):
        self.xml += """
</flashfile>"""
        print 'writing ', self.xmlfile
        with open(self.xmlfile, "w") as f:
            f.write(self.xml)

# class to generate installer .cmd file from json configuration file.
# .cmd files are used by droidboot to flash target without USB device.
class FlashFileCmd:

    def __init__(self, config):
        self.cmd = ""
        self.cmdfile = os.path.join(options.directory, config['filename'])

    def parse_command(self, commands):
        for cmd in commands:
            if cmd['type'] == 'fflash':
                self.cmd += 'flash:' + cmd['partition'] + '#/installer/' + os.path.basename(t2f[cmd['target']]) + '\n'
            elif cmd['type'] == 'ferase':
                self.cmd += 'erase:' + cmd['partition']
            elif cmd['type'] == 'foem':
                self.cmd += 'oem:' + cmd['arg'] + '\n'
            elif cmd['type'] == 'fcontinue':
                self.cmd += 'continue\n'

    def finish(self):
        print 'writing ', self.cmdfile
        with open(self.cmdfile, "w") as f:
            f.write(self.cmd)

def parse_config(conf):
    for c in conf['config']:
        if c['filename'][-4:] == '.xml':
            f = FlashFileXml(c, options.platform)
        elif c['filename'][-4:] == '.cmd':
            f = FlashFileCmd(c)

        commands = conf['commands']
        commands = [cmd for cmd in commands if not 'restrict' in cmd or c['name'] in cmd['restrict']]

        f.parse_command(commands)
        f.finish()

# dictionnary to translate Makefile "target" name to filename
def init_t2f_dict():
    d = {}
    for l in options.t2f.split():
        target, fname = l.split(':')
        d[target] = fname
    return d

if __name__ == '__main__':

    global options
    global t2f
    usage = "usage: %prog [options] flash.xml"
    description = "Tools to generate flash.xml"
    parser = OptionParser(usage, description=description)
    parser.add_option("-c", "--config", dest="infile", help="read configuration from file")
    parser.add_option("-p", "--platform", dest="platform", default='default', help="platform refproductname")
    parser.add_option("-b", "--buildtag", dest="btag", default='notag', help="buildtag")
    parser.add_option("-d", "--dir", dest="directory", default='.', help="directory to write generated files")
    parser.add_option("-t", "--target2file", dest="t2f", default=None, help="dictionary to translate makefile target to filename")
    (options, args) = parser.parse_args()

    with open(options.infile, 'rb') as f:
        conf = json.loads(f.read())

    t2f = init_t2f_dict()

    parse_config(conf)
