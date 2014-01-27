#!/usr/bin/env python

import subprocess
import os
import json
import tarfile
from optparse import OptionParser

# Dummy error, to handle failed git command nicely
class CommandError(Exception):
    pass

def print_verbose(a):
    if options.verbose:
        print a

# call an external program in a specific directory
def call(wd, cmd):
    origdir = os.getcwd()
    os.chdir(os.path.abspath(wd))

    print_verbose(wd + ' : ' + ' '.join(cmd))

    P = subprocess.Popen(args=cmd, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    os.chdir(os.path.abspath(origdir))
    stdout, stderr = P.communicate()

    print_verbose('Done')
    if P.returncode:
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
    gdata = querygerrit(' OR '.join(grev).split())

    projs = {}
    for r in gdata:
        p = g2p[str(r['project'])]
        if p in projs:
            projs[p].append(r)
        else:
            projs[p] = [r]
        grev.remove(r['number'])

    if grev:
        print 'skipping', ' '.join(grev), 'not found on gerrit'
    return projs

# cherry pick one commit
# p is project, r is gerrit json for this patch
# logchid is used to check if patches is already applied
def chpick_one(p, r, logchid):
    stline = '\t' + r['number'] + '/' + r['pset'] + '\t'
    if logchid.find(r['id']) > -1:
        print stline, 'Already Present'
        return
    br = r['lbranch']
    try:
        call(p, ['git','cherry-pick','--ff', br])
        print stline, 'Applied'
    except CommandError:
        print stline, 'Cherry pick FAILED'
        call(p, ['git','cherry-pick','--abort'])

# use git log --grep 'ChangeID' to check if a patch is present
# this command is long, so we do it once on each project with multiple --grep
def get_log_chid(p, g):
    grepcmd = ['git', 'log']
    for r in g:
        grepcmd.append('--grep')
        grepcmd.append(r['id'])
    return call(p, grepcmd)

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

# fetch and cherry-pick all gerrit inspection.
# grev : gerrit revision number, pset : dict with patchset for each revision
# brname : branchname to create
def chpick(grev, pset, brname):
    projs = query_gerrit_batch(grev)

    for p in projs:
        g = projs[p]

        print 'Project:', p

        #Check local branches
        all_branch = call(p, ['git','branch']).split()
        if brname:
            if brname in all_branch:
                call(p, ['git', 'checkout', brname])
            else:
                call(p, ['git', 'checkout', '-b', brname])

        logchid = get_log_chid(p, g)
        fetch_branches(p, g, pset, all_branch)

        for r in g:
            chpick_one(p, r, logchid)

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
    if logchid.find(r['id']) > -1:
        r['isApplied'] = 'Applied'
    else:
        r['isApplied'] = 'Missing'
    r['bz'] = get_bz_from_commit(r['commitMessage'])
    if r['bz'].isdigit():
        r['bzurl'] = '=hyperlink("http://shilc211.sh.intel.com:41006/show_bug.cgi?id=' + r['bz'] + '","' + r['bz'] + '")'
    else:
        r['bzurl'] = ''
    r['path'] = p
    r['ownername'] = r['owner']['name']
    r['psetinfo'] = r['curpset'] + '/' + r['lastpset']
    r['link'] = '=hyperlink("' + r['url'] + '","' + r['number'] + '")'
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
    f.write('Patch;URL;Review;Verified;Patchset;LatestPatchset;IsApplied;BZ;ProjectDir;Status;Owner;Subject\n')
    column = ['number', 'link', 'review', 'verified', 'curpset', 'lastpset', 'isApplied', 'bzurl', 'path', 'status', 'ownername', 'subject']

    projs = get_info(grev, pset)

    for p in projs:
        for r in projs[p]:
            line = ';'.join([r[c] for c in column]) + '\n'
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
    column = ['number', 'isApplied', 'status', 'bz']
    for p in projs:
        print 'Project ', p
        for r in projs[p]:
            print '\t'.join([r[c] for c in column])

# generate .patch files, and put them in a tar archive.
def genpatch(grev, pset, tfile):
    f = tarfile.open(tfile,'w')

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
# if patches apply, remove the .patch file
# if it fails, let it so user can apply it by hands
def applypatch(tfile):
    f = tarfile.open(tfile,'r')
    f.extractall()

    for patch in f.getnames():
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
    usage = "usage: %prog [options] arg"
    parser = OptionParser(usage)
    parser.add_option("-b", "--branch", dest="brname", default='',
                      help="create branch BRNAME or checkout BRNAME before cherry-pick")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose")
    parser.add_option("-f", "--file", dest="infile", default='', help="read gerrit id from file")
    parser.add_option("-c", "--csv", dest="csvfile", default='', help="write gerrit info to file")
    parser.add_option("-s", "--short", dest="printshort", action='store_true', help="print patches short status")
    parser.add_option("-l", "--long", dest="printlong", action='store_true', help="print patches long status")
    parser.add_option("-g", "--genpatch", dest="genpatch", default='', help="save patches to a tar file")
    parser.add_option("-a", "--applypatch", dest="applypatch", default='', help="apply all patches saved to a tar file")

    (options, args) = parser.parse_args()

    if options.applypatch:
        applypatch(options.applypatch)
        return

    if len(args) < 1 and not options.infile:
        parser.error("needs at least 1 gerrit revision")

    if options.infile:
        args += parse_infile(options.infile)

    if not find_repo_top():
        return
    init_gerrit2path()
    grev, pset = clean_args(args)

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
