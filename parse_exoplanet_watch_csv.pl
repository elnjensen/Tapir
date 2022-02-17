#!/usr/bin/perl

# Script to parse the CSV file of exoplanets for the Exoplanet Watch
# program.  Given the field names, I think this is essentially a
# download of a subset of transiting planets from NASA's Exoplanet
# Archive. 

# Copyright 2012-2022 Eric Jensen, ejensen1@swarthmore.edu.
# 
# This file is part of the Tapir package, a set of (primarily)
# web-based tools for planning astronomical observations.  For more
# information, see  the README.txt file or 
# http://astro.swarthmore.edu/~jensen/tapir.html .
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program, in the file COPYING.txt.  If not, see
# <http://www.gnu.org/licenses/>.


# Script to parse the CSV file of exoplanets for the Exoplanet Watch
# program, in order to pull out transiting planets and output just
# selected fields in an easier-to-read format for calculating transit
# ephemerides.  Attempts to calculate a transit duration if none is
# given in the file.

# For my use, I fetch the CSV file from JPL periodically
# via a cron job, and then run this script on it to generate my local
# plain-text target file for the transit-finding script.  My cron job
# looks something like this; the '-N' argument to wget causes the
# remote file to be fetched only if it is newer than the local copy. 

# cd /home/httpd/html/transits ; \ 
# wget -N [url here]  2>&1 ;  \
#  ./parse_exoplanet_watch_csv.pl CSV_file > exoplanettransit_targets.csv

# Initial creation, Eric Jensen, ejensen1@swarthmore.edu
# 2022-02-09 based on previous scripts. 

use Text::CSV qw( csv );
use Getopt::Std;
use Math::Trig qw(deg2rad pi);
use List::Util qw(min max);
use DateTime;
use DateTime::Format::Epoch::JD;

use strict;
use warnings; 

use constant R_sun => 6.957E8;  # Rsun in meters per IAU
# Mean R_Jupiter in meters per IAU WG on Cartographic Coordinates and
# Rotational Elements 2009
use constant R_jup => 6.9911E7  ; 
use constant AU => 149597870700;  # AU in meters per IAU

# Our target file is encoded as UTF-8, so make sure everything we
# write out is encoded in the same way: 
binmode(STDOUT, ":utf8");

# Unbuffered output, helps with tracking error messages: 
$| = 1;

# Set the -d flag ("debug") for verbose output of (some) problems.

our ($opt_d, $DEBUG);

my $options = 'd';

getopts($options);

if ($opt_d) {
    $DEBUG = 1;
} else {
    $DEBUG = 0;
}

# For calculating uncertainty on transit times below, we need to know
# how far we are from the epoch when the ephemeris was defined, so get
# the current JD: 
my $this_jd = DateTime::Format::Epoch::JD->format_datetime(DateTime->now());

my ($p, $V, $comment, $name, $duration,
    $duration_hours, $depth_ppt, $depth_ppt_string, $prev_name, 
    $i);


# Slurp all the lines from the file so we can loop over them and group
# together entries for the same planet. 

# Read from STDIN unless a filename is passed on the command line: 
my $datafile = *STDIN;
if (defined $ARGV[0]) {
    $datafile = $ARGV[0];
}

# Read the CSV file; return value is a reference to an array of
# hashes, so immediately dereference to get the array: 
my @csv_lines = @{ Text::CSV::csv(allow_whitespace => '1',
				  in => $datafile, 
				  encoding => "UTF8",
				  headers => "auto",
		                  )};

# Make a first pass through the targets to save only those entries
# that have sufficient information for us to calculate an ephemeris;
# that makes the logic in the next loop cleaner. 

my @good_entries = ();


foreach $p (@csv_lines) {

    # Make sure it has the entries we need to calculate a transit
    # ephemeris.  First check for period and time of mid-transit:
    if (($p->{'pl_orbper'} eq '') or ($p->{'pl_tranmid'} eq '')) {
	if ($DEBUG) {
	    print STDERR "Skipping entry for planet $p->{'pl_name'}"
		. " - period or transit mid-point missing.\n";
	}
	next;
    }

    # Add a comment field to make note of any estimations or oddities
    # in the entry: 
    $p->{'comment'} = '';

    push @good_entries, $p;
}

my $n_good = scalar(@good_entries);
my $n_total = scalar(@csv_lines); 

if ($DEBUG) {
    print STDERR "Found $n_good usable entries out of $n_total total.\n";
}

# Header for the CSV file with the names of each field: 
my @header = ("name","RA","Dec","vmag","epoch","epoch_uncertainty",
	      "period","period_uncertainty",
	      "duration","comments","depth","priority");

# Output will be an array of array references; start with the header: 
my @output_lines = (\@header);

PLANETS:
foreach $p (@good_entries) {
    my ($period_err, $midpoint_err); 
    if (($p->{'pl_orbpererr1'} eq '') and
	($p->{'pl_orbpererr2'} eq '')) {
	print STDERR "No period err for $p->{'pl_name'}, check.\n" if $DEBUG; 
	# If errors are missing, just leave error field blank. 
	$period_err = ''; 
    } else {
	# Take the *max* of upper and lower period errs: 
	$period_err = max($p->{'pl_orbpererr1'},
			  -1*$p->{'pl_orbpererr2'}); 
    }

    # Ditto for midpoint uncertainty: 
    if (($p->{'pl_tranmiderr1'} eq '') and
	($p->{'pl_tranmiderr2'} eq '')) {
	$midpoint_err = '';
    } else {
	$midpoint_err = max($p->{'pl_tranmiderr1'},
			    -1*$p->{'pl_tranmiderr2'}); 
    }
    $p->{'period_err'} = $period_err;
    $p->{'midpoint_err'} = $midpoint_err;

    # Get V magnitude or an alternate:
    if ($p->{'sy_vmag'} ne '') {
	$V = sprintf("%0.3f", $p->{'sy_vmag'});
    } elsif ($p->{'sy_gaiamag'} ne '') {
	$V =  sprintf("%0.3f", $p->{'sy_gaiamag'});
	$p->{'comment'} .= " Mag is Gaia G. ";
	print STDERR "Using Gaia mag for $p->{'pl_name'}.\n" if $DEBUG;
    } else {
	$V = -99; 
    }

    # Some entries that have good periods are missing duration.  See
    # if we can fill that in. 

    if ($p->{'pl_trandur'} eq '') {
	my ($duration, $status, $comment) = estimate_duration($p);
	if ($status) {
	    $p->{'pl_trandur'} = $duration;
	    $p->{'comment'} .= $comment;
	} else {
	    # Could not get duration at all! 
	    if ($DEBUG) {
		print STDERR "### Could not get duration for $p->{'pl_name'}!\n";
	    }
	    next PLANETS;
	}
    }

    # Sometimes no depth is given - try to estimate depth from planet
    # and stellar radii:
    if ( $p->{'pl_trandep'} eq '' ) {
	if ($DEBUG) {
	    print STDERR "No depth given for $p->{'pl_name'}, estimating.\n";
	}

	# Give depth in ppt:
	if ($p->{'pl_ratror'} ne '') {
	    $depth_ppt = 1000 * $p->{'pl_ratror'}**2;
	} elsif (($p->{'pl_radj'} ne '') and ($p->{'st_rad'} ne '')) {
	    $depth_ppt = 1000 * ($p->{'pl_radj'}*R_jup/($p->{'st_rad'}*R_sun))**2;
	} else {
	    print STDERR "Could not estimate depth for $p->{'pl_name'}\n";
	    $depth_ppt = -99;
	}

    } else {
	# Convert depth to ppt.  Depth is given as percentage (parts
	# per hundred) in catalog: 
	$depth_ppt = 10 * $p->{'pl_trandep'};
    }

    if ($depth_ppt < 1) {
	$depth_ppt_string = sprintf('%0.2f', $depth_ppt);
    } else {
	$depth_ppt_string = sprintf('%0.1f', $depth_ppt);
    }

    $duration_hours = sprintf('%0.2f', $p->{'pl_trandur'});
    

    # Short term hack/fix until NExSci fixes a coordinate rounding
    # bug: 
    if ($p->{'rastr'} =~ /60.00s/) {
	$p->{'rastr'} =~ s/60.00s/59.99s/;
    }

    # RA and Dec strings use hms and dms, change to colons for those
    # in between, strip trailing 's': 
    $p->{'rastr'} =~ s/[hmd]/:/g;
    $p->{'rastr'} =~ s/s//;
    $p->{'decstr'} =~ s/[hmd]/:/g;
    $p->{'decstr'} =~ s/s//;
    
    my @line = (
	$p->{'pl_name'},
	$p->{'rastr'},
	$p->{'decstr'}, 
	$V,
	$p->{'pl_tranmid'}, 
	$p->{'midpoint_err'}, 
	$p->{'pl_orbper'}, 
	$p->{'period_err'}, 
	$duration_hours,
	$p->{'comment'}, 
	$depth_ppt_string,
	$p->{'rank'}, 
	);

    push(@output_lines, \@line);

}	

my $status = Text::CSV::csv(in => \@output_lines, out => *STDOUT); 


# --- End of main program, just subroutines below here. 

sub estimate_duration {

# Estimate transit duration using other orbit parameters. Assumes
# input orbital period is in days, but converts returned 
# duration to hours. 

# Still to be tweaked - was a block of code in main loop. 
# Check for 'next' or 'die' to be sure we return errors instead of
# bailing. 

    my ($duration, $status, $comment); 

    my ($p) = @_;

    # No duration given; try to estimate from other
    # parameters, using formula of equation 16 of Seager &
    # Mallen-Ornelas 2003

    my $a_over_r = '';
    # Check 'defined' first to avoid warnings about uninitialized
    # values: 
    if ((defined $p->{'pl_orbsmax'}) and ($p->{'pl_orbsmax'} ne '') and 
	(defined $p->{'mst_rad'}) and ($p->{'mst_rad'} ne '')) {
	$a_over_r = ($p->{'pl_orbsmax'} * AU) / ($p->{'st_rad'}
						  * R_sun); 
    } else {
	# Not quite the same for non-zero e, since this is defined
	# as "The distance between the planet and the star at
	# mid-transit divided by the stellar radius."  Should be
	# close in most cases. 
	$a_over_r = $p->{'pl_ratdor'};
    }

    my $rplanet_over_rstar = $p->{'pl_ratror'};
    # Even though the above field is defined, sometimes it's not
    # filled in even though r_planet and r_star are both given: 
    if ($rplanet_over_rstar eq '') {
	if ((defined $p->{'pl_rads'}) and ($p->{'pl_rads'} ne '') and 
	    (defined $p->{'mst_rad'}) and ($p->{'mst_rad'} ne '')) {
	    $rplanet_over_rstar = $p->{'pl_rads'} / $p->{'mst_rad'};
	}
    }

    # Get impact parameter if not already given: 
    if ($p->{'pl_imppar'} eq '') {
	if (($p->{'pl_orbincl'} ne '') and 
	    ($a_over_r ne '')) {
	    $p->{'pl_imppar'} = $a_over_r *
		abs(cos(deg2rad($p->{'pl_orbincl'})));
	}  else {
	    # No inclination, so punt and assume transit across
	    # the middle of the star so we can at least get
	    # ballpark duration:
	    $p->{'pl_imppar'} = 0;
	}
    }

    if (($p->{'pl_imppar'} eq '') 
	or ($a_over_r eq '') or ($a_over_r < 1)
	or ($rplanet_over_rstar eq '') 
	or ($rplanet_over_rstar > 1)) {
	# can't do the calculation; return
	$status = 0;
	$comment = '';
	undef $duration; 
	return ($duration, $status, $comment); 
    }

    
    my $sqrt_term = (1 + $rplanet_over_rstar)**2
	- $p->{'pl_imppar'}**2;
    if ($sqrt_term < 0) {
	if ($DEBUG) {
	    print STDERR "Skipping entry for planet $p->{'pl_name'}"
		. " - cannot calculate duration, sqrt term is negative.\n";
	    print STDERR "R planet over Rstar: $rplanet_over_rstar\n";
	    print STDERR "a over R: $a_over_r\n";
	    print STDERR "Impact parameter: $p->{'pl_imppar'}\n"; 
	    print STDERR $p, "\n\n";
	}
	# can't do the calculation; return
	$status = 0;
	$comment = '';
	undef $duration; 
	return ($duration, $status, $comment); 
    }
    # Calculate duration in hours, assuming period is in days: 
    $duration = (24 * $p->{'pl_orbper'} / ($a_over_r * pi))
	* sqrt($sqrt_term); 
    $comment = "Duration estimated. "; 
    $status = 1; 

    return ($duration, $status, $comment); 
}
