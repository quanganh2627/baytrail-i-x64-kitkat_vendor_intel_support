#!/usr/bin/perl

use RPC::XML::Client;
use Data::Dumper;

# Usage : perl update_bz_comment <filename.txt> <release_name> <daily_build_version> <BZLogin> <BZPassword>
# e.g. : perl update_bz_comment info.txt MFLD_R2 20110905_002 BZ_login BZ_pwd
# This script reads a file that contains lines whose structure is as followed
# 1234 980989 0980989 098909
# 1234 being a BZ number and the other information are one or more gerrit patches URL
# The file adds the following comment in the BZ:
# "Integrated in the platform daily release MFLD_R2 build XXXX-YY-ZZ with the patches: patch1 patch2 patch3\n Reporters, please verify and close"

if (scalar(@ARGV) != 5) {
  exit 1;
}

my $inputfile = $ARGV[0];
my $release = $ARGV[1];
my $dailybuild = $ARGV[2];
my $bzlogin = $ARGV[3];
my $bzpassword = $ARGV[4];
my $cli = RPC::XML::Client->new("http://$bzlogin:$bzpassword\@umgbugzilla.sh.intel.com:41006/xmlrpc.cgi");
open (FILE, $inputfile) or die "Cannot open $inputfile";
while (<FILE>) {

  chomp;

  my $string = "";
  my @values = split(" ");
  $valueSize = scalar (@values);
  my $BZnumber = "";

  for my $p (0 .. ($valueSize)) {
      if ($p == 0) {
          $BZnumber = $values[$p];
          $string .= "Integrated in release $release build $dailybuild with the patche(s) ";
      }
      else {
          $string .= "$values[$p] ";
      }
  }

  my $tmp = $cli->send_request('Bug.add_comment', { id => $BZnumber, comment => $string});
}
close (FILE);
exit 0;
