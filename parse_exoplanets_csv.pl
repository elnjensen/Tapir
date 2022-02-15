#!/usr/bin/perl

# Script to parse the CSV file of exoplanets from exoplanets.org.

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

use Tie::Handle::CSV;
use Getopt::Std;
use strict;
use warnings; 

# Set the -d flag ("debug") for verbose output of (some) problems.

our ($opt_d, $DEBUG);

my $options = 'd';

getopts($options);

if ($opt_d) {
    $DEBUG = 1;
} else {
    $DEBUG = 0;
}

my $datafile = $ARGV[0];
my $fh = Tie::Handle::CSV->new(csv_parser =>
			       Text::CSV_XS->new({allow_whitespace => '1'}),
			       file => $datafile, 
			       open_mode => "< :encoding(UTF8)",
			       header => 1,
			       );


# Field separator for output file:
my $sep = " ,. ";


my ($csv_line, $V, $comment, $priority, $name, $duration,
    $duration_hours, $depth_mmag, $depth_mmag_string);

 PLANETS: 
    while ($csv_line = <$fh>) {
	# Only consider transiting objects:
	if ($csv_line->{'TRANSIT'} eq '1') {
	    $name =  $csv_line->{'NAME'};
	    if ($DEBUG) {
		print STDERR "Doing planet $name...\n"
	    }
	    
	    $comment = '';

	    # No coords are listed for most of the KOI objects;
	    # don't include objects in the output if they don't have
	    # coords:
	    if ( ($csv_line->{'RA_STRING'} =~ /^\s*$/) or
		 ($csv_line->{'DEC_STRING'} =~ /^\s*$/) ) {

		if ($DEBUG) {
		    print STDERR "No coords available for $name, skipping.\n"
		}
	    
		next PLANETS;
	    }


	    # Priority not really used now - set all to the same.
	    $priority = 5;

	    # Get the V mag, or use Kepler mag if V not present:
	    if ($csv_line->{'V'} ne '') {
		$V = sprintf("%0.2f",  $csv_line->{'V'});
	    } elsif ($csv_line->{'KP'} ne '') {
		$V = sprintf("%0.2f",  $csv_line->{'KP'});
	    } else {
		$V = -99; 
	    }

	    # If the time of transit is not given, we don't 
	    # include this object, since we wouldn't be able
	    # to calculate when it transits:
	    if ($csv_line->{'TT'} eq '') {
		next PLANETS;
	    }

	    # Get the duration; called "T14" in the CSV file because
	    # it is from 1st to 4th contact.
	    $duration = $csv_line->{'T14'};
	    if ($duration eq '') {
		# No duration given; try to estimate from other
	        # parameters, using formula of equation 16 of Seager &
	        # Mallen-Ornelas 2003
		if (($csv_line->{'B'} eq '') 
		    or ($csv_line->{'AR'} eq '') 
		    or ($csv_line->{'DEPTH'} eq '') 
		    or ($csv_line->{'PER'} eq '')) {
		    # can't do the calculation; skip this one:
		    if ($DEBUG) {
			print STDERR "Skipping planet $name"
			    . " - cannot calculate duration.\n"
			}
		    next PLANETS;
		}
		
		$duration = ($csv_line->{'PER'} / ($csv_line->{'AR'}
						   * 3.1415926536)) 
		    * sqrt((1 + sqrt($csv_line->{'DEPTH'}))^2
			   - $csv_line->{'B'}^2);
		$comment .= " Transit duration estimated.";
	    }
	    # Sometimes no depth is given - put a flag in for that:
	    if ( $csv_line->{'DEPTH'} eq '' ) {
		if ($DEBUG) {
		    print STDERR "No depth given for $name.\n"
		    }
		$depth_mmag = -99;
	    } else {
		# Convert depth to millimags:
		$depth_mmag = 1000 * 2.5 
		    * log(1 + $csv_line->{'DEPTH'})/log(10.);
	    }

	    # Only write out the +/- separator in cases where the
	    # error estimate actually exists!  This applies both to
	    # transit time and period uncertainties.
	    my ($period_error_sep, $transit_error_sep);
	    if ($csv_line->{'UPER'} =~ /^\s*$/) {
		$period_error_sep = "";
	    } else {
		$period_error_sep = " +/- ";
	    }
	    if ($csv_line->{'UTT'} =~ /^\s*$/) {
		$transit_error_sep = "";
	    } else {
		$transit_error_sep = " +/- ";
	    }
	    $depth_mmag_string = sprintf('%0.1f', $depth_mmag);
	    $duration_hours = sprintf('%0.2f', 24. * $duration);

	    # The RA string has some spurious leading plus signs on
	    # some entries, remove: 
	    $csv_line->{'RA_STRING'} =~ s/^\+//;

	    # Print the final output line:
	    print $name . $sep . $csv_line->{'RA_STRING'}
	    . $sep . $csv_line->{'DEC_STRING'} . $sep . $V
		. $sep . $csv_line->{'TT'} . $transit_error_sep 
		. $csv_line->{'UTT'}
	    . $sep . $csv_line->{'PER'} . $period_error_sep 
		. $csv_line->{'UPER'}
	    . $sep . $duration_hours . $sep . $comment . $sep . $priority
		. $sep . $depth_mmag_string
		. "\n";
	}
    }

close $fh;
