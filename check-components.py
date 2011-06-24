#!/usr/bin/env python

# this script checks that patch comments comply with the process
# constraints of the tool:
# start from within a repo
# the tool will only check patches in the checked out branch
# more checks will appear soon

from optparse import OptionParser
from subprocess import *
import sys,os,re,errno

# _FindRepo() is from repo script
# used to find the root a the repo we are currently in
GIT = 'git'                     # our git command
MIN_GIT_VERSION = (1, 5, 4)     # minimum supported git version
repodir = '.repo'               # name of repo's private directory
S_repo = 'repo'                 # special repo reposiory
S_manifests = 'manifests'       # special manifest repository
REPO_MAIN = S_repo + '/main.py' # main script

def _FindRepo():
  """Look for a repo installation, starting at the current directory.
  """
  dir = os.getcwd()
  repo = None

  while dir != '/' and not repo:
    repo = os.path.join(dir, repodir, REPO_MAIN)
    if not os.path.isfile(repo):
      repo = None
      dir = os.path.dirname(dir)
  return (repo, os.path.join(dir, repodir))

# split_patch splits a patch in 2 parts: comment and file_list
# in: file
# out: (string,string)
def split_patch(patchfile):
	try:
		patch = open(patchfile, 'r')
	except IOError:                     
		print "file", patch,"does not exist"
		sys.exit(errno.ENOENT)

	comment=[]
	file_list=[]
	start=True
	in_comment=False
	in_file_list=False
	for line in patch.readlines():
		if start==True and line.startswith("Subject:"):
			start=False
			in_comment=True
			line=line[len("Subject: "):]
		if in_comment and line.startswith("---"):
			in_comment=False
			in_file_list=True
			continue
		if in_comment:
			comment.append(line)
			continue
		if in_file_list and not line.strip() == "" and line[1].isdigit():
			in_file_list=False
			break
		if in_file_list and not line.strip() == "":
			fields=line[1:].split(" ")
			file_list.append(fields[0])

	return (comment,file_list)

# split_comment splits a text in paragraph (separation = blank line)
# in: string
# out: list of lines
def split_comment(comment):
	res=[]
	parag=[]
	for l in comment:
		if l.strip()!="":
			parag.append(l)
		else:
			res.append(parag)
			parag=[]
	if l.strip()!="":
		res.append(parag)
	return res

# get_change_id extracts the change ID from a list of lines
# in: list of lines
# out: string
def get_change_id(lines):
	change_id=""
	for l in lines:
		if str(l).startswith("Change-Id: "):
			change_id=l[len("Change-Id: "):]
	return change_id

# check_comment verifies if a comment complies with process rules (it can be updated/enriched over time)
# in: string
# out: (string,string,string) (report status,subject,change_id)
# current checks:
#	- 2nd line is blank
#	- 3rd line (start of comment body) starts with: BZ nnnn
#	- last paragraph contains change_id
def check_comment(comment):
	paragraphs=split_comment(comment)
	bzpattern=r'BZ: \d+'
	subject=paragraphs[0][0].strip()
	bzline=paragraphs[1][0].strip()
	check_ok=True
	report=""
	change_id=get_change_id(paragraphs[-1])
	if len(paragraphs[0])!=1:
		report="\n".join([report,"    Error: no blank line between subject line and comment body"])
	if not re.match(bzpattern,bzline):
		report="\n".join([report,"    Error: first line of comment body is not a Bugzilla ID (BZ: nnnn)"])
	if change_id=="":
		report="\n".join([report,"    Error: last paragraph of comment body should have gerrit Change-ID"])
	if report=="":
		report="    Comment OK"
	else:
		report=report[1:]
	return (report,subject,change_id)

# main

# parse options
parser = OptionParser()

parser.add_option("-f", "--force",
                  action="store_true", dest="force", default=False,
                  help="don't ask before deleting patches at root of repo")

(options, args) = parser.parse_args()
ask_before_delete=not options.force

# get the reference manifest (.repo/manifest.xml)
repo=_FindRepo()[1]
manifest=repo+'/manifest.xml'

if (not os.path.exists(manifest)):
	print "Error: no manifest in repo",repo
	sys.exit(errno.ENOENT)

# cd to repo root (repo format-patch writes patch files at the repo root)
os.chdir(os.path.dirname(repo))

# ask to remove existing patches
files=os.listdir(".")
old_patches=[ patch.strip() for patch in files if re.match("\d{4}\-.*\.patch", patch.strip()) ]
if len(old_patches) != 0:
	if ask_before_delete:
		print "There are old patches in %s:" %(os.getcwd())
		for old_patch in old_patches:
			print "    ",old_patch
		answer = raw_input("Are you OK to remove them? (y/n)")
		if not (answer == "y" or answer == "Y"):
			print "Error: please move your old patches before running this script"
			sys.exit(errno.EPERM)
	for old_patch in old_patches:
		try:
			ret=os.remove(old_patch)
		except OSError:
			print "Error: impossible to delete %s" %(old_patch)
			sys.exit(errno.EPERM)

# list patches to be checked
p5 = Popen(["repo", "format-patch", manifest], stdout=PIPE)
output=p5.communicate()[0]
patches = [ patch.strip() for patch in output.split('\n') if patch.strip() != '' and not patch.startswith('/') and not patch.startswith('no-clobber')]

if len(patches) == 0:
	print "Error: no patch to check"
	sys.exit(errno.ENOENT)
global_status=0

# check patches
print "############## REPORT START #################"
for patch in patches:
	(comment,file_list)=split_patch(patch)
	(report,subject,change_id)=check_comment(comment)
	if report != "    Comment OK":
		global_status=errno.EAGAIN
	print "checking patch %s ..." %(subject)
	print report
	print
	print"Change-Id: %s" %(change_id.strip())
	print
	print"File list:"
	for f in file_list:
		print f
	print"------------------------------------"
	print

print "############## REPORT END ###################"
print
print "Please check that all patches in other maintainers' projects are CodeReviewed+2 and Verified+1"
print "Please check that all patches in the projects you manage are merged"
print

sys.exit(global_status)
