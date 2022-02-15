#!/usr/bin/perl

# Script to parse the CSV file of exoplanets from NASA's Exoplanet Archive.

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


# Script to parse the CSV file of exoplanets from exoplanets.org, in
# order to pull out transiting planets and output just selected fields
# in an easier-to-read format for calculating transit ephemerides.
# Attempts to calculate a transit duration if none is given in the file.

# For my use, I fetch the CSV file from exoplanets.org periodically
# via a cron job, and then run this script on it to generate my local
# plain-text target file for the transit-finding script.  My cron job
# looks something like this; the '-N' argument to wget causes the
# remote file to be fetched only if it is newer than the local copy. 

# cd /home/httpd/html/ ; \ 
# wget -N http://exoplanets.org/csv-files/exoplanets.csv  2>&1 ;  \
#  ./parse_exoplanets_csv.pl exoplanets.csv > transit_targets.txt 

# Initial creation, Eric Jensen, ejensen1@swarthmore.edu
# Updated 2016-11-17 to force UTF-8 encoding in opening CSV file, 
#                    and require coordinates for targets. 
# 2017-02-23   Also make sure output is UTF-8!
# 2019-05-08   Fix calculation of durations; also pull data from 
#           alternate file for sources with missing data. 
# 2019-08-26  Change to NASA Exoplanet Archive from exoplanets.org;
# also search through multiple ephemerides to find most accurate one. 
# 2019-10-11: Switch to CSV for the target file


use Text::CSV qw( csv );
use Getopt::Std;
use Math::Trig qw(deg2rad pi);
use List::Util qw(min max);
use DateTime;
use DateTime::Format::Epoch::JD;

use strict;
use warnings; 

use constant R_sun => 6.957E8;  # Rsun in meters per IAU
use constant AU => 149597870700;  # AU in meters per IAU

# Our target file is encoded as UTF-8, so make sure everything we
# write out is encoded in the same way: 
binmode(STDOUT, ":utf8");

# Unbuffered output, helps with tracking error messages: 
$| = 1;

# An alternate target file to pull data from in the event 
# that data here are incomplete: 
my $target_magnitude_file = 'exoplanet_archive_transits_full_mags.txt';

# Set the -d flag ("debug") for verbose output of (some) problems.

our ($opt_d, $DEBUG);

my $options = 'd';

getopts($options);

if ($opt_d) {
    $DEBUG = 1;
} else {
    $DEBUG = 0;
}


# Field separator for output file:
my $sep = " ,. ";


# For calculating uncertainty on transit times below, we need to know
# how far we are from the epoch when the ephemeris was defined, so get
# the current JD: 
my $this_jd = DateTime::Format::Epoch::JD->format_datetime(DateTime->now());

my ($p, $V, $comment, $name, $duration,
    $duration_hours, $depth_ppt, $depth_ppt_string, $prev_name, 
    $i);

# Slurp all the lines from the file so we can loop over them and group
# together entries for the same planet. 

my $datafile = $ARGV[0];

# Read the CSV file; return value is a reference to an array of
# hashes, so immediately dereference to get the array: 
my @csv_lines = @{ Text::CSV::csv(allow_whitespace => '1',
				  in => $datafile, 
				  encoding => "UTF8",
				  headers => "auto",
		                  )};

# In addition, read in the file with the magnitudes and some other
# params: 

my @mag_lines = @{ Text::CSV::csv(in => $target_magnitude_file, 
				   encoding => "UTF8",
				   headers => "auto",
		                 )}; 


# Now @mag_lines is a list of hash references. Use it to create a lookup hash,
# keyed by the name of the planet.  In this map function, we iterate
# over the list, and iteratively use the name entry to create a key to
# a hash, with the value containing the relevant line: 
my %default_pars = map { $_->{"pl_name"} => $_ } @mag_lines; 



# Make a first pass through the targets to save only those entries
# that have sufficient information for us to calculate an ephemeris;
# that makes the logic in the next loop cleaner. 

my @good_entries = ();


foreach $p (@csv_lines) {

    # Make sure it has the entries we need to calculate a transit
    # ephemeris.
    # First check for period and time of mid-transit: 
    if (($p->{'mpl_orbper'} eq '') or ($p->{'mpl_tranmid'} eq '')) {
	if ($DEBUG) {
	    print STDERR "Skipping entry for planet $p->{'mpl_name'}"
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

# Now we have the good entries in order.  First we make a list of
# consecutive ones for the same system, then of those, pick the one
# that gives the smallest transit-time uncertainty. 
 
my @p_list = ();

# $i is our counter variable for the loop, but note that it is
# incremented within the loop body to group together like-named
# entries. 
$i = 0;

# Header for the CSV file with the names of each field: 
my @header = ("name","RA","Dec","vmag","epoch","epoch_uncertainty",
	      "period","period_uncertainty",
	      "duration","comments","depth");

# Output will be an array of array references; start with the header: 
my @output_lines = (\@header);

PLANETS:
while ($i < $n_good) {

    # At the start of this loop, we are always starting fresh with a
    # new system.  Add our current entry, then see how many more to
    # add: 
    @p_list =();  # fresh list

    do {
	push @p_list, $good_entries[$i];
	$prev_name = $good_entries[$i]->{'mpl_name'};
	$i++; 
    } until ($i == $n_good) or ($prev_name ne
				$good_entries[$i]->{'mpl_name'});

    # Now we have the list of entries for the same system.  Find the
    # one with minimum uncertainty. 

    my $min_err = 1e20;  # Large value to start. 
    my $p_best = '';

    if (scalar(@p_list) == 1) {
	$p_best = $p_list[0];
	$p = $p_best;
	my ($period_err, $midpoint_err); 
	# If errors are missing, try to estimate from number of
	# decimal places listed: 
	if (($p->{'mpl_orbpererr1'} eq '') and
	    ($p->{'mpl_orbpererr2'} eq '')) {
	    $period_err = ''; 
	} else {
	    $period_err = max($p->{'mpl_orbpererr1'},
			      -1*$p->{'mpl_orbpererr2'}); 
	}

	if (($p->{'mpl_tranmiderr1'} eq '') and
	    ($p->{'mpl_tranmiderr2'} eq '')) {
	    $midpoint_err = '';
	} else {
	    $midpoint_err = max($p->{'mpl_tranmiderr1'},
				-1*$p->{'mpl_tranmiderr2'}); 
	}
	$p_best->{'period_err'} = $period_err;
	$p_best->{'midpoint_err'} = $midpoint_err;

    } else {
	foreach $p (@p_list) {
	    # Take period error as max of upper and lower entries;
	    # Second error entry is negative, so multiply by -1.
	    next if (($p->{'mpl_orbpererr1'} eq '') or
		     ($p->{'mpl_orbpererr2'} eq '') or
		     ($p->{'mpl_tranmiderr1'} eq '') or
		     ($p->{'mpl_tranmiderr2'} eq ''));
	    my $period_err = max($p->{'mpl_orbpererr1'},
				 -1*$p->{'mpl_orbpererr2'}); 
	    my $midpoint_err = max($p->{'mpl_tranmiderr1'},
				   -1*$p->{'mpl_tranmiderr2'}); 
	    next if (($period_err == 0) or ($midpoint_err == 0));
	    # Otherwise, we have the fields we need to find the
	    # uncertainty: 
	    my $n_periods = abs($this_jd -
				$p->{'mpl_tranmid'})/$p->{'mpl_orbper'}; 
	    my $transit_unc = sqrt($midpoint_err**2 +
				   ($n_periods*$period_err)**2); 
	    if ($transit_unc < $min_err) {
		$min_err = $transit_unc;
		$p_best = $p;
		# Since we've calculated these anyway, save the errors
		# for printing later: 
		$p_best->{'period_err'} = $period_err;
		$p_best->{'midpoint_err'} = $midpoint_err;

	    }
	}
    }
    if ($p_best eq '') {
	print "More than one entry for $p_list[0]->{'mpl_name'}" . 
	    " but none have uncertainty fields, cannot choose.\n"; 
	exit;
    }

    # Now we have the best values for each entry; just a bit more
    # processing and we can print them out. 

    # Some entries that have good periods are missing duration.  See
    # if we can fill that in. 


    # Get the "default parameters" entry for this system: 
    my $pars = $default_pars{$p_best->{'mpl_name'}};

    # Get magnitude from default params: 
    if ($pars->{'st_optmag'} ne '') {
	$V = $pars->{'st_optmag'};
	if ($pars->{'st_optband'} =~ m/Kepler/) {
	    $p_best->{'comment'} .= " Mag is Kepler band. ";
	}
    } elsif ($pars->{'gaia_gmag'} ne '') {
	$V = $pars->{'gaia_gmag'};
	$p_best->{'comment'} .= " Mag is Gaia G. ";
    } else {
	$V = -99; 
    }

    
    # Also use depth from that file if we don't already have it: 
    if ($p_best->{'mpl_trandep'} eq '') { 
	if ($pars->{'pl_trandep'} ne '') {	
	    $p_best->{'mpl_trandep'} = $pars->{'pl_trandep'};
	} elsif ($pars->{'pl_ratror'} ne '') {	
	    # Use tabulated planet-star radius ratio, convert to percent: 
	    $p_best->{'mpl_trandep'} = 100 * ($pars->{'pl_ratror'})**2;
	} elsif (($pars->{'pl_rads'} ne '') and ($pars->{'st_rad'} ne '')) {	
	    # Calculate and use planet-star radius ratio, convert to percent: 
	    $p_best->{'mpl_trandep'} = 100 * ($pars->{'pl_rads'}/$pars->{'st_rad'})**2;
	}      
    }

    if ($p_best->{'mpl_trandur'} eq '') {
	# First try the 'default params' file: 
	if  ($pars->{'pl_trandur'} ne '') {	
	    $p_best->{'mpl_trandur'} = $pars->{'pl_trandur'};
	} else {
	    # Didn't find it there, loop over other entries to see if
	    # we can find one with a duration. 
	    my $dur_found = 0;
	    my @planet_list = @p_list;
	    while ((not $dur_found) and (scalar(@planet_list) > 0)) {
		$p = pop @planet_list;
		if ($p->{'mpl_trandur'} ne '') {
		    $p_best->{'mpl_trandur'} = $p->{'mpl_trandur'};
		    $dur_found = 1;
		}
	    }
	    if (not $dur_found) {
		# Try again, now with estimating duration from other
		# parameters. 
		@planet_list = @p_list;
		while ((not $dur_found) and (scalar(@planet_list) > 0)) {
		    $p = pop @planet_list;
		    my ($duration, $status, $comment) = estimate_duration($p);
		    if ($status) {
			$p_best->{'mpl_trandur'} = $duration;
			$p_best->{'comment'} .= $comment;
			$dur_found = 1;
		    }
		}
		if (not $dur_found) {
		    # Could not get duration at all! 
		    if ($DEBUG) {
			print STDERR "### Could not get duration for $p_best->{'mpl_name'}!\n";
		    }
		    next PLANETS;
		}

	    }
	}
    }

    # Just to make what's below less verbose: 
    $p = $p_best;


    # Sometimes no depth is given - try to estimate depth from planet
    # and stellar radii:
    if ( $p->{'mpl_trandep'} eq '' ) {
	# 
	if ($DEBUG) {
	    print STDERR "No depth given for $p->{'mpl_name'}.\n";
	    print STDERR "Estimating depth for $p->{'mpl_name'}\n$p\n";
	}

	# Give depth in ppt:
	if ($p->{'mpl_ratror'} ne '') {
	    $depth_ppt = 1000 * $p->{'mpl_ratror'}**2;
	} elsif (($p->{'mpl_rads'} ne '') and ($p->{'mst_rad'} ne '')) {
	    $depth_ppt = 1000 * ($p->{'mpl_rads'}/$p->{'mst_rad'})**2;
	} else {
	    print STDERR "Could not estimate depth for $p->{'mpl_name'}\n";
	    $depth_ppt = -99;
	}

    } else {
	# Convert depth to ppt.  Depth is given as percentage (parts
	# per hundred) in catalog: 
	$depth_ppt = 10 * $p->{'mpl_trandep'};
    }

    # Only write out the +/- separator in cases where the
    # error estimate actually exists!  This applies both to
    # transit time and period uncertainties.
    my ($period_error_sep, $transit_error_sep);
    if ($p->{'period_err'} =~ /^\s*$/) {
	$period_error_sep = "";
    } else {
	$period_error_sep = " +/- ";
    }
    if ($p->{'midpoint_err'} =~ /^\s*$/) {
	$transit_error_sep = "";
    } else {
	$transit_error_sep = " +/- ";
    }

    if ($depth_ppt < 1) {
	$depth_ppt_string = sprintf('%0.2f', $depth_ppt);
    } else {
	$depth_ppt_string = sprintf('%0.1f', $depth_ppt);
    }

    $duration_hours = sprintf('%0.2f', 24. * $p->{'mpl_trandur'});
    
    # RA and Dec strings use hms and dms, change to colons for those
    # in between, strip trailing 's': 
    $p->{'ra_str'} =~ s/[hmd]/:/g;
    $p->{'ra_str'} =~ s/s//;
    $p->{'dec_str'} =~ s/[hmd]/:/g;
    $p->{'dec_str'} =~ s/s//;
    
    # # Print the final output line:
    # print $p->{'mpl_name'} . $sep . $p->{'ra_str'} .
    # 	$sep . $p->{'dec_str'} . $sep . $V .
    # 	$sep . $p->{'mpl_tranmid'} . $transit_error_sep .
    # 	$p->{'midpoint_err'} . $sep . $p->{'mpl_orbper'} . $period_error_sep .
    # 	$p->{'period_err'} . $sep . $duration_hours . $sep . 
    # 	$p->{'comment'} . $sep . $priority . $sep . 
    # 	$depth_ppt_string . "\n";

    my @line = (
	$p->{'mpl_name'},
	$p->{'ra_str'},
	$p->{'dec_str'}, 
	$V,
	$p->{'mpl_tranmid'}, 
	$p->{'midpoint_err'}, 
	$p->{'mpl_orbper'}, 
	$p->{'period_err'}, 
	$duration_hours,
	$p->{'comment'}, 
	$depth_ppt_string,
	);

    push(@output_lines, \@line);

}	

my $status = Text::CSV::csv(in => \@output_lines, out => *STDOUT); 


# --- End of main program, just subroutines below here. 


# Note that I wrote this but then decided not to use it; it ends up
# picking some entries from the Exoplanet Archive that list parameters
# to very high apparent precision but don't quote uncertainties.  We
# don't want to privilege those over ones that actually give
# uncertainties.  Leaving it here in case it's useful at some point. 

sub estimate_error {
    my ($n) = @_;

    # Find the number of digits after the decimal place.
    # First we match that part of the string: 
    $n =~ m/\.(\d+)$/; 
    # Then find number of characters in the matched string: 
    my $count = length($1); 

    # Trap unexpected patterns: 
    if ($count ==0) {
	die "Got an unexpected string in estimate_error: $n";
    }
    # Error is assumed to be in that decimal place:
    my $err = 5 * 10**(-1 * $count); 
    return $err;
}

sub estimate_duration {

# Still to be tweaked - was a block of code in main loop. 
# Check for 'next' or 'die' to be sure we return errors instead of
# bailing. 

    my ($duration, $status, $comment); 

    my ($p) = @_;

    # No duration given; try to estimate from other
    # parameters, using formula of equation 16 of Seager &
    # Mallen-Ornelas 2003

    my $a_over_r = '';
    if (($p->{'mpl_orbsmax'} ne '') and 
	($p->{'mst_rad'} ne '')) {
	$a_over_r = ($p->{'mpl_orbsmax'} * AU) / ($p->{'mst_rad'}
						  * R_sun); 
    } else {
	# Not quite the same for non-zero e, since this is defined
	# as "The distance between the planet and the star at
	# mid-transit divided by the stellar radius."  Should be
	# close in most cases. 
	$a_over_r = $p->{'mpl_ratdor'};
    }

    my $rplanet_over_rstar = $p->{'mpl_ratror'};
    # Even though the above field is defined, sometimes it's not
    # filled in even though r_planet and r_star are both given: 
    if ($rplanet_over_rstar eq '') {
	if (($p->{'mpl_rads'} ne '') and 
	    ($p->{'mst_rad'} ne '')) {
	    $rplanet_over_rstar = $p->{'mpl_rads'} / $p->{'mst_rad'};
	}
    }

    # Get impact parameter if not already given: 
    if ($p->{'mpl_imppar'} eq '') {
	if (($p->{'mpl_orbincl'} ne '') and 
	    ($a_over_r ne '')) {
	    $p->{'mpl_imppar'} = $a_over_r *
		abs(cos(deg2rad($p->{'mpl_orbincl'})));
	}  else {
	    # No inclination, so punt and assume transit across
	    # the middle of the star so we can at least get
	    # ballpark duration:
	    $p->{'mpl_imppar'} = 0;
	}
    }

    if (($p->{'mpl_imppar'} eq '') 
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
	- $p->{'mpl_imppar'}**2;
    if ($sqrt_term < 0) {
	if ($DEBUG) {
	    print STDERR "Skipping entry for planet $p->{'mpl_name'}"
		. " - cannot calculate duration, sqrt term is negative.\n";
	    print STDERR "R planet over Rstar: $rplanet_over_rstar\n";
	    print STDERR "a over R: $a_over_r\n";
	    print STDERR "Impact parameter: $p->{'mpl_imppar'}\n"; 
	    print STDERR $p, "\n\n";
	}
	# can't do the calculation; return
	$status = 0;
	$comment = '';
	undef $duration; 
	return ($duration, $status, $comment); 
    }
    $duration = ($p->{'mpl_orbper'} / ($a_over_r * pi))
	* sqrt($sqrt_term); 
    $comment = "Duration estimated. "; 
    $status = 1; 

    return ($duration, $status, $comment); 
}
