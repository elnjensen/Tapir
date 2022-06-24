#!/usr/bin/perl 

use strict; 
use warnings; 
use CGI;
use Text::CSV qw( csv );

# Simple script to get data (coords, mag, depth) for a TESS Object of
# Interest (TOI) from our local tess target file, given the TIC or TOI
# number.  Outputs JSON data; status field is 0 if not found, 1
# otherwise.

my $q = CGI->new;
 
print $q->header(-type =>"text/json",
		 -charset => "UTF-8",
    );

my $failure_status = '{ "status": 0 }' . "\n";

# Get either the TIC number or TOI number from the name:
my $name = $q->param('name');

my %filter;

# Figure out whether it's a TIC name or TOI name (or neither): 
if ($name =~ /^\s*TIC\s*([\d.]+)\s*$/i) {
    my $tic_num = $1;
    # Escape any decimal point in the string: 
    $tic_num =~ s/\./\\./;
    # Match either with or without trailing .01, .02 etc., i.e. 
    # either including that or not including should match. 
    $filter{1} = sub { m/^TIC $tic_num(\.\d\d)?$/ };
} elsif ($name =~ /^\s*TOI\s*([\d.]+)\s*$/i) {
    my $toi_num = $1;
    # Escape any decimal point in the string: 
    $toi_num =~ s/\./\\./;
    $filter{4} = sub { m/^$toi_num$/ };
} else {
    # Failed to match:
    print $failure_status;
    exit;
}

# # Fetch the TIC number: 
# my $tic = $q->param('tic');

# my $tic_valid;
# # Make sure it only contains numbers or a decimal point: 
# if ($tic !~ /^(TIC\s*)?[\d.]+$/i) {
#     $tic = 'xxx';
#     $tic_valid = 0;
# } else {
#     $tic_valid = 1;
# }

# # Fetch the TIC number: 
# my $toi = $q->param('toi');

# my $toi_valid;
# # Make sure it only contains numbers or a decimal point: 
# if ($toi !~ /^(TOI\s*)?[\d.]+$/i) {
#     $toi = 'xxx';
#     $toi_valid = 0;
# } else {
#     $toi_valid = 1;
# }

# if ($toi_valid) {
#     my $pattern = $toi;
#     $pattern =~ s/\./\\./;
#     # TOI field in target list doesn't have "TOI" in it: 
#     $pattern = s/TOI\s*//i;
#     $filter{4} = sub { m/^$pattern$/ };
# }

# if ($tic_valid) {
#     # Match either with or without trailing .01, .02 etc., i.e. 
#     # either including that or not including should match. 
#     $filter{1} = sub { m/^TIC $tic(\.\d\d)?$/ };
# }

my @lines = @{ Text::CSV::csv(in => '/home/httpd/html/transits/toi_targets.csv', 
			      encoding => "UTF-8",
			      headers => "auto",
			      filter => \%filter,      
		   )};


if (scalar(@lines) == 0) {
    print $failure_status;
    exit;
}


my @fields = ("name", "TOI", "depth", "RA", "Dec", "Tmag");

# Could try to make this more general at some point but for now just
# return the first match if multiple TIC numbers match up.  (Matching
# on TOI should be unique, but if we strip the .01, .02 etc. from the
# TIC number, that could match multiple stars.

my $t = $lines[0];
print "{\n\"status\": 1,\n";
my $i = 0;
# Copy the mag field to one with a more accurate name. Even though
# it's really TESS mag, the mag field is labeled 'vmag' for
# compatibility with other target files.
$t->{Tmag} = $t->{vmag};
foreach my $f (@fields) {
    print "\"$f\": \"$t->{$f}\"";
    # No trailing comma on last field:
    if ($i == $#fields) {
	print "\n";
    } else {
	print ",\n";
    }	
    $i++;
}
print "}\n";



