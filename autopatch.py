#!/usr/bin/env python

# autopatch.py : script to manage patches on top of repo
# Copyright (c) 2014, Intel Corporation.
# Author: Falempe Jocelyn <jocelyn.falempe@intel.com>
#
# This program is free software; you can redistribute it and/or modify it
# under the terms and conditions of the GNU General Public License,
# version 2, as published by the Free Software Foundation.
#
# This program is distributed in the hope it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.

import subprocess
import os
import json
import tarfile
import urllib2
import threading
import sys
from optparse import OptionParser

# Dummy error, to handle failed git command nicely
class CommandError(Exception):
    pass

def print_verbose(a):
    if options.verbose:
        print a

# call an external program in a specific directory
def call(wd, cmd, quiet=False):
    print_verbose(wd + ' : ' + ' '.join(cmd))

    P = subprocess.Popen(args=cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, cwd=wd)
    stdout, stderr = P.communicate()

    print_verbose('Done')
    if P.returncode:
        if not quiet:
            print 'Command', cmd
            print 'Failed ' + stderr
        raise CommandError(stderr)
    return stdout

# look for ".repo" in parent directory
def find_repo_top():
    if os.path.isdir('.repo'):
        return True

    lookdir = os.getcwd()
    while not os.path.isdir(os.path.join(lookdir,'.repo')):
        newlookdir = os.path.dirname(lookdir)
        if lookdir == newlookdir:
            print 'no repo found', lookdir
            return False
        lookdir = newlookdir
    print 'found repo top at', lookdir
    os.chdir(lookdir)
    return True

# Query gerrit server for a list of gerrit patch ID.
# return a list of a json parsed data
def querygerrit(rev):
    cmd = ["ssh", "android.intel.com",
           "gerrit", "query", '--current-patch-set', "--format=json", '--commit-message'] + rev

    print_verbose('Start Gerrit Query ' + ' '.join(cmd))
    p = subprocess.Popen(args=cmd,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()

    print_verbose('Done')

    if p.returncode:
        print "Fetch failed " + stderr

    ret = [json.loads(s) for s in stdout.strip().split('\n')]
    del ret[-1]
    return ret

# Generate a dictionary to convert gerrit project name
# to repo relative path using repo list
def init_gerrit2path():
    global g2p
    g2p = {}
    d = call('.', ['repo','list']).strip()
    for l in d.split('\n'):
        p,g = l.split(':')
        g2p[g.strip()] = p.strip()

# Generate 1 query for all requested gerrit revision
# eg: 111453 OR 123433 OR 115533
# grev : list of gerrit revision number to query
# return a dictionary with {project_path : [ gerjson1, gerjson2, ..]}
def query_gerrit_batch(grev):
    gjson = querygerrit(' OR '.join(grev).split())

    # sort the list in the same order as grev
    gjson.sort(key=lambda r: grev.index(r['number']))

    projs = {}
    for r in gjson:
        if not str(r['project']) in g2p:
            continue

        p = g2p[str(r['project'])]
        if p in projs:
            projs[p].append(r)
        else:
            projs[p] = [r]
        grev.remove(r['number'])
    if grev:
        print 'skipping', ' '.join(grev), 'not found on gerrit'
    return projs

# Download a daily/weekly manifest from artifactory
def download_manifest(period, num, fname):
    mname = 'manifest_' + num + '_generated.xml'
    mpath = os.path.join('.repo', 'manifests', mname)
    if os.path.exists(mpath):
        return mname

    print 'get manifest from artifactory'
    url = 'http://mcg-depot.intel.com:8081/artifactory/cactus-absp/build/eng-builds/main/PSI/' + period + '/' + num + '/' + fname
    mg = urllib2.urlopen(url).read()

    print 'copy it to', mpath
    f = open(mpath, 'w')
    f.write(mg)
    f.close()
    return mname

# Synchronize repo with a specific manifest
# mname is the manifest name in .repo/manifests/ directory
def set_repo_manifest(mname):
    print 'initialize repository'
    call('.', ['repo', 'init', '-m', mname])
    print 'synchronize repository (may take a while)'
    call('.', ['repo', 'sync', '-l', '-d', '-c'])

# set repo to a weekly manifest
# ww is in '2013_WW05' format
def set_repo_weekly(ww):
    mname = download_manifest('weekly', ww, 'manifest-generated.xml')
    set_repo_manifest(mname)

# set repo to a daily manifest
# num is in the '20140205_2940' format
def set_repo_daily(num):
    mname = download_manifest('daily', num, 'manifest-' + num + '-generated.xml')
    set_repo_manifest(mname)

# cherry pick one commit
# p is project, r is gerrit json for this patch
# logchid is used to check if patches is already applied
def chpick_one(p, r, logchid):
    stline = '\t' + r['number'] + '/' + r['pset'] + '\t'
    if r['id'] in logchid:
        return stline + 'Already Present\n'
    br = r['lbranch']
    try:
        call(p, ['git','cherry-pick','--ff', br], quiet=True)
        return stline + 'Applied\n'
    except CommandError:
        call(p, ['git','cherry-pick','--abort'])
        log =  stline + 'Cherry pick FAILED\n'
        log += '\n\t\t'.join(['\t\tyou can resolve the conflict with','cd ' + p, 'git cherry-pick ' + br, 'git mergetool'])
        return log + '\n'

# use git log --grep 'ChangeID' to check if a patch is present
# this command is long, so we do it once on each project with multiple --grep
def get_log_chid(p, g):
    grepcmd = ['git', 'log', '-n', '2000', '--format="%b"']
    msg = call(p, grepcmd).decode('utf8')
    return [r['id'] for r in g if msg.find(r['id']) > 0]

# fetch only required gerrit patches
# save them to a local branch (refs-changes-40-147340-5)
# so we can avoid later git fetch, if the local branch is already present.
# (user shouldn't mess with this branches, or it will break ....)
def fetch_branches(p, g, pset, all_branch):
    ref_to_fetch = []
    for r in g:
        if r['number'] in pset:
            rev = r['number']
            ref = 'refs/changes/' + rev[-2:] + '/' + rev + '/' + pset[rev]
            r['pset'] = pset[rev]
        else:
            ref = r['currentPatchSet']['ref']
            r['pset'] = ref.split('/')[-1]
        lbranch = ref.replace('/', '-')
        r['lbranch'] = lbranch
        if not lbranch in all_branch:
            ref_to_fetch.append('+' + ref + ':' + lbranch)
    if ref_to_fetch:
        call(p, ['git','fetch','umg'] + ref_to_fetch)

def chpick_threaded(p, g, pset, brname, lock):
    #Check local branches
    all_branch = call(p, ['git','branch']).split()
    if brname:
        if brname in all_branch:
            call(p, ['git', 'checkout', brname])
        else:
            call(p, ['git', 'checkout', '-b', brname])
    logchid = get_log_chid(p, g)
    fetch_branches(p, g, pset, all_branch)

    log = 'Project ' + p + '\n'
    for r in g:
        log += chpick_one(p, r, logchid)
    with lock:
        sys.stdout.write(log + '\n')

# fetch and cherry-pick all gerrit inspection.
# grev : gerrit revision number, pset : dict with patchset for each revision
# brname : branchname to create
def chpick(grev, pset, brname):
    projs = query_gerrit_batch(grev)
    allth = []
    lock = threading.Lock()

    for p in projs:
        g = projs[p]

        th = threading.Thread(None, chpick_threaded, None, (p, g, pset, brname, lock), None)
        th.start()
        allth.append(th)

    for th in allth:
        th.join()

# get BZ number from commit message
# find first line with BZ: and get bz number if it exists
def get_bz_from_commit(msg):
    for l in msg.split('\n'):
        if l[0:3] == 'BZ:':
            bznum = l[4:]
            if bznum.isdigit():
                return bznum
    return '-----'

# adding review value is a hard task
# +2 + -2 = -2 and +2 + +1 = +2
def review_add(x, y):
    revtable = { '-2' : 5, '2' : 4, '-1' : 3, '1' : 2, '0' : 1, '' : 0}
    if revtable[x] > revtable[y]:
        return x
    return y

# add more user friendly info in json results
def parse_json_info(p, r, logchid, pset):
    pretty_verify = { '1' : 'Verified', '0' : 'No Score', '' : 'No Score', '-1' : 'Fails'}
    pretty_review = { '-2' : '-2', '-1' : '-1', '0' : '0', '1' : '+1', '2' : '+2', '' : '0'}

    r['lastpset'] = r['currentPatchSet']['ref'].split('/')[-1]
    if r['number'] in pset:
        r['curpset'] = pset[r['number']]
    else:
        r['curpset'] = r['lastpset']
    if r['id'] in logchid:
        r['isApplied'] = 'Applied'
    else:
        r['isApplied'] = 'Missing'
    r['bz'] = get_bz_from_commit(r['commitMessage'])
    if r['bz'].isdigit():
        r['bzurl'] = '=hyperlink("http://shilc211.sh.intel.com:41006/show_bug.cgi?id=' + r['bz'] + '";"' + r['bz'] + '")'
    else:
        r['bzurl'] = ''
    r['path'] = p
    r['ownername'] = r['owner']['name']
    r['psetinfo'] = r['curpset'] + '/' + r['lastpset']
    r['link'] = '=hyperlink("' + r['url'] + '";"' + r['number'] + '")'
    r['review'] = ''
    r['verified'] = ''

    if 'approvals' in r['currentPatchSet']:
        for ap in r['currentPatchSet']['approvals']:
            if ap['type'] == 'Code-Review':
                r['review'] = review_add(r['review'], ap['value'])
            elif ap['type'] == 'Verified':
                r['verified'] = review_add(r['verified'], ap['value'])
    r['review'] = pretty_review[r['review']]
    r['verified'] = pretty_verify[r['verified']]

# get information about a list of patches.
def get_info(grev, pset):
    projs = query_gerrit_batch(grev)
    for p in projs:
        logchid = get_log_chid(p, projs[p])
        for r in projs[p]:
            parse_json_info(p, r, logchid, pset)
    return projs

# print a csv file, so you can import it in Libreoffice/Excel
def pr_csv(grev, pset, outfile):
    f = open(outfile, 'wb')
    f.write('\t'.join(['Patch','URL','Review','Verified','Patchset','Latest Patchset','IsApplied','BZ','Project Dir','Status','Owner','Subject\n']))
    column = ['number', 'link', 'review', 'verified', 'curpset', 'lastpset', 'isApplied', 'bzurl', 'path', 'status', 'ownername', 'subject']

    projs = get_info(grev, pset)

    for p in projs:
        for r in projs[p]:
            line = '\t'.join([r[c] for c in column]) + '\n'
            f.write(line)
    f.close()

# print long information on each gerrit number
def pr_long(grev, pset):
    projs = get_info(grev, pset)
    column = ['url', 'isApplied', 'psetinfo', 'bz', 'status', 'review', 'verified', 'subject']
    print '   ' + '\t'.join(column)
    for p in projs:
        print 'Project ', p
        for r in projs[p]:
            print '   ' + '\t'.join([r[c] for c in column])

# print short summary on each gerrit number
def pr_short(grev, pset):
    projs = get_info(grev, pset)
    for p in projs:
        print '# Project ', p
        for r in projs[p]:
            print r['url'] + ' # ' + r['subject']

# generate .patch files, and put them in a tar archive.
# add current manifest to tar archive if asked to do so ( -m )
def genpatch(grev, pset, tfile):
    f = tarfile.open(tfile,'w')

    if options.manifest:
        mname = os.path.relpath(os.path.realpath('.repo/manifest.xml'))
        print 'ADD ', mname
        f.add(mname)

    projs = query_gerrit_batch(grev)

    for p in projs:
        g = projs[p]

        print 'Project:', p
        # Check local branch (this can avoid long git fetch cmd).
        all_branch = call(p, ['git','branch']).split()

        fetch_branches(p, g, pset, all_branch)

        for r in g:
            pname = call(p, ['git', 'format-patch', '-1', r['lbranch'], '--start-number', r['number']]).strip()
            pname = os.path.join(p, pname)
            newname = os.path.join(p, r['number'] + '-' + r['pset'] + '.patch')
            print 'ADD ', newname
            f.add(pname, arcname=newname)
            os.remove(pname)

    f.close()
    print tfile, 'generated'

# extract files from tar archive and apply them
# if a manifest is present, set repo to this manifest.
# if patches apply, remove the .patch file
# if it fails, let it so user can apply it by hands
def applypatch(tfile):
    f = tarfile.open(tfile,'r')
    f.extractall()

    allfiles = f.getnames()
    mname = [ m for m in allfiles if '.xml' in m ]
    if mname:
        set_repo_manifest(os.path.basename(mname[0]))
        allfiles.remove(mname[0])

    for patch in allfiles:
        p, fname = os.path.split(patch)
        try:
            call(p, ['git', 'am', '-3', '--keep-cr', '--whitespace=nowarn', fname])
            print patch, '\t\t\tApplied'
            os.remove(patch)
        except CommandError:
            print patch, '\t\t\tFAILED'
            call(p, ['git','am','--abort'])
    f.close()
    return

# clean arguments given
# https://android.intel.com/#/c/149140/5 to 149140 pset 5
# remove duplicate
def clean_args(args):
    grev = []
    pset = {}
    for a in args:
        l = a.strip().rstrip('/').split('/')
        #handle patchset revision (ie xxxxx/x)
        if len(l) > 1 and l[-1].isdigit() and l[-2].isdigit():
            if not l[-2] in grev:
                grev.append(l[-2])
                pset[l[-2]] = l[-1]
        elif len(l) > 0 and l[-1].isdigit():
            if not l[-1] in grev:
                grev.append(l[-1])
        else:
            print 'cannot parse', a, 'to a gerrit revision'
    return grev, pset

# parse input file
def parse_infile(fname):
    args = []
    f = open(fname)
    c = f.read()
    for l in c.split('\n'):
        l = l.replace('/#/','/')
        comment = l.find('#')
        if comment > -1:
            l = l[0:comment]
        l = l.strip().rstrip('/')
        if l:
            args.append(l)
    f.close()
    return args

def main():
    global options
    usage = "usage: %prog [options] patch1 patch2 ... "
    description = "Genereric tool to manage a list of patches from gerrit. The default behavior is to apply the patches to current repository"
    parser = OptionParser(usage, description=description)
    parser.add_option("-b", "--branch", dest="brname", default='',
                      help="create branch BRNAME or checkout BRNAME before cherry-pick")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose")
    parser.add_option("-f", "--file", dest="infile", help="read gerrit id from file instead of argument list")
    parser.add_option("-c", "--csv", dest="csvfile", help="write gerrit information on the list of file to a csv file")
    parser.add_option("-s", "--short", dest="printshort", action='store_true', help="print patches short status")
    parser.add_option("-l", "--long", dest="printlong", action='store_true', help="print patches long status")
    parser.add_option("-g", "--genpatch", dest="genpatch", help="save patches to a tar file")
    parser.add_option("-a", "--applypatch", dest="applypatch", help="apply all patches saved to a tar file")
    parser.add_option("-w", "--weekly", dest="weekly", help="synchronize repo to weekly manifest ex: 2014_WW05")
    parser.add_option("-d", "--daily", dest="daily", help="synchronize repo to daily manifest ex: 20140205_2940")
    parser.add_option("-m", "--manifest", dest="manifest", action='store_true', help="when used with -g, add the manifest.xml to the tar file")

    (options, args) = parser.parse_args()

    if not find_repo_top():
        return

    if options.applypatch:
        applypatch(options.applypatch)
        return

    if options.weekly:
        set_repo_weekly(options.weekly)
    elif options.daily:
        set_repo_daily(options.daily)
    elif not options.infile and len(args) < 1:
        parser.print_help()

    init_gerrit2path()

    if options.infile:
        args += parse_infile(options.infile)

    grev, pset = clean_args(args)

    if not grev:
        print 'No patches to process, exiting (use -h for help)'
        return

    if options.csvfile:
        pr_csv(grev, pset, options.csvfile)
        return
    if options.printshort:
        pr_short(grev, pset)
        return
    if options.printlong:
        pr_long(grev, pset)
        return
    if options.genpatch:
        genpatch(grev, pset, options.genpatch)
        return

    chpick(grev, pset, options.brname)

if __name__ == "__main__":
    main()
