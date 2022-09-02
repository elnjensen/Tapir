#!/usr/bin/perl

# Code to read in a file of targets for eclipse/transit observations,
# find upcoming events, sort them according to date, and print the
# results, either as HTML, or in CSV format to be read
# into Google Calendar or another calendar program.  Input parameters
# provided by transits.cgi, which calls this script. 


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


# These next settings are turned on to have the strictest possible
# error checking and warnings, to help find obscure bugs.  If they are
# causing problems, any of them can be commented out.

# Require declaration of all variables:
use strict;
# Warn about suspect constructions, uninitalized variables, etc.
# Equivalent to the -w command-line switch.
use warnings;
# Cause fatal errors to print to browser rather than (in addition to?)
# webserver log file:
use CGI::Carp qw(fatalsToBrowser);

# Some observatory names have non-ASCII characters: 
use utf8;

use Astro::Coords;
use Astro::Telescope;
# Constants for degrees to radians and vice versa, and angular
# separation routine: 
use Astro::PAL qw( DD2R DR2D palDsep );

# Note - code at the end of this file adds a couple of new methods to
# DateTime and DateTime::Duration that aren't in the core module. 
use DateTime;
use DateTime::Duration;

use DateTime::Set;
use DateTime::Format::Epoch::JD;

use HTML::Template::Expr;
use CGI qw/ -utf8 /;
use CGI::Cookie;
use URI::Escape;
use HTML::Entities;
use Switch;
use List::Util qw (min max); 
use Text::CSV qw( csv );
use Parallel::ForkManager;

# We should be getting UTF-8 data from our target list, so make sure
# we output in the same format. It's not clear whether this makes a
# difference vs. just setting the character set in the HTTP header,
# but it doesn't hurt. 
binmode(STDOUT, ":utf8");

############# Variables for local configuration ##############

# Put things here that are likely to need to be changed in order to
# use this code for a different purpose:

# Maximum number of events to output; set to avoid searches 
# that would tie up server for a long time: 
my $max_eclipses_to_print = 1000;

# Template for the HTML output page:
my $template_filename = 'target_table.tmpl';
# A template for CSV output; this may supersede the above setting
# based on user input below.
my $csv_template_filename = 'csv_text.tmpl';
# File containing target info; include path as needed.
# This is the default value, subject to change below based on other
# flags. 
my $target_file = 'transit_targets.csv'; 

# Parameters for setting cookies stored in the user's
# browser to remember input parameters:
my $cookie_domain = '.astro.swarthmore.edu';
my $cookie_path = '';
my $cookie_expires = '+1M';

# Contact info provided in the fatal_error subroutine:
my $script_contact_person = 'Eric Jensen, ejensen1@swarthmore.edu';

# Look at the subroutine 'parse_target_line' toward the end of the
# file to see the default assumed format for the input target file,
# and to change how that line is parsed into variables if necessary. 

# You should also edit the subroutines 'finding_chart_page' and
# 'target_info_page' at the end of this file to either (a) return 
# valid URLs for your targets or (b) return undef.


######## End variables for local configuration ###############


# Switch to turn on some very rudimentary debugging output:
my $debug = 0;

# Very rudimentary timing of the script:
my $script_start_time = time;

# Define the CGI object that will both allow us to fetch the input
# variables to the script and also to print the HTML output:
my $q = CGI->new();

# First, get the necessary input parameters for calculating the
# transit visibility; these come from a separate page that passes them
# into this script.

# Observatory latitude and longitude; give in degrees, with positive
# for north latitude and east longitude; use negative for south
# latitude or west longitude.

# There are two different possible ways that this info can be
# specified.  For the pre-defined observatories, it is passed as a
# semicolon-separated string that has latitude, longitude, and
# timezone all in one field.  Otherwise, those three quantities can be
# specified separately in individual fields. 

my $observatory_string = $q->param("observatory_string");
my $flag_for_manual_entry = 'Specified_Lat_Long';

if ((not defined $observatory_string) or ($observatory_string eq "")) {
    $observatory_string = $flag_for_manual_entry;
}

my ($observatory_latitude, $observatory_longitude,
    $temporary_timezone, $observatory_timezone, 
    $observatory_name, $observatory_shortname); 

# Check to see if the entered string contains the text that indicates
# we should ignore it and use individual fields instead, or if we
# should try to parse it.

if ($observatory_string !~ /$flag_for_manual_entry/) {
    ($observatory_latitude, $observatory_longitude,
     $temporary_timezone, $observatory_name, $observatory_shortname) 
	= split(/;/, $observatory_string);
} else {
    $observatory_longitude = $q->param("observatory_longitude");
    $observatory_latitude = $q->param("observatory_latitude");
    $temporary_timezone = $q->param("timezone");
    $observatory_name = "Other Site";
    $observatory_shortname = "Other Site";
}

# The timezone string gets used in an 'eval' statement by
# DateTime::Timezone at some point, so we need to untaint it here by
# checking it against a regular expression.  We have to allow a '/'
# here, even though it is a path separator, because it is a legitimate
# part of some timezone names. 
if ($temporary_timezone =~ m%^\s*([_/+\-0-9A-Za-z]+)$%) {
    $observatory_timezone = encode_entities($1);
} else {
    my $err_timezone = encode_entities($temporary_timezone);
    die "Unrecognized timezone: [$err_timezone]\n";
}

# Make sure latitude and longitude only have valid chars: 
$observatory_longitude = num_only($observatory_longitude);
$observatory_latitude = num_only($observatory_latitude);
# And likewise for names: 
$observatory_name = encode_entities($observatory_name);
$observatory_shortname = encode_entities($observatory_shortname);

# Check to see if they set the parameter to use UTC no matter what.
# We keep $observatory_timezone set to the local timezone, but 
# use this boolean to check what to use for output for main display. 
my $use_utc = num_only($q->param("use_utc"));
if ((not defined $use_utc) or ($use_utc =~ /^\s*$/)) {
    $use_utc = 0;
}

# Desired time windows for data:

# Start date:
my $start_date_string = encode_entities($q->param("start_date"));
if ((not defined $start_date_string) or ($start_date_string =~ /^\s*$/)) {
    $start_date_string = 'today';
}

# Days in the future to print (including start date):
my $days_to_print = num_only($q->param("days_to_print"));
if ((not defined $days_to_print) or ($days_to_print =~ /^\s*$/)) {
    $days_to_print = 1;
}

# Days in the past (based from start date) to print:
my $days_in_past = num_only($q->param("days_in_past"));

# If they didn't specify a backward-looking window, then only show
# future eclipses:
if ((not defined $days_in_past) or ($days_in_past =~ /^\s*$/)) {
  $days_in_past = 0;
}

# Minimum start/end elevation to show; default to 0:
my $minimum_start_elevation = num_only($q->param("minimum_start_elevation"));
if ((not defined $minimum_start_elevation) 
    or ($minimum_start_elevation =~ /^\s*$/)) {
  $minimum_start_elevation = 0;
}

my $minimum_end_elevation = num_only($q->param("minimum_end_elevation"));
if ((not defined $minimum_end_elevation) 
    or ($minimum_end_elevation =~ /^\s*$/)) {
  $minimum_end_elevation = 0;
}

# Min/max hour angle to show; default to +/- 12H:
my $minimum_ha = num_only($q->param("minimum_ha"));
if ((not defined $minimum_ha) 
    or ($minimum_ha =~ /^\s*$/)) {
  $minimum_ha = -12;
}

my $maximum_ha = num_only($q->param("maximum_ha"));
if ((not defined $maximum_ha) 
    or ($maximum_ha =~ /^\s*$/)) {
  $maximum_ha = 12;
}

my $baseline_hrs = num_only($q->param("baseline_hrs"));
if ((not defined $baseline_hrs) 
    or ($baseline_hrs =~ /^\s*$/)) {
  $baseline_hrs = 0;
}

my $show_unc = num_only($q->param("show_unc"));
if ((not defined $show_unc) 
    or ($show_unc =~ /^\s*$/)) {
  $show_unc = 0;
}


# Fall back on 'or' behavior if there is it isn't defined,
# or if there is anything other that "and" or "or" in that flag: 
my $and_vs_or = lc($q->param("and_vs_or"));
if ((not defined $and_vs_or) 
    or ($and_vs_or eq "") or ($and_vs_or !~ /^(and|or)$/)) {
  $and_vs_or = "or";
}


# Special flag for observing from space; no elevation or day/night
# constraints on transit visibility:
my $observing_from_space = num_only($q->param("space"));
if ((not defined $observing_from_space) 
    or ($observing_from_space eq "")) {
  $observing_from_space = 0;
}



# Minimum priority to show; default to zero:
my $minimum_priority = num_only($q->param("minimum_priority"));
if ((not defined $minimum_priority) or ($minimum_priority eq "")) {
  $minimum_priority = 0;
}

# Minimum depth (in ppt) to show; default to zero:
my $minimum_depth = num_only($q->param("minimum_depth"));
if ((not defined $minimum_depth) or ($minimum_depth =~ /^\s*$/)) {
  $minimum_depth = 0;
}

# Maximum (faintest) V mag to show:
my $maximum_V_mag = num_only($q->param("maximum_V_mag"));
if ((not defined $maximum_V_mag) or ($maximum_V_mag =~ /^\s*$/)) {
  $maximum_V_mag = 30;
}

# Maximum airmass for airmass plots:
my $max_airmass = num_only($q->param("max_airmass"));
if ((not defined $max_airmass) or ($max_airmass =~ /^\s*$/)) {
  $max_airmass = 2.4;
}

# Target name string to match (can be a regex):
my $target_string = encode_entities($q->param("target_string"));
if (not defined $target_string) {
    $target_string = '';
} else {
    # Eliminate the most obvious vulnerability here:
    $target_string =~ s/script//ig;
    # Strip leading and trailing whitespace on this string:
    $target_string =~ s/^\s*(\S+)\s*$/$1/;
}

# Check to see if we are doing just a single object with manual
# ephemeris entry.  If this is set to 1, it means that we 
# will not read the target file, but will instead take the
# entered ephemeris for a single object and just use that.
my $single_object = $q->param("single_object");
if ((not defined $single_object) or ($single_object eq "")) {
    $single_object = 0;
}


# The 'single_object' flag is overloaded to possibly indicate
# alternate target lists: 
my $tess = 0;
my $exowatch = 0;

# Flag for doing TOIs instead of known planets: 
if ($single_object == 2) {
    $target_file = 'toi_targets.csv';
#    $template_filename = 'target_table.tmpl';  # may change this
    $tess = 1;
} elsif ($single_object == 3) {
    $target_file = 'exoplanet_watch_targets.csv';
    $template_filename = 'target_table_exowatch.tmpl'; 
    $exowatch = 1;
}

# Whether to show the ephemeris data:
my $show_ephemeris = $q->param("show_ephemeris");

# How to define twilight (given value is altitude of Sun at division
# between day and night, e.g. -12 for nautical twilight).
my $twilight = $q->param("twilight");
if ((not defined $twilight) or ($twilight =~ /^\s*$/)) {
  $twilight = -12;
}

# Desired orbital phase to calculate and plot.  Zero is transit. 
my $phase = $q->param("phase");
if ((not defined $phase) or ($phase =~ /^\s*$/)) {
  $phase = 0;
}

my $par_ref;
# If some parameters are entered with a comma instead of decimal point
# (different localization), substitute so the number is handled
# correctly:
foreach $par_ref (\$observatory_latitude, \$observatory_longitude,
		  \$twilight, \$max_airmass, \$maximum_V_mag,
		  \$minimum_start_elevation, \$minimum_end_elevation,
		  \$minimum_ha, \$maximum_ha, \$days_to_print,
		  \$days_in_past, \$phase, \$minimum_depth,
		  \$minimum_priority) {
    if ($$par_ref =~ /\d,\d/) {
	$$par_ref =~ s/,/\./;
    }
}


# Set up the value in radians of this angle (which is what the
# calculations actually require, as well as a label to use for the
# output:
my ($twilight_rad, $twilight_label);

switch ($twilight) {
    case -1   {$twilight_rad = Astro::Coords::SUN_RISE_SET;
	       $twilight_label = "Sunrise/sunset"; }
    case -6   {$twilight_rad = Astro::Coords::CIVIL_TWILIGHT;
	       $twilight_label = "Civil twilight"; }
    case -12  {$twilight_rad = Astro::Coords::NAUT_TWILIGHT;
	       $twilight_label = "Nautical twilight"; }
    case -18  {$twilight_rad = Astro::Coords::AST_TWILIGHT;
	       $twilight_label = "Astronomical twilight"; }
    # Interpret other values as elevation in degrees:
    else      {$twilight_rad = DD2R * $twilight;
	       $twilight_label = sprintf("Sun elev. %0.1f&deg;", $twilight); 
	       # Make the minus sign look a little nicer:
	       $twilight_label =~ s/-(\d)/&ndash;$1/; }
    }

# Whether the output will be printed as an HTML table; if this
# parameter is not set, then the output is printed in a
# comma-delimited form suitable for import into a calendar program,
# e.g. Google Calendar.
my $print_html =  $q->param("print_html");
# If they don't pass the parameter at all, print HTML rather than CSV:
if (not defined $print_html) {
    $print_html = 1;
}

if ($print_html == 2) {
    # Signal for raw CSV output; change the template:
    $template_filename = $csv_template_filename;
}

# As long as the user allows it, we set cookies for many of the input
# parameters; that way they are filled in with useful default values
# the next time the user visits the input form.  (For example, the
# latitude/longitude and/or observatory are remembered across sessions.) 


my $observatory_cookie = CGI::Cookie->
    new(-name    =>  'observatory_string',
	-value   =>  "$observatory_string",
	-expires =>  $cookie_expires,
	-domain  =>  $cookie_domain,
	-path    =>  $cookie_path,
	);

my $utc_cookie = CGI::Cookie->
    new(-name    =>  'Use_UTC',
	-value   =>  "$use_utc",
	-expires =>  $cookie_expires,
	-domain  =>  $cookie_domain,
	-path    =>  $cookie_path,
	);

my $unc_cookie = CGI::Cookie->
    new(-name    =>  'Show_uncertainty',
	-value   =>  "$show_unc",
	-expires =>  $cookie_expires,
	-domain  =>  $cookie_domain,
	-path    =>  $cookie_path,
	);

my $and_cookie = CGI::Cookie->
    new(-name    =>  'Use_AND',
	-value   =>  "$and_vs_or",
	-expires =>  $cookie_expires,
	-domain  =>  $cookie_domain,
	-path    =>  $cookie_path,
	);

my $latitude_cookie = CGI::Cookie->
  new(-name    =>  'observatory_latitude',
      -value   =>  "$observatory_latitude",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $longitude_cookie = CGI::Cookie->
  new(-name    =>  'observatory_longitude',
      -value   =>  "$observatory_longitude",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $timezone_cookie = CGI::Cookie->
  new(-name    =>  'observatory_timezone',
      -value   =>  "$observatory_timezone",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $days_cookie = CGI::Cookie->
  new(-name    =>  'days_to_print',
      -value   =>  "$days_to_print",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $days_in_past_cookie = CGI::Cookie->
  new(-name    =>  'days_in_past',
      -value   =>  "$days_in_past",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $minimum_start_elevation_cookie = CGI::Cookie->
  new(-name => 'minimum_start_elevation',
      -value   =>  "$minimum_start_elevation",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $minimum_end_elevation_cookie = CGI::Cookie->
  new(-name => 'minimum_end_elevation',
      -value   =>  "$minimum_end_elevation",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $minimum_ha_cookie = CGI::Cookie->
  new(-name => 'minimum_ha',
      -value   =>  "$minimum_ha",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $maximum_ha_cookie = CGI::Cookie->
  new(-name => 'maximum_ha',
      -value   =>  "$maximum_ha",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );


my $baseline_hrs_cookie = CGI::Cookie->
  new(-name => 'baseline_hrs',
      -value   =>  "$baseline_hrs",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );


my $minimum_priority_cookie = CGI::Cookie->
  new(-name    =>  'minimum_priority',
      -value   =>  "$minimum_priority",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $minimum_depth_cookie = CGI::Cookie->
  new(-name    =>  'minimum_depth',
      -value   =>  "$minimum_depth",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $twilight_cookie = CGI::Cookie->
  new(-name    =>  'twilight',
      -value   =>  "$twilight",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $max_airmass_cookie = CGI::Cookie->
  new(-name    =>  'max_airmass',
      -value   =>  "$max_airmass",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

# Only store the V mag value if it's constraining, otherwise blank:
my $maximum_Vmag_cookie = CGI::Cookie->
  new(-name    =>  'maximum_V_mag',
      -value   =>  $maximum_V_mag < 30 ? "$maximum_V_mag" : "",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

# Now set up objects that will let us calculate the times of sunrise
# and sunset, necessary for determining observability.

my $sun = new Astro::Coords(planet => "sun");
my $moon = new Astro::Coords(planet => "moon");

# Associate the observatory coordinates with this object by defining a
# telescope object for our coordinates. The library requires latitude
# and longitude in radians; the constant DD2R (decimal degrees to
# radians) is defined by Astro::PAL.  We specify an altitude of 0,
# since we need to say something; presumably this could be specified
# on input if we wanted to be even more precise about rise and set
# times.

my $telescope = new Astro::Telescope(Name => "MyObservatory", 
				  Long => $observatory_longitude*DD2R,
				  Lat => $observatory_latitude*DD2R,
				  Alt => 0,
				 );
$sun->telescope($telescope);
$moon->telescope($telescope);


# Calculate the set of sunrise and sunset times that we will use later
# for testing transit observability.  We make a list of these times
# here, so that we can pass them in to the subroutine and re-use them
# for each subsequent target.

# To do this, we need to find the date around which we are basing the
# calculation.  

# If they specify 'today', we just do 24 hours from the present time.
# But if they pick another date, we want to do noon to noon *in the
# timezone of the observatory in question*. 

my $base_date;
if ($start_date_string =~ /^\s*today\s*$/i) {
    $base_date = DateTime->now( time_zone => 'UTC' );
} else {
    # Parse the date out of the date string with a regular expression;
    # allow one-digit days and months in case they leave off the
    # leading zero, but require four-digit years:
    $start_date_string =~ /(\d{1,2})-(\d{1,2})-(\d{4})/;
    my ($month,$day,$year) = ($1,$2,$3);
    if ( (not defined $1) or (not defined $2) or (not defined $3)
	 or ($month < 1) or ($month > 12) or ($day < 1) 
	 or ($day > 31) or ($year <= 0)) {
	# Give them a hint if maybe they used European-style
	# DD-MM-YYYY format:
	my $hint = '';
	if ($month > 12) {
	    $hint = "Maybe you listed days before months?";
	} 
	die "Could not parse date [$start_date_string]; " 
	    . "must be 'today' or in MM-DD-YYYY format. $hint";
    }
    # Start at noon, local time, on requested day:
    $base_date = DateTime->new(
			 year => $year,
			 month => $month,
			 day => $day,
			 hour => '12',
			 time_zone => $observatory_timezone,
			 );
    $base_date->set_time_zone('UTC');
}

# Get new objects for the start and end by cloning and then adding the
# necessary offset.  The clone-> operation is necessary because
# otherwise we've just created a new reference to a single object and
# any changes would change the original, too.  For specifying the
# offsets, we need to take two things into account.  First, we want to
# be sure that we have a large enough window for calculating
# sunrises/sunsets that we really reach all the dates we'll need
# (i.e., we need to find the *next* sunset after our last possible
# eclipse, even if that might nominally lie outside the window the
# user has requested.  Second, the way DateTime arithmetic works is
# that only integer numbers of days can be added on.  To address both
# of these, we add 2 to the input values, and then truncate to just
# the integer part, which has the effect of adding between 1 and 2
# days to our actual window on each end. 

my $start_date = $base_date->clone;
$start_date->subtract( days => int($days_in_past + 2) );

my $end_date = $base_date->clone;
$end_date->add( days => int($days_to_print + 2) );
   
# Now calculate the desired sunrises and sunsets, and save them as
# DateTime::Set objects.

# We start by creating empty sets, and a DateTime object we'll
# increment to step through our time interval:
my $sunsets = DateTime::Set->empty_set;
my $sunrises = DateTime::Set->empty_set;
my $current_date = $start_date->clone;

# Now loop over the days in the interval and calculating the sunrises
# and sunsets:
while ($current_date <= $end_date) {
  # Set our "sun" object to this date:
  $sun->datetime($current_date);

  # Find the next sunrise and sunset times, and put them into the
  # sets we are building up:
  my $next_sunset = $sun->set_time(horizon => $twilight_rad);
  my $next_sunrise = $sun->rise_time(horizon => $twilight_rad);

  # If the Sun doesn't rise or doesn't set on that day (e.g. at polar
  # latitudes) then the above might be undefined and we can't merge it
  # with the rest of the set: 

  if (not defined $next_sunset) {
      # Check to see if this is because Sun is always down:
      if ($sun->el(format => 'rad') < $twilight_rad) {
	  # Dark so we can observe; take the meridian crossing as the
	  # delimeter of the night, rather than sunrise/sunset: 
	  $sunsets = $sunsets->union( $sun->meridian_time() ); 
      }
  } else {
      $sunsets = $sunsets->union( $next_sunset ); 
  }

  if (not defined $next_sunrise) {
      # Check to see if this is because Sun is always down:
      if ($sun->el(format => 'rad') < $twilight_rad) {
	  # Dark so we can observe; take the meridian crossing as the
	  # delimeter of the night, rather than sunrise/sunset: 
	  $sunrises = $sunrises->union( $sun->meridian_time() ); 
      }
  } else {
      $sunrises = $sunrises->union( $next_sunrise ); 
  }
  

  # Increment by a day and go back to the beginning of the loop.
  # Actually, since the time of sunset and sunrise shift a little bit
  # day to day, if we increment by a day, and if we happen to be doing
  # this exactly at sunset or sunrise, we could miss an event (e.g.,
  # the next sunrise could come 23h59m later and we increment by 24h).
  # To be on the safe side, increment by less than 24 hours. The edge
  # case near the poles is that the first/last days with sunlight can
  # differ by up to an hour in day length from the previous day. If we
  # end up calculating some duplicate times (which we will eventually
  # if we have a long enough span) it doesn't really matter, since
  # DateTime::Set recognizes duplicate values and doesn't actually add
  # another one to the set.

  $current_date->add( hours => 23, minutes => 0 );
}


# Print out the appropriate header for either the calendar output or
# the HTML page:
my $print_calendar;

if ($print_html == 0) {
  $print_calendar = 1;
  print $q->header(-type =>"text/csv",
		   -charset => "UTF-8",
		   -attachment => "transits.csv");
  my $header_text = "Subject,Start Date,Start Time,End Date," .
    "End Time,All Day Event,Description\r\n";
  print $header_text;
} else {  # HTML output
  $print_calendar = 0;
  if ($print_html == 1) {
      # Print the HTML header, including the cookies.  This output is
      # where the cookies actually are returned the user's browser and set.
      print $q->header(-type => "text/html",
		       -charset => "UTF-8",
		       -Cache_Control => "no-cache",
		       -cookie => [$latitude_cookie, 
				   $longitude_cookie, 
				   $utc_cookie,
				   $unc_cookie,
				   $and_cookie,
				   $observatory_cookie,
				   $timezone_cookie, 
				   $days_cookie,
				   $minimum_start_elevation_cookie, 
				   $minimum_end_elevation_cookie, 
				   $minimum_ha_cookie,
				   $maximum_ha_cookie,
				   $baseline_hrs_cookie,
				   $days_in_past_cookie, 
				   $minimum_priority_cookie, 
				   $maximum_Vmag_cookie, 
				   $minimum_depth_cookie,
				   $max_airmass_cookie,
				   $twilight_cookie]
		       );
      print $q->start_html( -title => "Upcoming transits",
			    );
  } else {
      # Print raw CSV (not for calendar):
      print $q->header(-type =>"text/csv",
		       -charset => "UTF-8",
		       -attachment => "transits.csv");
  }
}  # End printing headers.


# Now, the main part of the code, for dealing with transits.  First,
# we need to set up some variables we'll use.

# Set up a hash that contains input parameters describing the
# observatory, dates, and so on - parameters that are not
# target-specific but which govern which events are observable and/or
# desired: 

my %constraints = (
		   days_to_print=>$days_to_print,
		   days_in_past=>$days_in_past,
		   observatory_latitude => $observatory_latitude,
		   observatory_longitude => $observatory_longitude,
		   observatory_timezone => $observatory_timezone,
		   observing_from_space => $observing_from_space,
		   minimum_start_elevation 
		      => $minimum_start_elevation,
		   minimum_end_elevation 
		      => $minimum_end_elevation,
		   sunrises => $sunrises,
		   sunsets => $sunsets,
		   telescope => $telescope,
		   debug => $debug,
		   base_date => $base_date,
                   twilight_rad => $twilight_rad,
                   sun => $sun,
                   moon => $moon,
                   baseline_hrs => $baseline_hrs,
                   phase => $phase,
		   );


# Initialize the arrays we'll use to sort the eclipse times and
# the text to print:
my @eclipse_times = ();
my @eclipse_info = ();
my @eclipse_input_data = ();
my @non_eclipse_info = ();

# Separate code fetches the target info, and then stores it in a text
# file.  Here we read in the text file and parse it. 


# Specify the record separator we will use to split up the line
# into fields; This record separator (a comma followed by a
# period) makes it straightforward to allow commas to be embedded
# within fields themselves.  Spaces on either side of the field
# separator are not significant, i.e. they are ignored.

my $rec_separator = ',.';

# If they have entered an ephemeris for a single object, we use
# that to construct an equivalent target info line; otherwise we
# read target lines from the specified target file:

my @lines = ();
my $no_twilight = 0;

if ($sunrises->is_empty_set() and $sunsets->is_empty_set()) {
    # No darkness; just leave target list empty;
    # Set a flag so we know why there are no entries:
    $no_twilight = 1;
} elsif ($single_object == 1) {
    # They have checked the radio button that specifies manual entry
    # of the ephemeris for a single object, so get the entered
    # info. Put these into a hash, since that's what would be returned
    # if we use a regular target file:

    my %t;
    $t{'RA'} =  $q->param("ra");
    $t{'Dec'} =  $q->param("dec");

    $t{'name'} =  $q->param("target");
    $t{'period'} =  $q->param("period");
    $t{'epoch'} =  $q->param("epoch");
    $t{'duration'} =  $q->param("duration");
    $t{'depth'} =  $q->param("depth");
    $t{'comments'} =  "Manually-entered single object";

    push @lines, \%t;
    # Effectively disable the filtering on transit depth and
    # priority below by re-setting the threshhold values here.
    # The target doesn't have this info, so we don't want it
    # to get filtered out inadvertently.
    $minimum_depth = -2;
    $minimum_priority = -2;
} else {
    # Read the file. Could include a different path here; be sure this
    # is readable by whatever process runs the CGI script.

    # Try to open the file; we wrote it with UTF-8 encoding, so make 
    # sure we read it back the same way: 

    @lines = @{ Text::CSV::csv(in => $target_file, 
			       encoding => "UTF8",
			       headers => "auto",
		    )};
}

# Initialize a few variables for keeping track of errors:
my $error_line_count = 0;
my @error_names_list = ();


# Flag to indicate whether we exit the loop after hitting a limit on
# how many events to print: 
my $reached_max_eclipses = 0;

# Now, loop over the lines of the input, assuming one target per
# line.  Lines read from CSV are hash references, with each hash keyed
# by the header names in the file. 

# Fields assumed to be present in the CSV (and thus in the hash keys)
# are: 

# name: target name
# RA:  J2000 RA in h:m:s
# Dec: J2000 Dec in d:m:s
# vmag: V magnitude
# epoch:  JD for central transit (i.e. zero point of the ephemeris)
# epoch_uncertainty: in days; optional, but propagated if present. 
# period: Period in days
# period_uncertainty: in days; optional, but propagated if present.
# duration: Transit duration, in hours
# comments: Comments on the target; these are not used in the processing,
#           but they are passed along to the output.
# depth: Depth of the transit in ppt.  Not used in calculations but
#        can be a filter for which events to display.

# If different field names are used in the input file, name
# reassignments can be given below (as with RA and Dec here).

# Our list of references to targets we want to search, i.e. those
# that survive any cuts on target name, magnitude, etc., 
#  and have sufficient data: 

my @targets_to_search = ();

TARGET_LOOP:
foreach my $target_ref (@lines) {
  
  # We default to everything being assumed to be a periodic /
  # eclipsing / transiting event for this code; non-period targets are
  # an option in other code that's not used here.

  $target_ref->{phot_requested} = 1;

  # Likewise we assign a placeholder priority for the non-TESS
  # targets: 
  if (not ($tess or $exowatch)) {
      $target_ref->{priority} = 1;
  }

  # Just different names for these than are in input file: 
  $target_ref->{ra_string} = $target_ref->{RA};
  $target_ref->{dec_string} = $target_ref->{Dec};

  # For printing input info if needed: 
  my $cleaned_line = join(", ", map { "$target_ref->{$_}" } keys %$target_ref);

  # Combine the hash of target-specific info with the
  # previously-created hash of general observatory circumstances, to
  # make a master hash that we will use to determine object
  # observability.  Note that combining two hashes in this way causes
  # problems if there are duplicate keys in the two hashes (the value
  # in the second key-value pair will overwrite the one in the first
  # pair with the same key); watch out for this if you add fields to
  # either hash. 

  my %target_info = (%$target_ref, %constraints);


  # Now save the input line, to show the ephemeris used.
  # Note: it seems a little weird here to save this input line in a
  # hash with only one entry, and then push that one-element hash
  # into an array.  However, this array-of-hashes format ends up
  # making it easier to loop over later in the HTML output template.
  # (See explanation and examples for HTML::Template at
  # http://html-template.sourceforge.net/article.html )

  # Make our local hash:
  my %input_data;
  $input_data{line} = $cleaned_line;
  push @eclipse_input_data, \%input_data;


  # Then check to see if we're restricting only to particular
  # targets, and if so, see if this one matches.  If it doesn't, we
  # can just go on to the next target:
  if ($target_string ne "") {
      if ($tess) {
	  # Users might add "TOI" to search since it's in the output: 
	  my $toi_string = "TOI " .  $target_info{TOI};
	  unless (($target_info{name} =~ /$target_string/i) or 
		  ($toi_string =~ /$target_string/i))
	  {
	      next TARGET_LOOP;
	  }
      } else {
	  if ($target_info{name} !~ /$target_string/i) {
	      next TARGET_LOOP;
	  }
      }
  }


  # Make sure the necessary fields are there (check against empty
  # strings) and if not, increment error count and go to next field.

  my $error = 0;  # Start by assuming no error;

  # Must have coords no matter what:
  if ( ($target_info{ra_string} eq "") or ($target_info{dec_string} eq "") ) {
      $error = 1;
  }

  if ($error) {      
      $error_line_count++;
      push @error_names_list, $target_info{name};
      if ($debug) {
	  print $q->pre("Error processing incomplete input line:
						    $cleaned_line");
      }
      next TARGET_LOOP;
  }


  # See if the priority is too low to bother with:
  if ($target_info{priority} < $minimum_priority) {
      next TARGET_LOOP;
  }

  # See if the target is too faint:
  if ((defined $target_info{vmag}) and
      ($target_info{vmag} !~ /^\s*$/) and
      ($target_info{vmag} > $maximum_V_mag)) {
      next TARGET_LOOP;
  }

  # OK, the target has passed all of our input filters, so now we pass
  # it off to the subroutine that reads the ephemeris and finds all of
  # the visible upcoming transits, subject to the constraints we've
  # imposed.  The target info is passed in, and the return values are
  # array references that contain information about the transits (if
  # any) that were found to be visible for this target. For example,
  # if the target was found to have two visible transits in the
  # specified time period, then each of the returned references would
  # be to an array with two entries.

  # This subroutine is where much of the work of the program takes
  # place.

  # We pass in all of the necessary info in a hash of input
  # parameters.  Since the variables above here are global by
  # default, it's possible that there is some necessary information
  # that is being used by the subroutine through global variables
  # rather than being passed in as a parameter, but I've attempted
  # to make this modular and to pass the necessary information only
  # through parameters rather than relying on globals. 

  # As long as this is a periodic target (type 1 or 3), we pass it to
  # the subroutine that calculates eclipses:
  if ( ($target_info{phot_requested} == 1) or
       ($target_info{phot_requested} == 3) ) {

      # See if the depth is too low to bother with; this filter only
      # applies to periodic targets, so is inside the above 'if':
      if ($target_info{depth} < $minimum_depth) {
	  next TARGET_LOOP;
      }

      push @targets_to_search, \%target_info;
  }

  # Now we also need to check for observability for "any time"
  # targets; here we don't check for specific eclipses, just for
  # whether the maximum altitude of the target during the night
  # exceeds a given threshold (currently set to 10 degrees).

  if ( ($target_info{phot_requested} == 2) or
       ($target_info{phot_requested} == 3) ) {
      my %local_hash = %target_info;
      my ($target_info_ref) = get_observability(\%local_hash);
      push @non_eclipse_info, @$target_info_ref;
  }

    
}  # end of TARGET_LOOP loop over input file

# Print a message showing how many targets we are searching; if 
# none at all, just bail out now: 
if ($print_html == 1) {
    my $n_targets = scalar @targets_to_search;
    my $constraint_msg = "(on name, V mag, depth, etc.).  ";
    if ($n_targets == 0) {
	print "<h2>No targets match your constraints $constraint_msg";
	print "Check your inputs.\n</h2>";
	print $q->end_html;
	exit;
    } else {
	if ($n_targets == 1) {
	    print "<p>Only 1 target matches your constraints $constraint_msg";
	} else {
	    print "<p>$n_targets targets match your constraints $constraint_msg";
	}
	print "Searching for observable transits...</p>\n";
    }
}

# For parallelizing, we split the input target list into roughly 
# equal-sized chunks and parse out *lists* of targets in parallel.
# This reduces overhead from the inter-process communication for 
# spawning a process for a small number of targets. 

# Number of forks we'll use; we have 8 cores, so leave one free: 
my $forks = 7;
# Divide the target array into chunks; make sure we don't
# have more chunks than subprocesses, but also that we don't
# end up with zero chunk size if target list is small:
my $chunk_size = max(5, int(scalar @targets_to_search / ($forks - 1)));
my $pm = Parallel::ForkManager->new($forks);
# Hash that will hold the results: 
my %results;

# Anonymous subroutine that will run at the end of each fork, 
# to return the results from that process in a hash:
$pm->run_on_finish( sub {
    my ($pid, $exit_code, $ident, $exit_signal, 
	$core_dump, $data_structure_reference) = @_;
    my $key = $data_structure_reference->{key};
    $results{$key} = $data_structure_reference->{result};
});

# Assemble our set of chunks of the input target array: 
my @chunk_list = ();
# Make a copy so we preserve the original target list, since
# 'splice' is destructive: 
my @target_list_copy = @targets_to_search;
while (@target_list_copy) {
    my @target_list = splice @target_list_copy, 0, $chunk_size;
    # We add a *reference* to this list of a subset of targets: 
    push @chunk_list, \@target_list;
}

# Variable to serve as a key for hash returning from 
# different forks:
my $i = 0;
# Now loop over the sub-lists, spinning off separate processes: 
foreach my $chunk_ref (@chunk_list) {
    $i++;
    my $pid = $pm->start;
    # Now we have forked, and have two processes entering at this 
    # part of the code (if the fork was successful).
    # Parent process has PID > 0, and falls through to next part of loop; 
    # child process has PID == 0, so continues to do this chunk.
    # If the fork failed, PID is undefined. 
    if ((defined $pid) and ($pid == 0)) {
	# Lists to save results from this set of targets: 
	my @eclipse_times_partial = ();
	my @eclipse_info_partial = ();
	# Process a chunk of the target list: 
	foreach my $target_ref ( @{$chunk_ref} ) {
	    my ($eclipse_times_ref, $eclipse_info_ref) = get_eclipses($target_ref);
	    push @eclipse_times_partial, @{$eclipse_times_ref};
	    push @eclipse_info_partial, @{$eclipse_info_ref};
	}
	# Put references to these lists into an array: 
	my @return_vals = (\@eclipse_times_partial, \@eclipse_info_partial);
	# And return a reference to that array, keyed by our integer i:
	$pm->finish(0, { result => \@return_vals, key => $i });
    }
}
$pm->wait_all_children;
 
# Now that all processes are done, we unpack the results hash
# and put all of returned events into lists: 
foreach my $key (keys %results) {
   my ($eclipse_time_ref, $eclipse_info_ref) = @{ $results{$key} };
   push @eclipse_times, @{ $eclipse_time_ref };
   push @eclipse_info, @{ $eclipse_info_ref };
}

# Total number of events found: 
my $n_eclipses = scalar @eclipse_times;

# For now, save the non-parallel code in case we want to go back to
# it, or do an if-then to run it in some cases. 
# SEARCH_LOOP:
# # Now actually do the searching:
# foreach my $target_info_ref (@targets_to_search) {
#     my ($eclipse_time_ref,$eclipse_info_ref) = get_eclipses($target_info_ref);

#     # Take the references to the returned lists of eclipse strings and
#     # times, and add those arrays to our growing lists:
#     push @eclipse_times, @$eclipse_time_ref;
#     push @eclipse_info, @$eclipse_info_ref;

#     # Check to see if we have reached the limit of how many events
#     # to find; if so set a flag and stop searching: 
#     $n_eclipses = scalar @eclipse_times;
#     if ($n_eclipses > $max_eclipses_to_print) {
# 	$reached_max_eclipses = 1;
# 	last SEARCH_LOOP;
#     }
# }

# All done - sort, then print the output!

# If there were any errors processing the input, note that first:
if ($error_line_count > 0) {
    my ($phrase, $verb, $target_error_string);
    if ($error_line_count == 1) {
	$phrase = "target has";
	$verb = "was";
    } else {
	$phrase = "$error_line_count targets have";
	$verb = "were";
    }
    $target_error_string = join(", ", @error_names_list);
    if ($print_html == 1) {
	print $q->p("The following $phrase incomplete data" .
		    " and $verb not used: $target_error_string");
    }
}


# Now we want to report the visible transits, but we need to rearrange
# them first.  The subroutine has found them all, but they are ordered
# target by target rather than chronologically, so we need to sort
# them by mid-transit time.  We have information about each transit
# stored in different arrays, so we need not only to sort the transit
# times - we also need to be able to sort other arrays in that same
# order.  So what we want is a set of array *indices* that we can use
# to index each of these arrays, so that we keep the correct entries
# for each transit matched up with each other.

# This next bit is potentially a little cryptic, so let's document it
# carefully.  First, create an array that just has integers in
# numerical order, with the same number of entries as our array of
# transit times:

my @array_indices = (0..$#eclipse_times);

# Now we will sort that array, but as the sorting criterion, we will
# use the array values of the array @eclipse_times.  The syntax of
# Perl's sort is:
# @array_of_sorted_values = sort { sorting criterion } @array_to_sort;

my @sorted_eclipse_indices = sort {$eclipse_times[$a] <=>
				       $eclipse_times[$b]} @array_indices;

# So now we have an array of indices that are sorted in such a way
# that they will return eclipse times in chronological order if we use
# the indices to index array @eclipse_times. 

# Sort the eclipse information that we want to output:
my @sorted_eclipse_info = @eclipse_info[@sorted_eclipse_indices];

# Now we can use those indices to print out the eclipse *strings* in
# time order:

if ($print_html) {   # True for either 1 or 2

  if ($reached_max_eclipses) {
      my $max_message = "Not all potential targets were searched. "
          . "Output truncated by exceeding cap of "
	  . " $max_eclipses_to_print events. "
          . "To search all targets, set tighter constraints"
          .  " or use a shorter time window.";
      if ($print_html == 1) {
	  print $q->h2($max_message);
      } else {
	  print $max_message;
      }
  }


  if ($print_html == 1) {
      # Print the title text for the output page:
      my $day_word = 'days';
      if ($days_to_print <= 1) {
	  $day_word = "day";
      }

      my $past_string = '';
      if ($days_in_past > 0) {
	  $past_string = " and the past $days_in_past days";
      }

      my $timezone_to_display = $use_utc ? 'UTC' : $observatory_timezone;
      print $q->h2("Upcoming events for the next $days_to_print $day_word"
		   . " $past_string from $start_date_string;"
		   .  " start/end given in timezone "
		   . "$timezone_to_display.");
      my $label_lowercase = $twilight_label;
      $label_lowercase =~ tr/[A-Z]/[a-z]/;
      print $q->h3("Night starts/ends at $label_lowercase.");
  } elsif ($print_html == 2) {
      # The CSV standard says that double quotes embedded within a
      # quoted field need to be doubled up so they aren't interpreted as
      # the end of the field:
      foreach my $t (@sorted_eclipse_info, @non_eclipse_info) {
	  $t->{comments} =~ s/\"/\"\"/g;
      }
  }


  # Get the count of how many non-eclipse "any time" targets we have,
  # since this may well be zero for some uses:
  my $non_eclipse_target_count = scalar(@non_eclipse_info);

  # Also sort the non-eclipse targets by time of max elevation during
  # the night; remember that each element is a hash reference, so we
  # de-reference to get the desired field:
  my @sorted_non_eclipse_info = sort {$a->{max_elevation_jd} <=>
				       $b->{max_elevation_jd}
				  }  @non_eclipse_info;

  # Initialize the HTML template that will create the output.
  my $template = HTML::Template::Expr->new(filename =>
					   $template_filename,
					   utf8 => 1,
					   die_on_bad_params => 0);

  # Pass the eclipse information, and the variables describing
  # the input constraints, into the template, and print the output.

  $template -> param(eclipse_info => \@sorted_eclipse_info,
		     eclipse_input_data => \@eclipse_input_data,
		     non_eclipse_info => \@sorted_non_eclipse_info,
		     non_eclipse_target_count => $non_eclipse_target_count,
		     observatory_latitude => $observatory_latitude,
		     observatory_longitude => $observatory_longitude,
		     observatory_name => $observatory_name,
		     observatory_shortname => $observatory_shortname,
		     observing_from_space => $observing_from_space,
		     observatory_string =>
		       uri_escape($observatory_string),
		     minimum_start_elevation => 
		       $minimum_start_elevation,
		     minimum_end_elevation => 
		       $minimum_end_elevation,
		     minimum_ha => 
		       $minimum_ha,
		     maximum_ha => 
		       $maximum_ha,
		     timezone => $observatory_timezone,
		     baseline_hrs => $baseline_hrs,
		     show_unc => $show_unc,
		     use_utc => $use_utc,
		     and_vs_or => $and_vs_or,
		     minimum_depth => $minimum_depth,
		     minimum_priority => $minimum_priority,
		     twilight => $twilight,
		     twilight_label => $twilight_label,
		     show_ephemeris => $show_ephemeris,
		     max_airmass => $max_airmass,
		     reached_max_eclipses => $reached_max_eclipses,
		     tess => $tess,
		     no_twilight => $no_twilight,
		    );
  print $template->output();

  if ($print_html == 1) {
      my $time_seconds =  sprintf("%d", time - $script_start_time);
      my $seconds_word = ($time_seconds eq "1") ? "second" : "seconds";
      my $execution_time = sprintf("Script took %s %s for %d events.", 
				   $time_seconds, $seconds_word, $n_eclipses);
      print $q->p($execution_time);
      print $q->end_html;
  }

} else {  # Matches "if $print_html" - if not, it's basic
          # CSV calendar output with $print_html == 0.
  my $eclipse_entry;
  foreach $eclipse_entry (@sorted_eclipse_info) {
      print $eclipse_entry->{csv_text};
  }
}

# End of main program.



# As noted above, the main program focuses on reading the input data,
# and printing the output, and defers much of the work of identifying
# observable events to a subroutine.  Here it is!

sub get_eclipses {

  # This subroutine takes as input various parameters that describe
  # one particular target (name, coordinates, magnitude), its
  # ephemeris (zero point, period, depth and time width of transit),
  # and observing circumstances (latitude, longitude, timezone,
  # time/date window to consider).  It then calculates the events
  # occurring during the specified time window for that target, and
  # determines whether or not these will be observable (or partially
  # observable) given the input constraints.  Information about any
  # observable events is returned in the form of references to arrays
  # of event information; see end of subroutine for details on what is
  # returned.  Note: returned array references may be to empty arrays,
  # i.e. there may be no observable events for a particular target.

  # First, unpack the input parameters; these are passed in a hash so
  # that they can be identified by name, i.e. it's not necessary to
  # pass them in in any particular order.

  my ($param_ref) = @_;
  my $ra_string = $param_ref->{ra_string};
  my $dec_string = $param_ref->{dec_string};
  my $name = $param_ref->{name};
  my $vmag = $param_ref->{vmag};
  my $epoch = $param_ref->{epoch};
  my $epoch_uncertainty = $param_ref->{epoch_uncertainty};
  my $period = $param_ref->{period};
  my $period_uncertainty = $param_ref->{period_uncertainty};
  my $eclipse_width = $param_ref->{duration};
  my $days_to_print = $param_ref->{days_to_print};
  my $days_in_past = $param_ref->{days_in_past};
  my $observatory_timezone = $param_ref->{observatory_timezone};
  my $observing_from_space = $param_ref->{observing_from_space};
  my $comments = $param_ref->{comments};
  my $priority = $param_ref->{priority};
  my $depth = $param_ref->{depth};
  my $sunsets = $param_ref->{sunsets};
  my $sunrises = $param_ref->{sunrises};
  my $telescope = $param_ref->{telescope};
  my $minimum_start_elevation 
    = $param_ref->{minimum_start_elevation};
  my $minimum_end_elevation 
    = $param_ref->{minimum_end_elevation};
  my $debug = $param_ref->{debug};
  my $base_date = $param_ref->{base_date};
  my $sun = $param_ref->{sun};
  my $moon = $param_ref->{moon};
  my $twilight_rad = $param_ref->{twilight_rad};
  my $baseline_hrs = $param_ref->{baseline_hrs};
  my $phase = $param_ref->{phase};
  my $tess = (defined $param_ref->{'disposition'}) ? 1 : 0;

  # Before we can calculate eclipse visibility, we need to set up
  # some basics, like the current date and time.

  my $thisjd = DateTime::Format::Epoch::JD->format_datetime($base_date); 

  # Set up a coordinate object that will allow us
  # to calculate the elevation of the target at different
  # times: 

  my $target = new Astro::Coords( ra => $ra_string,
				  dec => $dec_string,
				  type => 'J2000',
				  units => 'sexagesimal',
      );
  $target->telescope($telescope);

  my $ra_deg = $target->ra( format => 'deg' );
  my $dec_deg = $target->dec( format => 'deg' );



  # Now the next bit of code takes the 'epoch' field of the transit
  # ephemeris, which gives the JD of one particular transit (typically
  # at some point in the past), and uses that to calculate the JD of a
  # transit that is near the start of the time window we're
  # considering.

  # Get the number of periods between the start of our time window
  # (which is possibly some days in the past) and the initial epoch:

  my $n_periods = ($thisjd - $days_in_past - $epoch)/$period; 

  # Now get just the integer part of this, so we can start our search
  # at a new epoch (i.e. exactly on a transit).  For safety, we start
  # a few periods before the desired time window, just so we don't
  # lose an event in our rounding off:

  my $n_period_int = int($n_periods - 2); 

  # Now get a new transit epoch that is that integral number of
  # periods later, which should be close to our desired start time:

  my $new_epoch = $epoch + ($n_period_int * $period);

  # If we want to consider a phase other than the primary eclipse
  # (which is at phase = 0), calculate the necessary offset in time:

  my $offset = $period * $phase;

  # Now that we have determined our desired starting epoch, we
  # define various objects in Perl's DateTime framework; these will
  # let us more easily manipulate and compare dates and times, do
  # time arithmetic, shift timezones, etc.

  # Define the object for the eclipse date and time.  Until we need
  # to do otherwise, we'll do all of our calculations in UTC.
  my $dt = $base_date->clone;
  $dt->set_time_zone('UTC');

  # Also create separate objects for transit start and end: 
  my $dt_start = $dt->clone();
  my $dt_end = $dt->clone();

  # We'll want to check the start and end of eclipse, too - if any of
  # these (start, middle, or end) are at night, then we'll list it.
  # Thus, we need to calculate the eclipse half-width, and it will be
  # useful to have this expressed as a DateTime::Duration object as
  # well, for easier time arithmetic.

  my $eclipse_half_duration =  hours_to_duration($eclipse_width/2.);

  # We also want the above in units of days; 0.5*(hrs/24) = hrs/48
  my $eclipse_half_dur_days = $eclipse_width/48;

  # Likewise for the out-of-transit baseline requested: 

  my $baseline_duration = hours_to_duration($baseline_hrs);

  # Now we've laid all the groundwork, so we can start into the main
  # loop of this subroutine.  We start at the eclipse event whose
  # epoch we determined above, and we step through successive eclipses
  # (jumping forward one period each time) until we reach the end of
  # the specified time window.  For each eclipse, we check to see
  # whether or not it is at least partially observable, and if so, we
  # save the necessary information for return at the end of the
  # subroutine.

  # Initialize the lists for holding the eclipse information for any
  # observable eclipses.  If no observable eclipses are found, these
  # lists will be returned empty. 
  my @local_eclipse_strings = ();
  my @local_eclipse_times = ();
  my @local_eclipse_info = ();

  # Just so we don't loop forever (e.g. if a huge number of days in
  # the future was specified), we set some maximum number of
  # eclipses we'll check:
  my $eclipse_iteration = -1;
  my $max_eclipses_to_try = 2000;


  # Whether the ingress and egress are split across different nights: 
  my $split_transit = 0;

 ECLIPSE_LOOP:
  while ($eclipse_iteration < $max_eclipses_to_try) {

    # If the split_transit flag is set, then we are doing the second
    # pass for a transit where both ingress and egress are observable,
    # but on different nights; don't increment the counter.
    $eclipse_iteration++ unless $split_transit;
    # Calculate JD of next eclipse, taking into account the shift from
    # BJD at the solar system barycenter (where the ephemeris is
    # specified) to the JD_UTC observed at Earth for this particular
    # target: 
    my $eclipse_bjd = $new_epoch + $period*$eclipse_iteration + $offset;
    my $eclipse_jd = bjd2utcjd($eclipse_bjd, $ra_deg*DD2R,
			       $dec_deg*DD2R); 

    # For both of the endpoint comparisons, we extend by half the
    # duration, in case the ingress or egress falls within our window
    # even though the midpoint might not. By doing this, we are making
    # sure the entire event (not just the midpoint) is outside the
    # window of consideration.

    my $ingress_jd = $eclipse_jd - $eclipse_half_dur_days;
    my $egress_jd  = $eclipse_jd + $eclipse_half_dur_days;

    # Flags for whether the ingress and egress fall within the
    # requested time window.  Start out false, then check below.
    my $ingress_in_window = 0;
    my $egress_in_window = 0;
 
    # Have we gone past the specified time window yet?  If so, we
    # exit from the loop:
    if ($ingress_jd > ($thisjd + $days_to_print)) {
	last ECLIPSE_LOOP;
    } elsif ($ingress_jd >= ($thisjd - $days_in_past)) {
	$ingress_in_window = 1;
    }

    # Is the eclipse completely before our time window? If so,
    # just increment to next eclipse and jump back to the start of
    # the loop:
    if ( $egress_jd < ($thisjd - $days_in_past) ) {
	next ECLIPSE_LOOP;
    } elsif ($egress_jd <= ($thisjd + $days_to_print)) {
	$egress_in_window = 1;
    }

    # Note that there is an edge case here: for a long-duration
    # transit, it's possible that neither the ingress nor egress will
    # fall within our window, but the midpoint will.  We will treat
    # this as observable if the "observing_from_space" option is set,
    # but otherwise we will catch this below, where we require
    # observability of ingress and/or egress.

    # A more complicated edge case arises if the transit duration is
    # long and both the ingress and egress are observable at night,
    # but on different nights.  Those are potentially two separate,
    # observable events; they are handled with the split_transit
    # flag below.

    # Convert the eclipse midpoint from JD to a DateTime object.
    # There's a slight computational cost to doing this conversion
    # every time through the loop, rather than having one DateTime
    # object and incrementing it; but the disadvantage of the latter
    # is that we'd have to jump through hoops to create a Duration
    # object of sufficient precision.  This is just simpler. 

    my $dt = DateTime::Format::Epoch::JD->parse_datetime($eclipse_jd);
    $dt->set_time_zone('UTC');
    # Get the UT date of mid-transit:
    my $mid_date_utc = $dt->ymd();


    # Now that we have the time object, we can ask the key
    # question: is this eclipse at night, or during the day? We
    # test that for all three of the start, middle, and end of the
    # eclipse, so that we can show partially-visible eclipses:

    # Get DateTime objects for start and end of eclipse:
    my $dt_start = $dt->clone->subtract_duration($eclipse_half_duration);
    my $dt_end = $dt->clone->add_duration($eclipse_half_duration);
    my $start_date_utc = $dt_start->ymd();
    my $end_date_utc = $dt_end->ymd();



    # Then use this to get elevations at the relevant times: 
    $target->datetime($dt_start);
    my $el_start_deg = $target->el(format=>'deg');

    # Short-circuit our loop if this doesn't pass the cut: 
    if ( ($el_start_deg < $minimum_start_elevation) 
	 and ($and_vs_or eq 'and') and (not $observing_from_space)) {
	next ECLIPSE_LOOP;
    }


    $target->datetime($dt_end);
    my $el_end_deg = $target->el(format=>'deg');

    if (      ($el_end_deg < $minimum_end_elevation) 
	 and  ($el_start_deg < $minimum_start_elevation) 
	 and (not $observing_from_space)) {
	next ECLIPSE_LOOP;
    } elsif (( ($el_end_deg < $minimum_end_elevation) 
	 or    ($el_start_deg < $minimum_start_elevation) )
	and ($and_vs_or eq 'and')
        and (not $observing_from_space)) {
	next ECLIPSE_LOOP;
    }

    # If this event passes further cuts below, eventually we will want
    # to know the mid-event elevation as well, but we defer
    # calculating it, as well as hour angles and azimuths, until we're
    # sure we need them.

    # Now we can check whether either the ingress or egress occurs at
    # night; to do this, we just find the elevation of the sun at
    # those times, and compare them to the threshold set by the user
    # for determining sunset: 


    $sun->datetime($dt_start); 
    my $is_daytime_start = ( $sun->el(format=>'rad') > $twilight_rad );
    $sun->datetime($dt_end); 
    my $is_daytime_end   = ( $sun->el(format=>'rad') > $twilight_rad );

    # Again, eventually we may want to know whether the middle is in
    # daytime, but we'll defer that until we determine whether or not
    # we really need it. 


    if ( ($observing_from_space) or 
	 (not ($is_daytime_start and $is_daytime_end))) {   

      # Part of eclipse is at night - go ahead!

      # To be shown as an observable eclipse, we check both the start
      # and the end elevation, and also see whether the start and end
      # are at night.  We also cast a wider net above in terms of the
      # times, but now we check to see if the start and end are
      # actually within the time window the user requested. 

      # Whether the start and end constraints are ANDed or ORed
      # depends on user input, so take that literal "and" or "or"
      # string and use 'eval' to apply it in a boolean test. If the
      # user has requested the "space" observatory option, which shows
      # all eclipses for a given target within the time window, we
      # ignore these other constraints.

      my $start_is_observable = (($el_start_deg >= $minimum_start_elevation) 
      	  and (not $is_daytime_start) and $ingress_in_window);
      my $end_is_observable = (($el_end_deg >= $minimum_end_elevation)
      	  and (not $is_daytime_end) and $egress_in_window);
      my $is_observable = eval("\$start_is_observable $and_vs_or \$end_is_observable");


      if (($is_observable) or ($observing_from_space)) {
	  
	# Then the eclipse should be visible! ... but one more check: 

	# Calculate the hour angles and azimuths at start; these are
	# relatively expensive to calculate, so we defer them to here: 
	$target->datetime($dt_start);
	my $az_start_deg = $target->az(format=>'deg');
	my $ha_start = $target->ha(format=>'hour');
	$target->datetime($dt_end);
	my $az_end_deg = $target->az(format=>'deg');
	my $ha_end = $target->ha(format=>'hour');

	# Now re-evaluate observability: 
	$start_is_observable = ($start_is_observable and 
	    ($ha_start >= $minimum_ha) and 
	    ($ha_start <= $maximum_ha)); 

	$end_is_observable = ($end_is_observable and 
	    ($ha_end >= $minimum_ha) and 
	    ($ha_end <= $maximum_ha)); 

	$is_observable = eval("\$start_is_observable $and_vs_or \$end_is_observable");


	unless (($is_observable) or ($observing_from_space)) {
	     next ECLIPSE_LOOP;
	}


	# Check for very long-duration events where both start and end
	# could be observable, but are in different nights: 
	my $next_sunrise = $sunrises->next($dt_start);
	my $previous_sunset = $sunsets->previous($dt_start);
	
	if ($split_transit) {
	    # This should be the second pass for a transit where both
	    # ingress and egress are observable, but on different
	    # nights.  We have handled ingress on the first pass, so
	    # now handle egress (by just marking ingress as
	    # unobservable) and reset the flag: 
	    $start_is_observable = 0;
	    $split_transit = 0;
	} elsif (($start_is_observable and $end_is_observable) and 
		 ($next_sunrise < $dt_end)) {
	    # We have a long-duration case. We mark this as two
	    # separate events that might both be observed. For the
	    # first pass, we take the ingress and mark the egress as
	    # unobservable.
	    next ECLIPSE_LOOP if (($and_vs_or eq 'and') and 
				  (not $observing_from_space));
	    $end_is_observable = 0;
	    $split_transit = 1;
	}

	# Passed other tests, now go ahead and get the mid-event
	# elevation and daytime status: 

	$target->datetime($dt);
	my $az_mid_deg = $target->az(format=>'deg');
	my $el_mid_deg = $target->el(format=>'deg');
	my $ha_mid = $target->ha(format=>'hour');

	$sun->datetime($dt); 
	my $is_daytime_mid   = ( $sun->el(format=>'rad') > $twilight_rad );

	my $mid_is_observable = ((not $is_daytime_mid) and 
				   ($el_mid_deg >= $minimum_end_elevation) and 
				   ($el_mid_deg >= $minimum_start_elevation) and 
				   ($ha_mid >= $minimum_ha) and 
				   ($ha_mid <= $maximum_ha) and 
				 ($dt < $next_sunrise));



        # Determine the uncertainty on the transit time by propagating
        # the period and epoch uncertainties.  These may be undefined
        # for particular targets.  If both are undefined, leave this
        # uncertainty field as undefined.
        my ($midtime_uncertainty_string, 
	    $midtime_uncertainty_hours,
	    $midtime_uncertainty_duration); 
        if ( ( defined $period_uncertainty ) or 
             ( defined $epoch_uncertainty ) ) {
	   # We know at least one is defined; to avoid error messages,
           # set the other to zero if undefined:
	   if ( not defined $period_uncertainty ) {
	       $period_uncertainty = 0;
	   }
	   if ( not defined $epoch_uncertainty ) {
	       $epoch_uncertainty = 0;
	   }
           # Input uncertainties are in days; add in quadrature and
	   # convert to hours: 
           $midtime_uncertainty_hours = 24. * sqrt($epoch_uncertainty**2 +
               (($n_period_int + $eclipse_iteration)*$period_uncertainty)**2); 
           # There are some cases where we have very stale
	   # ephemerides, so the numbers from the above calculation
	   # can get quite big.  But it's not meaningful for the
	   # uncertainty to be bigger than half the period (since then
	   # it covers the next event), so limit it here:
           if ($midtime_uncertainty_hours > ($period * 0.5 * 24)) {
               $midtime_uncertainty_hours =  $period * 0.5 * 24;
           }

	   $midtime_uncertainty_duration = hours_to_duration($midtime_uncertainty_hours); 

           # And get a string to print out, HH:MM: 
           $midtime_uncertainty_string = sprintf("%d:%02.0f",
                                                  int($midtime_uncertainty_hours), 
              60 * ($midtime_uncertainty_hours - int($midtime_uncertainty_hours))); 
        } else {
	   $midtime_uncertainty_duration = hours_to_duration(0); 
	   $midtime_uncertainty_hours = 0;
	}

	# If a non-zero baseline is requested, also calculate relevant quantities 
	# at those points.  Initialize all first: 
	my ($az_pre, $az_post, $el_pre, $el_post, 
	    $ha_pre, $ha_post, $pre_time, $post_time,
	    $pre_time_UTC, $post_time_UTC,
	    $pre_date_UTC, $post_date_UTC,
	    $is_daytime_pre, $is_daytime_post,
	    $is_observable_pre, $is_observable_post,
	    $is_observable_baseline) = (0) x 17;  

	my $dt_pre = $dt_start - $baseline_duration;
	my $dt_post = $dt_end + $baseline_duration;
	if ($show_unc) {
	    $dt_pre = $dt_pre - $midtime_uncertainty_duration;
	    $dt_post = $dt_post + $midtime_uncertainty_duration;
	}
	    
	if (($baseline_hrs > 0) or $show_unc) {
	    $target->datetime($dt_pre);
	    $az_pre = $target->az(format=>'deg');
	    $el_pre = $target->el(format=>'deg');
	    $ha_pre = $target->ha(format=>'hour');
	    $target->datetime($dt_post);
	    $az_post = $target->az(format=>'deg');
	    $el_post = $target->el(format=>'deg');
	    $ha_post = $target->ha(format=>'hour');
	    $sun->datetime($dt_pre);
	    $is_daytime_pre   = ( $sun->el(format=>'rad') > $twilight_rad );
	    $sun->datetime($dt_post);
	    $is_daytime_post   = ( $sun->el(format=>'rad') > $twilight_rad );
	    $pre_time_UTC = $dt_pre->hm;
	    $pre_date_UTC = $dt_pre->ymd;
	    $post_time_UTC = $dt_post->hm;
	    $post_date_UTC = $dt_post->ymd;
	    $dt_pre->set_time_zone($observatory_timezone);
	    $dt_post->set_time_zone($observatory_timezone);
	    $pre_time = $dt_pre->hm;
	    $post_time = $dt_post->hm;

	    # Find observability, including baseline constraints: 
	    $is_observable_pre = ($start_is_observable and 
				  (not $is_daytime_pre) and 
				  ($el_pre >= $minimum_start_elevation) and 
				  ($ha_pre >= $minimum_ha) and 
				  ($ha_pre <= $maximum_ha) and 
				  ($dt_pre > $previous_sunset));

	    $is_observable_post = ($end_is_observable and 
				   (not $is_daytime_post) and 
				   ($el_post >= $minimum_end_elevation) and 
				   ($ha_post >= $minimum_ha) and 
				   ($ha_post <= $maximum_ha) and 
				   ($dt_post < $next_sunrise));

	    $is_observable_baseline = eval("\$is_observable_pre $and_vs_or \$is_observable_post");
	}

        # Find the times when we can actually start or end observing, 
        # given the constraints.


	# Get the correct local sunset date for the eclipse.  We know
	# at this point that part of the eclipse is observable, so 
	# if it's the ingress, we use the sunset before that.  If
	# that's not observable, then the egress must be, so we use 
	# the sunset before *that* instead. 

	my ($sunrise_object, $sunset_object);
	if ($start_is_observable) {
	  # Find previous sunset for ingress:
	  $sunset_object = $sunsets->previous($dt_start)->clone;
	} else {
	  # Find previous sunset for egress:
	  $sunset_object = $sunsets->previous($dt_end)->clone;
	}

        # Once we have the desired sunset, then we always
        # want the sunrise that follows: 
        $sunrise_object = $sunrises->next($sunset_object)->clone;


	# If ingress is observable, we'll tack on some previous
        # baseline to see how much more we can observe.  If not, we
        # just search forward from ingress.
	# Minimum value allowed here is 30 minutes or 0.5 hours: 
	my $desired_baseline = max ($baseline_hrs + $midtime_uncertainty_hours, 0.5);

	my $max_baseline = $start_is_observable ? $desired_baseline : 0;

	# Find the earliest observable time, given desired baseline:
	my $obs_start_time;
	if ($observing_from_space) {
	    $obs_start_time = $dt_start -
		hours_to_duration($desired_baseline);
	} else {
	    # If the nominal start time (ingress) for our search is 
	    # before the night starts, then start search from sunset
	    # of the relevant night instead.  This can save time
	    # in typical cases, but is also essential for correctly
	    # handling very-long-transit cases to make sure we 
	    # aren't inadvertently searching in the wrong night. 
	    my $search_start = ($dt_start > $sunset_object) ? $dt_start : $sunset_object;
	    
	    $obs_start_time = 
		observable_time({
		    target => $target, 
		    name => $name,
		    start_time => $search_start, 
		    max_time => $dt_end,
		    max_baseline => $max_baseline,
		    minimum_elevation =>  $minimum_start_elevation,
		    alt_min_elevation =>  $minimum_end_elevation,
		    minimum_ha => $minimum_ha,
		    maximum_ha => $maximum_ha,
		    sun => $sun,
		    is_daytime_start => $is_daytime_start,
		    is_daytime_end => $is_daytime_end,
		    twilight_rad => $twilight_rad,
		    backward => 0,
		    time_step_minutes => 1,
				}
		);
	}

	# Same logic for egress.  Here we also want to be careful of
	# the very-long-transit cases, so we check to make sure that
	# we are staying within the same night, and not inadverently
	# getting an end time that is in the *following* night. 

	my $search_end_time = $dt_end;
	my $daytime_end_flag = $is_daytime_end;
	# But if the end happens to be after the sun rises, start the
	# search earlier: 
	if ($dt_end > $sunrise_object) {
	    $search_end_time = $sunrise_object;
	    # We also tweak this flag for whether it is daytime at the
	    # end; nominally this applies to the egress time, but here
	    # we want to signal that no matter where the egress is
	    # (e.g. in the next night) that we won't be able to
	    # observe it.  Setting this daytime end flag will force
	    # it to search only within the current night, without
	    # influencing the color-coding of the actual end time: 
	    $daytime_end_flag = 1;
	    $end_is_observable = 0;
	}

	$max_baseline = $end_is_observable ? $desired_baseline : 0;

	my $obs_end_time;
	if ($observing_from_space) {
	    $obs_end_time = $dt_end +
		hours_to_duration($desired_baseline);
	    $start_is_observable = 1;
	    $end_is_observable = 1;
	    $mid_is_observable = 1;
	    $is_observable_pre = 1;
	    $is_observable_post = 1;
	    $is_observable_baseline = 1;
	} else {
	    $obs_end_time = 
		observable_time({
		    target => $target, 
		    name => $name,
		    start_time => $search_end_time, 
		    max_time => $dt_start,
		    max_baseline => $max_baseline,
		    minimum_elevation =>  $minimum_end_elevation,
		    alt_min_elevation =>  $minimum_start_elevation,
		    minimum_ha => $minimum_ha,
		    maximum_ha => $maximum_ha,
		    sun => $sun,
		    is_daytime_start => $is_daytime_start,
		    is_daytime_end => $daytime_end_flag,
		    twilight_rad => $twilight_rad,
		    backward => 1,
				}
		);
	}

	# If the user specified unequal elevation limits, we can get
	# odd behavior in calculating start and end times since it can
	# be ambiguous how to handle a target that meets one limit but
	# never meets the other - clean up some edge cases here.
	if (($minimum_start_elevation != $minimum_end_elevation) and
	    (not $observing_from_space)) {
	    if ((not $start_is_observable) and
		($obs_start_time < $dt_start)) {
		# Push start time to just after ingress:
		$obs_start_time = $dt_start->clone();
		$obs_start_time->add(minutes => 1);
	    }

	    if ((not $end_is_observable) and
		($obs_end_time > $dt_end)) {
		# Push end time to just before egress:
		$obs_end_time = $dt_end->clone();
		$obs_end_time->subtract(minutes => 1);
	    }
	}

	# Catch a particular edge case, where a circumpolar target
	# transits under the pole, but start and end are observable.
	# If the user has set any hour angle limits at all, then they
	# will necessarily be violated somewhere in the observable
	# interval in this case, so skip this event.  In principle we
	# could try to slice up the event to show only the time on
	# either side of the lower meridian, but the logic of that
	# gets complicated pretty fast, so for now just skip these
	# events.  See refine_ha_limits routine for a start at how to
	# parse this out, but using that output would require more
	# code here to re-check everything at the changed times.

	if ( (($minimum_ha > -12) or ($maximum_ha < 12)) and
	     (not $observing_from_space)) {
	    # Some HA limits are set, check this:
	    $target->datetime($obs_start_time);
	    my $ha_obs_start = $target->ha(format=>'hour');
	    $target->datetime($obs_end_time);
	    my $ha_obs_end = $target->ha(format=>'hour');

	    if (($ha_obs_start > 0) and ($ha_obs_end < 0)) {
		# Target crosses lower meridian, must violate HA
		# limits at some point:
		next ECLIPSE_LOOP;
	    }
	}

	# Save this as JD for passing to ACP script:
	my $obs_end_jd = DateTime::Format::Epoch::JD->
	    format_datetime($obs_end_time);


	# Get the amount and fraction of the transit that is
	# observable with the given constraints:
	my ($transit_fraction, $transit_observable_hrs);

	if ($start_is_observable and $end_is_observable) {
	    $transit_fraction = 100;
            $transit_observable_hrs = $eclipse_width;
	} elsif ($start_is_observable) {
            $transit_observable_hrs = $obs_end_time->
				     subtract_datetime_absolute($dt_start)->seconds()/3600.;
	    $transit_fraction = 100*$transit_observable_hrs/$eclipse_width;
	} else {
	    $transit_observable_hrs = $dt_end->
				     subtract_datetime_absolute($obs_start_time)->seconds()/3600;
	    $transit_fraction = 100*$transit_observable_hrs/$eclipse_width;
	}

	if (not $use_utc) {
	    $obs_start_time->set_time_zone($observatory_timezone);
	    $obs_end_time->set_time_zone($observatory_timezone);
	}

	# Also find the fraction of desired OOT baseline that is
	# observable.  We allocate 50% each to pre-ingress and
	# post-egress baseline: 
	my $baseline_fraction = 0;
        # Amount of pre- and post-transit baseline observable, in hours:
        my $baseline_pre_hrs = 0;
        my $baseline_post_hrs = 0;

	if ($obs_start_time <= $dt_start) {
            $baseline_pre_hrs = $dt_start->
				     subtract_datetime_absolute($obs_start_time)->seconds()/3600.; 
	    $baseline_fraction += 50*$baseline_pre_hrs/$desired_baseline;
	}	    

	if ($obs_end_time >= $dt_end) {
            $baseline_post_hrs = $obs_end_time->
				     subtract_datetime_absolute($dt_end)->seconds()/3600.;
	    $baseline_fraction += 50*$baseline_post_hrs/$desired_baseline;
	}	    

	# Make up a hash with all the bits of info, to return:
	my %eclipse;

	# SVG tags for displaying the transit.  We want everything in
	# decimal hours, passed in relative to ingress: 

        my $svg_path = "";

        unless ($observing_from_space) {
	   # Get the full-transit path to stroke in a lighter color: 
           $svg_path .= transit_svg({ start => -$desired_baseline, 
		  		      end => $eclipse_width + $desired_baseline,        
				      egress => ($dt_end -
						     $dt_start)->to_hrs,        
				      depth => $depth,
				      desired_baseline => $desired_baseline, 
				      class => 'grey',
				     }); 
        }

        # Draw the observable part of the transit in a different
        # color:
        $svg_path .= transit_svg({ start => ($obs_start_time -
					         $dt_start)->to_hrs, 
				   end => ($obs_end_time -
					           $dt_start)->to_hrs,        
				   egress => ($dt_end -
					              $dt_start)->to_hrs,        
				   depth => $depth,
				   desired_baseline =>
				                    $desired_baseline, 
				   class => 'active',
				  }); 

	# Also get information about the moon phase and distance from
	# our target, at mid-transit time: 
	$moon->datetime($dt);
	$sun->datetime($dt);
	$target->datetime($dt);

	my ($ra_moon, $dec_moon) = $moon->radec; 
	my ($ra_sun, $dec_sun) = $sun->radec; 
	my ($ra_target, $dec_target) = $target->radec;

	# Moon illumination formula from Meeus, "Astronomical
	# Algorithms".  Formulae 46.1 and 46.2 in the 1991 edition,
	# using the approximation cos(psi) \approx -cos(i).  Error
	# should be no more than 0.0014 (p. 316).

	my $moon_illum =  0.5 * (1. - sin($dec_sun)*sin($dec_moon) -
				 cos($dec_sun)*cos($dec_moon)*
				 cos($ra_sun - $ra_moon));

	my $moon_distance_deg = palDsep($ra_moon, $dec_moon, 
					$ra_target, $dec_target) * DR2D; 


	# Get the *local* date and day of week of the sunset
	# at the start of the night of this eclipse.  This is
	# not necessarily the date of the local sunset when
	# converted to the desired timezone, e.g. the user
	# could be requesting output in UTC, but be located in
	# the western United States, so the UT date at the
	# start of the night could already be one day ahead of
	# the local evening date.  So we can't rely on the
	# timezone specified by the user. Instead, we use the
	# longitude to determine a roughly-correct offset from
	# UTC, and use that timezone for determining the local
	# evening date.  Note that this approximate timezone was
	# already calculated above to specify the correct local start
	# date. 


	# Before shifting timezones, grab the UT dates of 
	# sunset and sunrise; useful for some observers in 
	# scheduling:
	my $sunset_time_UTC =  sprintf("%02d:%02d",
				   $sunset_object->hour,
				   $sunset_object->minute);

	my $sunset_UTC_datetime = sprintf("%s %s",
				      $sunset_object->ymd, 
				      $sunset_time_UTC);

	my $sunrise_time_UTC =  sprintf("%02d:%02d",
				   $sunrise_object->hour,
				   $sunrise_object->minute);

	my $sunrise_UTC_datetime = sprintf("%s %s",
				      $sunrise_object->ymd, 
				      $sunrise_time_UTC);

	# Now that we have the right sunset, we can set it to
	# our shifted timezone and find the date associated
	# with it:
	$sunset_object->set_time_zone($observatory_timezone);

	# Get the local date of sunset in this local
	# timezone.  First string is for table cell display, 
	# second and third are for other labels. 
	my $sunset_local_string = $sunset_object->day_abbr . ". " .
	                          $sunset_object->ymd;

	my $sunset_time_local =  sprintf("%02d:%02d",
				   $sunset_object->hour,
				   $sunset_object->minute);

	my $sunset_local_datetime = sprintf("%s %s",
				      $sunset_object->ymd, 
				      $sunset_time_local);


	# Same for sunrise: 
	$sunrise_object->set_time_zone($observatory_timezone);

	my $sunrise_local_string = $sunrise_object->day_abbr . ". " .
	                          $sunrise_object->ymd;

	my $sunrise_time_local =  sprintf("%02d:%02d",
				   $sunrise_object->hour,
				   $sunrise_object->minute);

	my $sunrise_local_datetime = sprintf("%s %s",
				      $sunrise_object->ymd, 
				      $sunrise_time_local);


	# Save the JD of sunset so we know which night we're
	# referring to, e.g. for an eclipse that just barely
	# starts before dawn and so might have the
	# *following* day's sunset closest to its midpoint:
	my $sunset_jd = DateTime::Format::Epoch::JD->
	  format_datetime($sunset_object);


	# Now get some other assorted dates and times that are
	# used in the output.  We store them both in UTC and
	# in the local timezone:

	my $start_time_UTC = ($dt - $eclipse_half_duration)->hm;
	my $mid_time_UTC = $dt->hm;
	my $end_time_UTC = ($dt + $eclipse_half_duration)->hm;
	
	$dt->set_time_zone($observatory_timezone);
	my $local_time = $dt->hm;
	my $local_date = $dt->ymd;


	# String for printing the duration:
	my $eclipse_duration_string = hours_to_hm($eclipse_width);

	# Now find times of the start and end of eclipse:
	# DateTime objects for start and end:
	my $dt_start_local = $dt - $eclipse_half_duration;
	my $dt_end_local = $dt + $eclipse_half_duration;
	$dt_start_local->set_time_zone($observatory_timezone);
	$dt_end_local->set_time_zone($observatory_timezone);

	my $local_date_start = $dt_start_local->ymd;
	my $local_time_start = $dt_start_local->hm;
	my $local_date_end = $dt_end_local->ymd;
	my $local_time_end = $dt_end_local->hm;

	# Flag conditions where the eclipse starts before sunset, or
	# ends after sunrise:
	$eclipse{ends_after_sunrise} = $is_daytime_end;
	$eclipse{starts_before_sunset} = $is_daytime_start;
	$eclipse{middle_in_daytime} = $is_daytime_mid;

	$eclipse{name} = $name;
	$eclipse{vmag} = $vmag;
	$eclipse{sunset_jd} = $sunset_jd;
	$eclipse{jd} = $eclipse_jd;
	# For these start/end times, to save space in the output we take off
	# 2,450,000 from the values, i.e. output = JD - 2450000

	$eclipse{jd_start} = sprintf("%0.3f", $ingress_jd
				     - 2450000);
	$eclipse{jd_end} = sprintf("%0.3f", $egress_jd
				   - 2450000);
	$eclipse{jd_mid} = sprintf("%0.3f", $eclipse_jd
				   - 2450000);
        
        # Same thing, except for the BJD values.
	$eclipse{bjd_start} = sprintf("%0.4f", $eclipse_bjd -
                                      $eclipse_half_dur_days - 2450000);

	$eclipse{bjd_mid} = sprintf("%0.4f", $eclipse_bjd - 2450000);

	$eclipse{bjd_end} = sprintf("%0.4f", $eclipse_bjd +
                                    $eclipse_half_dur_days - 2450000);



	$eclipse{obs_end_jd} = sprintf("%0.3f", $obs_end_jd
				   - 2450000);
        
	$eclipse{start_time} = $local_time_start;
	$eclipse{start_time_UTC} = $start_time_UTC;
	$eclipse{start_az} = sprintf("%0.0f",$az_start_deg);
	$eclipse{start_el} = sprintf("%02.0f",$el_start_deg);
	$eclipse{start_ha} = sprintf("%+04.1f",$ha_start);
	$eclipse{start_date} = $local_date_start;
	$eclipse{start_date_UTC} = $start_date_utc;
	$eclipse{mid_time} = $local_time;
	$eclipse{mid_time_UTC} = $mid_time_UTC;
	$eclipse{mid_az} = sprintf("%0.0f",$az_mid_deg);
	$eclipse{mid_el} = sprintf("%02.0f",$el_mid_deg);
	$eclipse{mid_ha} = sprintf("%+04.1f",$ha_mid);
	$eclipse{mid_date} = $local_date;
	$eclipse{mid_date_UTC} = $mid_date_utc;
	$eclipse{end_time} = $local_time_end;
	$eclipse{end_time_UTC} = $end_time_UTC;
	$eclipse{end_az} = sprintf("%0.0f",$az_end_deg);
	$eclipse{end_el} = sprintf("%02.0f",$el_end_deg);
	$eclipse{end_ha} = sprintf("%+04.1f",$ha_end);
	$eclipse{end_date} = $local_date_end;
	$eclipse{end_date_UTC} = $end_date_utc;
        $eclipse{time_unc} = $midtime_uncertainty_string;
	$eclipse{sunrise_time_local} = $sunrise_time_local;
	$eclipse{sunset_time_local} = $sunset_time_local;
	$eclipse{sunset_local_datetime} = $sunset_local_datetime;
	$eclipse{sunrise_local_datetime} = $sunrise_local_datetime;
	$eclipse{sunset_local_string} = $sunset_local_string;
	$eclipse{sunrise_time_UTC} = $sunrise_time_UTC;
	$eclipse{sunset_time_UTC} = $sunset_time_UTC;
	$eclipse{sunset_UTC_datetime} = $sunset_UTC_datetime;
	$eclipse{sunrise_UTC_datetime} = $sunrise_UTC_datetime;
	$eclipse{moon_illum} = sprintf("%0.0f", $moon_illum*100); 
        if ($moon_distance_deg < 1) {
	   $eclipse{moon_dist} = sprintf("%0.1f", $moon_distance_deg); 
        } else {
	   $eclipse{moon_dist} = sprintf("%0.0f", $moon_distance_deg); 
        }
        # An arbitary measure of moon fullness and angular distance, 
        # used for highlight problematic cases in the output: 
        $eclipse{moon_metric} = 100*$moon_illum + 1000/$moon_distance_deg;
	$eclipse{coords} = $ra_string . " " . $dec_string;
	$eclipse{ra} = $ra_string;
	$eclipse{dec} = $dec_string;
	$eclipse{ra_deg} = sprintf("%0.5f", $ra_deg);
	$eclipse{dec_deg} = sprintf("%0.5f", $dec_deg);
	$eclipse{comments} = $comments;
	$eclipse{priority} = $priority;
        $eclipse{period} = sprintf("%0.2f",$period);
        # Above is nicely-formatted period; below is full period to
	# whatever precision we know it, for CSV output for scripting: 
        $eclipse{period_raw} = $period;
        $eclipse{period_unc} = $period_uncertainty;
        $eclipse{epoch} = $epoch;
        $eclipse{epoch_unc} = $epoch_uncertainty;
	$eclipse{depth} = $depth;
	$eclipse{duration} = $eclipse_duration_string;
	$eclipse{duration_hrs} = $eclipse_width;
        if (defined($param_ref->{duration_uncertainty})) {
	   $eclipse{duration_unc} = 
               hours_to_hm($param_ref->{duration_uncertainty}); 
	   $eclipse{duration_unc_hrs} =
               $param_ref->{duration_uncertainty};
        }

        # Fill in all the variables related to baseline: 
	$eclipse{baseline_hrs} = $show_unc ? 
                                   sprintf("%0.1f", $baseline_hrs + $midtime_uncertainty_hours) : 
                                   sprintf("%0.1f", $baseline_hrs);
	$eclipse{az_pre} = sprintf("%0.0f", $az_pre);
        $eclipse{az_post} = sprintf("%0.0f", $az_post);
        $eclipse{el_pre} = sprintf("%0.0f", $el_pre);
        $eclipse{el_post} = sprintf("%0.0f", $el_post);
        $eclipse{ha_pre} = sprintf("%+0.1f", $ha_pre);
        $eclipse{ha_post} = sprintf("%+0.1f", $ha_post); 
        $eclipse{pre_time} = $pre_time;
        $eclipse{post_time} = $post_time; 
        $eclipse{pre_time_UTC} = $pre_time_UTC;
        $eclipse{pre_date_UTC} = $pre_date_UTC;
        $eclipse{post_time_UTC} = $post_time_UTC; 
        $eclipse{post_date_UTC} = $post_date_UTC; 
        $eclipse{is_daytime_pre} = $is_daytime_pre; 
        $eclipse{is_daytime_post} = $is_daytime_post; 
        $eclipse{is_observable_baseline} = $is_observable_baseline; 
        $eclipse{mid_is_observable} = $mid_is_observable; 

        $eclipse{obs_start_time} = $obs_start_time->hm;
        $eclipse{obs_end_time} = $obs_end_time->hm;
        $eclipse{transit_fraction} = sprintf("%0.0f", $transit_fraction);  
        $eclipse{baseline_fraction} = sprintf("%0.0f", $baseline_fraction);  
        $eclipse{svg_path} = $svg_path;

        $obs_start_time->set_time_zone('UTC');
        $eclipse{obs_start_utc} = sprintf("%s %s",
				       $obs_start_time->ymd, 
				       $obs_start_time->hm);
        $eclipse{obs_start_jd} = sprintf("%0.4f", 
             DateTime::Format::Epoch::JD->format_datetime($obs_start_time) - 2450000);


        $obs_end_time->set_time_zone('UTC');
        $eclipse{obs_end_utc} = sprintf("%s %s",
				       $obs_end_time->ymd, 
				       $obs_end_time->hm);
        $eclipse{obs_end_jd} = sprintf("%0.4f", 
             DateTime::Format::Epoch::JD->format_datetime($obs_end_time) - 2450000);


        $eclipse{single_object} = $single_object;
        $eclipse{tess} = $tess;
        $eclipse{priority} = $param_ref->{"priority"};
        if ($tess) {
           $eclipse{disposition} = $param_ref->{"disposition"};
           $eclipse{toi} = $param_ref->{"TOI"};
        }

        # Call the subroutine that constructs a URL for a 
        # unique page about this target; it will be linked 
        # on the output page if defined. 
	($eclipse{target_page}, $eclipse{target_page_label}) 
              = target_info_page(\%eclipse);

        # Call the subroutine that constructs a URL for a 
        # finding chart for this target; it will be linked 
        # on the output page if defined. 
	$eclipse{finding_chart} = finding_chart_page(\%eclipse);

	# If we are printing CSV output for import into a
	# calendar rather than printing HTML, we want to
	# create a title and note for the calendar entry that
	# given helpful descriptive info in a modest amount of
	# space:

        $eclipse{csv_text} = eclipse_csv_entry(\%eclipse);

	push(@local_eclipse_times, $eclipse_jd);
	push(@local_eclipse_info, \%eclipse);



      } # End block for eclipse being visible
    } # End of block for eclipse being at night
  } # End of while block ECLIPSE_LOOP

  return \@local_eclipse_times, \@local_eclipse_info;

} # End subroutine get_eclipses



sub get_observability {

  # This subroutine takes as input various parameters that describe
  # one particular target (name, coordinates, magnitude), its
  # ephemeris (zero point, period, depth and time width of transit),
  # and observing circumstances (latitude, longitude, timezone,
  # time/date window to consider).  It then calculates the events
  # occurring during the specified time window for that target, and
  # determines whether or not these will be observable (or partially
  # observable) given the input constraints.  Information about any
  # observable events is returned in the form of references to arrays
  # of event information; see end of subroutine for details on what is
  # returned.  Note: returned array references may be to empty arrays,
  # i.e. there may be no observable events for a particular target.

  # First, unpack the input parameters; these are passed in a hash so
  # that they can be identified by name, i.e. it's not necessary to
  # pass them in in any particular order.

  my ($param_ref) = @_;
  my $ra_string = $param_ref->{ra_string};
  my $dec_string = $param_ref->{dec_string};
  my $name = $param_ref->{name};
  my $observatory_timezone = $param_ref->{observatory_timezone};
  my $comments = $param_ref->{comments};
  my $priority = $param_ref->{priority};
  my $sunsets = $param_ref->{sunsets};
  my $sunrises = $param_ref->{sunrises};
  my $telescope = $param_ref->{telescope};
  my $debug = $param_ref->{debug};
  my $base_date = $param_ref->{base_date};


  my $target = new Astro::Coords( ra => $ra_string,
				  dec => $dec_string,
				  type => 'J2000',
				  units => 'sexagesimal',
      );

  $target->telescope($telescope);


  # Set the start and end time of the upcoming night - start at the
  # sunset following our base time, and end at the sunrise after that: 
  my $current_time = $sunsets->next($base_date)->clone;
  my $end_time = $sunrises->next($current_time)->clone;
  $current_time->set_time_zone('UTC');
  $end_time->set_time_zone('UTC');
  my $sunset_jd 
      = DateTime::Format::Epoch::JD->format_datetime($current_time);

  # We will loop over times to find the max elevation of the target
  # during the night:
  my $max_target_elevation = -1000;
  my ($max_elevation_time, $elevation); 

  while ($current_time < $end_time) {      
      # Get elevations at the relevant times: 
      $target->datetime($current_time);
      $elevation = $target->el(format=>'deg');
      if ($elevation > $max_target_elevation) {
	  $max_target_elevation = $elevation;
	  $max_elevation_time = $current_time->clone;
      }
      $current_time->add(minutes => 10);
  }
  

  # To be shown as an observable target, the target has to be above a
  # minimum elevation at some point during the night.  If it is
  # observable, we will put a reference to its hash into a list, and
  # return a reference to that one-element list.  Otherwise, we return
  # a reference to an empty list.

  my @return_vals = ();
  if ( $max_target_elevation >= 10 ) {
      # Make a clone of the input parameters, which we will return
      # with just a few more fields added:
      my %info = %$param_ref;
      $info{max_elevation} = sprintf("%0.0f",$max_target_elevation);
      my $timezone_to_display = $use_utc ? 'UTC' : $observatory_timezone;
      $max_elevation_time->set_time_zone($timezone_to_display);
      $info{max_elevation_time} = $max_elevation_time->hm;
      # Get the JD also, for easier sorting;
      $info{max_elevation_jd} 
         = DateTime::Format::Epoch::JD->format_datetime($max_elevation_time);
      $info{sunset_jd} = $sunset_jd;
      # Call the subroutine that constructs a URL for a 
      # unique page about this target; it will be linked 
      # on the output page if defined. 
      ($info{target_page}, $info{target_page_label}) = target_info_page(\%info);
      
      # Call the subroutine that constructs a URL for a 
      # finding chart for this target; it will be linked 
      # on the output page if defined. 
      $info{finding_chart} = finding_chart_page(\%info);
      $info{coords} = $ra_string . " " . $dec_string;
      $info{ra} = $ra_string;
      $info{dec} = $dec_string;
      push @return_vals, \%info;
  }

  return \@return_vals;

}  # End of sub get_observability


sub fatal_error {

  # Simple routine to just let us write the error message in one place
  # so it can be easily modified.  Input parameter is the specific
  # message to print; this is followed by more general text that can
  # be customized.

  my ($message) = @_;
  print "The program generated the following error:"; 
  print "<pre> $message </pre>";
  print "Please contact $script_contact_person"
	      . " with this error.";
  die $message;
}

sub eclipse_csv_entry {

    # Given input information about a transit or eclipse, construct a
    # comma-separated string that conforms to the specification for
    # import of a calendar event into Google Calendar, following the
    # format for Google cal CSV entries at
    # http://www.google.com/support/calendar/bin/answer.py?answer=45656

    # In addition to the start/end times and dates, we also construct
    # a string with elevation, magnitude, etc.  This string is used in
    # the "Notes" field of the calendar when imported.

    # Input: a hash reference to the hash with all the different
    # fields of information about this particular target (e.g. name,
    # coords, etc.) which can be used to construct the string.
    # Output: returns a CSV string used in the calendar.  The string
    # should end with "\n" so that each eclipse prints on a separate
    # line. 

    my $target_ref = shift @_;
    # Convert the hash reference to a local hash:
    my %t = %$target_ref;

    # Create the basic comma-separated entry for the calendar, with
    # label, start date and time, end date and time, and a field
    # denoting that it is not an all-day event:
    my $eclipse_entry = "Transit of $t{name},$t{start_date},"
	. "$t{start_time},$t{end_date},$t{end_time},FALSE,";

    # And also construct some notes that will appear in the
    # Description field of the calendar entry:
    my $note = "Transit of $t{name}; $t{ra} $t{dec};";
    $note .= " Elev. at start, mid, end: "
	. "$t{start_el}, $t{mid_el}, $t{end_el}. ";
    chomp($t{comments});
    if ($t{comments} !~ /^\s*$/) { # Comment not empty
	$note .= "Notes: $t{comments}";
	# Add a trailing period if not there already:
	if ($note !~ /\s*\.\s*$/) {
	    $note .= ". ";
	}
    }
    if (defined $t{finding_chart}) {
	# To get the current path in order to make the finding chart
	# URL absolute, we need the full URL, minus the script name
	# itself:
	my $url = CGI::url( -full => 1);
	my $script = CGI::url( -relative => 1);
	$url =~ s/$script$//;
	$note .= "Finding chart at ${url}$t{finding_chart}.";
    }

    # The CSV standard says that double quotes embedded within a
    # quoted field need to be doubled up so they aren't interpreted as
    # the end of the field:
    $note =~ s/\"/\"\"/g;

    # Add the note to the final entry.  It needs to be enclosed in
    # double quotes, or any embedded commas will be interpreted as
    # field separators:
    $eclipse_entry .= '"' . $note . '"' . "\r\n";

    return $eclipse_entry;
    
}

    

sub target_info_page {

    # Given input information about a target, construct the URL of a
    # page that will be listed in the output where a user can find
    # more info, e.g. a candidate information page for a large survey,
    # or a catalog entry of some kind.  If the return value is
    # undefined, nothing appears in the output.

    # Input: a hash reference to the hash with all the different
    # fields of information about this particular target (e.g. name,
    # coords, etc.) which can be used to construct the URL.

    # Output: two strings.  The first is the URL of the page; the
    # second is the label to be displayed as the link text in the
    # output.   If the first is undefined, nothing is displayed in the
    # output. 

    my $target_ref = shift @_;

    # Use the target name to construct the URL of the page
    # with target info on it:
    my $name = $target_ref->{name};
    # Replace spaces with underscores:
    #$name =~ s/\s+/_/g;
    my ($target_page_url, $target_page_label);

    if (($target_ref->{tess}) and ($name =~ m/TIC (\d+)(\.\d+)? ?/)) {
	# Then use back-references to those matches to make the URL:
	$target_page_url = "https://exofop.ipac.caltech.edu/tess/target.php?id=$1";
	$target_page_label = "ExoFOP";
    } else {
	$target_page_url = "https://exoplanetarchive.ipac.caltech.edu/cgi-bin/DisplayOverview/nph-DisplayOverview?objname=$name";
	$target_page_label = "Exoplanet Archive";
    }
    

    return $target_page_url, $target_page_label;
}

sub finding_chart_page {

    # Given input information about a target, construct the URL of a
    # finding chart page or image that will be listed in the
    # output. If the return value is undefined, nothing appears in the
    # output.

    # Input: a hash reference to the hash with all the different
    # fields of information about this particular target (e.g. name,
    # coords, etc.) which can be used to construct the URL.

    my $target_ref = shift @_;

    # Use the target name to construct the URL of the page
    # with the finding chart.  If we are running the script
    # with just a single object as input, presumably we
    # do not already have a finding chart for it, so 
    # we create a custom link to generate one on the fly:

    my $chart_url;
    my $name = $target_ref->{name};
    if ($target_ref->{single_object}==1) {
	$chart_url = "/create_finding_chart.cgi?"
	    . "target=$name"
	    . "&ra=$target_ref->{ra}"
	    . "&dec=$target_ref->{dec}";
    } else {
	# Remove TOI info if present: 
	$name =~ s/ *\(TOI [\d\.]+\) *//;
	# Replace spaces, slashes, and parens with underscores:
	$name =~ s%[ \s / \( \) ]+%_%g;
	# Make sure no underscores at the end of the name:
	$name =~ s/_+$//;
	$chart_url = "finding_charts/$name.jpg";
    }
    return $chart_url;
}

sub hours_to_duration {

# Takes as input a (possibly non-integer) number of hours, and returns
# a DateTime::Duration object.  To create this, we need to find the
# equivalent integer number of hours, minutes, and seconds.  The
# seconds value is rounded to the nearest integer.  These integers
# are useful for initializing DateTime objects, which require integer
# inputs for all arguments. 

    my $float_hours = shift @_; 

    my $float_minutes = 60.* ($float_hours - int($float_hours));
    my $float_seconds = 60.* ($float_minutes - int($float_minutes));

    # Initialize the duration object with the integer values, 
    # using sprintf to get rounding rather than truncation.  

    my $new_duration = DateTime::Duration->
	new(
	    hours =>   int($float_hours), 
	    minutes => int($float_minutes), 
	    seconds => sprintf("%0.0f", $float_seconds),
	);

    return $new_duration;

}

sub hours_to_hm {

# Takes a decimal number of hours and returns a string of the form
# h:mm or hh:mm, properly rounded to the nearest minute. 

    my $hrs = shift;
    my $h_int = int($hrs);

    my $min = 60*($hrs - $h_int);
    my $m_int = int($min);

    my $sec = 60*($min - $m_int);

    $m_int++ if ($sec >= 30); 

    # If rounding up crosses an hour boundary, handle that.
    if ($m_int == 60) {
	$m_int = 0;
	$h_int++;
    }
    return sprintf("%d:%02d", $h_int, $m_int);

}

sub observable_time {

# Find the earliest (or latest) observable time for a
# target, given a set of constraints. Overall goal is to find
# how much before ingress (or after egress) a target can be
# observed.  The same routine can be used for both cases, 
# by specifying whether to search forward or backward in 
# time from a specified starting point.  

# Note that this search is not foolproof.  It assumes that you are
# passing in the time of an event that is observable with the input
# constraints, and the question is only how far past that (in either
# direction) you can also observe. 

# The speed of the search can be increased by using coarser time
# steps, at the expense of precision of the time constraint
# returned. The time returned will always be observable, but for, say,
# a 10-minute time step it could be conservative by up to just shy of
# 10 minutes. It is only used for the hour angle constraint, not the
# daytime or elevation constraints. 

# Inputs:  Hash ref of input parameters:
#   max_baseline: baseline to try, in hours
#   start_time: DateTime object giving zero point for search, *not 
#      including baseline*.  (Typically ingress or egress time.)  So
#      we shift this by max_baseline to start the search. 
#   backward: if this flag is true, search back in time.
#   time_step_minutes:  Step size for hour angle search; others can be 
#      calculated directly. 
#   target, sun:  Astro::Coords instances for those bodies, containing
#      info about their coords, observing location, and time. 
#   twilight_rad:  Solar elevation in radians defining twilight. 
#   minimum_elevation:  elevation in degrees above which target is
#      considered observable. 
#   alt_min_elevation:  As above, but alternate elevation to search if
#     target never gets above minimum_elevation.  This is only relevant
#     when finding start and stop times for targets with asymmetric
#     limits.  During transit, either limit could apply. 
#   max_time: DateTime object, time beyond which returned time should
#     not extend.  This is used to keep pre-ingress limits from bleeding
#     over and returning post-ingress start times in the unequal limit
#     case.  If 'backward' is true, this is an *earliest* time limit.
#   minimum_ha, maximum_ha:  hour angle limits, in hours. 
#   name:  Target name - only used for informative error messages. 
#
# Returns: Datetime

    my $DEBUG = 0; 

    my ($args) = @_; 

    # Maximum baseline to consider relative to starting point; 
    # optional, defaults to 1 hour: 
    if (not defined($args->{'max_baseline'})) {
	$args->{'max_baseline'} = 1; 
    }

    my $sign;  # Direction to search 

    # Direction to search; optional, defaults to forward in time. 
    if ($args->{'backward'}) {  # Empty defaults to False
	$sign = -1;
    } else {
	$sign = 1;
    }

    # Make the requested baseline (amount by which we extend the start 
    # or end time) a duration, modified by direction we're going: 
    my $baseline = hours_to_duration($args->{'max_baseline'} * $sign); 

    # Get time increment: 
    my $time_step;
    if ((not defined($args->{'time_step_minutes'})) or
	 ($args->{'time_step_minutes'} <= 0)) {
	$time_step = 1;
    } else {
	$time_step = $args->{'time_step_minutes'};
    }

    my $inc = DateTime::Duration->new( minutes => $time_step * $sign); 

    # The start time for searching is the input time, modified by the
    # requested baseline time.  If the search direction is backward,
    # then $baseline will be a negative duration, meaning this logic
    # will extend the initial time (from which we'll search back).
    # Note that this start time for the search window may be modified
    # below, e.g. if it's not at night. 
    my $time = $args->{'start_time'} - $baseline;
    my $target = $args->{'target'};

    # Debugging
    my $search_start = $time;


    # Start with the constraint that our search window needs to be at
    # night, and to stay during the same night as the event of interest: 

    my $sun = $args->{'sun'};
    # Set sun to time of event, so we can check relevant
    # sunrise/sunset times, to keep search window in darkness: 
    $sun->datetime($args->{'start_time'});

    # In the block below, the sunrise or sunset times could be
    # undefined for sites near the poles.
    if ($sign == 1){
	if ($args->{'is_daytime_start'}) {
	    # Start searching as soon as it gets dark, i.e. at the 
	    # next sunset: 
	    my $next_sunset = $sun->set_time( horizon => 
					      $args->{'twilight_rad'});
	    $time = $next_sunset if (defined $next_sunset);
	} else {
	    # Start is in darkness, so find the previous sunset that starts the night:
	    my $start_of_night = $sun->set_time( horizon => 
						 $args->{'twilight_rad'}, 
						 event => -1);
	    # Start at the later of the start of night and the suggested 
	    # start window;
	    if ((defined $start_of_night) and 
		(DateTime->compare( $start_of_night, $time ) == 1)) {
		$time = $start_of_night;
	    }
	}
    } else {
	# Backward searching to set end time. 
	if ($args->{'is_daytime_end'}) {
	    # Start searching as soon as it gets dark (looking back),
	    # i.e. at the previous sunrise: 
	    my $previous_sunrise = $sun->rise_time( horizon => 
						    $args->{'twilight_rad'},
						    event => -1);
	    $time = $previous_sunrise if (defined $previous_sunrise);
	} else {
	    # Find the next sunrise that ends the night:
	    my $end_of_night = $sun->rise_time( horizon => 
						$args->{'twilight_rad'});
	    # Start at the earlier of the end of night and the suggested 
	    # start window:
	    if ((defined $end_of_night) and 
		(DateTime->compare( $time, $end_of_night ) == 1)) {
		$time = $end_of_night;
	    }
	}
    }

    if ($DEBUG) {
	$sun->datetime($time);
	my $temp_el =  $sun->el(format=>'deg'); 
	print "<br /> Sun elevation $temp_el at $time.\n"; 
    }

    $target->datetime($time);
    my $el =  $target->el(format=>'deg');

    # Now deal with elevation constraints.  We check the elevation and
    # if that's fine, we go on. If not, we find the time after that
    # (or prior to that) when it was at the limiting elevation:

    my $el_to_satisfy = $args->{'minimum_elevation'};

    if ($el < $args->{'minimum_elevation'}) {

	# If the target never reaches the desired elevation, these
	# routines will return an undefined value for time.  In that
	# case, we try an alternate elevation.  This can happen when
	# ingress and egress are given different elevation limits.
	# Typically we set start time by ingress limit and end time by
	# egress limit, but if one of these can't be reached, we use
	# the other.  If neither can be reached, this code should
	# never be called since the event is unobservable - this will
	# trigger an error on the elevation check below. 
	if ($sign == 1) {
	    # Next rise: 
	    my $new_time = $target->rise_time( horizon => 
					DD2R*$el_to_satisfy);
	    # Make sure we find a time, and it is not past the end of
	    # our search window: 
	    if (defined($new_time) and 
		(DateTime->compare($new_time, $args->{'max_time'}) != 1))
	    {
		# Found time to reach that limit, save it: 
		$time = $new_time;
	    } else {
		# Couldn't achieve that, check alternate limit:
		$el_to_satisfy = $args->{'alt_min_elevation'};
		if ($el < $el_to_satisfy) {
		    # Get rise time for this limit; when above "if"
		    # isn't true, we don't get in here and $time is
		    # unchanged since we've met the elev. limit. 
		    $time = $target->rise_time( horizon => 
						DD2R*$el_to_satisfy);
		}
	    }
	} else {
	    # Working backward, find previous set time: 
	    my $new_time = $target->set_time( horizon =>
				       DD2R*$el_to_satisfy, 
				       event => -1);
	    # Make sure we find a time, and it is not past the end of
	    # our search window: 
	    if (defined($new_time) and 
		(DateTime->compare($new_time, $args->{'max_time'}) != -1))
	    {
		# Found time to reach that limit, save it: 
		$time = $new_time;
	    } else {
		# Couldn't achieve that, check alternate limit:
		$el_to_satisfy = $args->{'alt_min_elevation'};
		if ($el < $el_to_satisfy) {
		    $time = $target->set_time( horizon =>
					       DD2R*$el_to_satisfy, 
					       event => -1);
		}
	    }
	}

	# The above should find a time as long as either ingress or
	# egress is observable, but if not, the error will be flagged
	# below. 

	$target->datetime($time);
	$el = $target->el(format=>'deg');
    }

    if ($DEBUG) {
	print "<br />El $el at $time.\n"; 
    }

    
    # Having gotten into the regime where elevation is OK, we now
    # satisfy the hour angle constraint:

    my $ha =  $target->ha(format=>'hour');
    while (($ha < $args->{'minimum_ha'}) or ($ha > $args->{'maximum_ha'})) {
	$time = $time + $inc;
	$target->datetime($time);
	$ha =  $target->ha(format=>'hour');
    }

    if ($DEBUG) {
	print "<br />HA $ha at $time.\n"; 
    }
    
    
    # Just to double-check, make sure the elevation is still
    # OK at the possibly-shifted time we've found:
    $target->datetime($time);
    $el =  $target->el(format=>'deg');

    # Check, but allow a little rounding error: 
    if ($el + 1 < $el_to_satisfy) {
	my $inc_string = $inc->in_units( 'minutes' );
	my $message = "Error with elevation calculation in sub observable_time" .
	    ". Elevation is $el at time $time. (HA $ha, start time" . 
	    " $args->{'start_time'} Inc $inc_string search start $search_start  \n";
	$message .= "Baseline $args->{'max_baseline'} Min elevation $args->{'minimum_elevation'}.\n"; 
	if (defined($args->{'name'})) {
	    $message .= "Target $args->{'name'}\n";
	}
	fatal_error($message);
    } elsif  (($ha < $args->{'minimum_ha'}) or ($ha > $args->{'maximum_ha'})) {
	my $message = "Error with hour angle calculation in sub observable_time" .
	    ". Hour angle is $ha at time $time.\n";
	fatal_error($message);
    }

    return $time; 
    
}

sub DateTime::hm {
  # Just a simple shortcut for formatting ease, since the 
  # DateTime package doesn't provide a built-in method for 
  # only hours and minutes.  This also rounds to the nearest minute,
  # rather than truncating. 
  my $dt = shift;
  my ($h,$m,$s) = split(/:/, $dt->hms()); 
  $m++ if ($s >= 30); 
  # If rounding up crosses an hour boundary, handle that.  However,
  # we do not round 23:59:30+ up to 00:00, since that causes issues
  # elsewhere in the code when we cross a date boundary but the hh:mm
  # and date may be getting passed separately.  So:
  if ($m == 60) {
      if ($h == 23) {
	  $m = 59; # Put it back where it was
      } else {
	  $m = 0;
	  $h++;
      }
  }
  return sprintf("%02d:%02d", $h, $m);
}


sub DateTime::Duration::to_hrs {
    # Given a DateTime::Duration object, return it in decimal hours.
    # Good only to the nearest second, and good only for durations
    # less than a month. 

    my $dur = shift; 

    my $sign = $dur->is_negative() ? -1 : 1;

    # These named methods always return positive numbers, 
    # so multiply sum by the sign: 
    return $sign * (($dur->weeks * 7 + $dur->days) * 24 + $dur->hours
		    + $dur->minutes/60. + $dur->seconds/3600.);

}



sub transit_svg {
    # Return an HTML SVG path that will depict the observable part of a
    # transit, including baseline. 


    # Inputs are three times in decimal hours, relative to the 
    # ingress time: 
    # start: start of the observable window (and thus the SVG trace)
    # egress
    # end: end of the observable window. 

    # It is always the case that start < end, and ingress < egress,
    # but the two pairs can be intermixed, e.g. we might not be able
    # to start observing until after ingress. 


    # Conversion factors from hours to pixels (for x), depth in ppt
    # to pixels (for y), and number of pixels to offset the y values 
    # from zero; adjust as needed:

    use constant { H2P_default => 150, # Horiz. hours-to-pix scale
		   D2P => 25,  # Depth ppt-to-pix scale
		   YTOP => 15, # Offset above
		   YHEIGHT => 540, # Y space available
		   XWIDTH => 1000,  # X space available
		   MINDEPTH => 0.5, # Scale shallow transits to at
				    # least this min depth 
		   MAXWIDTH => 5,  # Max duration hrs before trunc
    };

    my ($a) = @_; 

    # Assigning this to a variable since we may have to tweak it: 
    my $H2P = H2P_default; 

    # Shift reference point from ingress at zero, to maximum desired
    # baseline at zero for start of the plot: 

    # Since ingress was at zero, it now sits at baseline: 
    my $ingress =  $a->{'desired_baseline'}; 

    my ($start, $end, $egress) = 
	($a->{'start'} + $ingress, 
	 $a->{'end'} + $ingress,
	 $a->{'egress'} + $ingress,
	); 

    my $mid = $ingress + 0.5*($egress - $ingress); 

    # Check if duration too wide to show: 
    my $wide = ($egress - $ingress) > MAXWIDTH;

    if ($wide) {
	# Change the y scaling to make the whole transit fit; 
	# We'll flag this later with a hash mark:
	$H2P /= ($egress - $ingress) / MAXWIDTH;
    }    

    my $class = '';
    if (defined $a->{'class'}) {
	$class = 'class="' . $a->{'class'} . '"';
    }

    my $xstart = sprintf("%0.0f", $H2P * $start);
    my $xend = sprintf("%0.0f", $H2P * $end);
    my $ydepth = sprintf("%0.0f", D2P * max($a->{'depth'}, MINDEPTH)); 
    my $yzero = YTOP;

    # We always want the midpoint of the transit to sit at the
    # x-midpoint defined by the width XWIDTH, so transform as needed: 
    my $transform = sprintf("transform=\"translate(%0.0f)\"", 0.5*XWIDTH
			    - $mid*$H2P); 

    my $deep = 0;
    # Make sure the bottom stays in view: 
    if (($ydepth + $yzero) > YHEIGHT) {
	$ydepth = YHEIGHT - $yzero;
	$deep = 1;	
    }

    # Hash pattern to show part of depth missing on graph:
    my $h1 = 30;
    my $hash = sprintf("l %d %d l %d %d l %d %d", $h1, $h1, -2*$h1,
		       -2*$h1, $h1, $h1);

    my $y_half = sprintf("%0.0f", $ydepth * 0.5); 

    # Start the path tag: 
    my $path = "<path $class $transform d=\""; 

    # Fully out-of-transit partials, just a line: 
    if (($end <= $ingress) or ($start >= $egress)) {
	$path .= "M $xstart $yzero H $xend" . '"/>';
	return $path;
    }


    my $y_delta = $ydepth;

    if ($start <= $ingress) {
	my $xingress = sprintf("%0.0f", $H2P * $ingress);
	$path .= "M $xstart $yzero H $xingress ";
	if ($deep) {
	    # Skip a bit of path and show hashes on the gap: 
	    $path .= "v $y_half $hash m 0 100 $hash ";
	    $y_delta -= 100 + $y_half;
	}
	$path .= "v $y_delta ";
    } else {  # Starts in mid-transit: 
	my $ystart = $yzero + $ydepth;
	$path .= "M $xstart $ystart "; 
    }

    if ($end > $egress) {
	# Extend and draw the egress:
	my $xegress = sprintf("%0.0f", $H2P * $egress);
	$path .= "H $xegress "; 
	$y_delta = $ydepth;
	if ($deep) {
	    my $y_up = -$y_half + 100;
	    # Skip a bit of path: 
	    $path .= "v $y_up $hash m 0 -100 $hash ";
	    $y_delta = $y_half;
	}
	$path .= "v -$y_delta ";
    }

    $path .= "H $xend "; 
    
    # If it was too wide and we drew that part of the transit, add a
    # has mark to show that: 
    if ($wide and ($start < $mid) and ($end > $mid)) {
	$path .= sprintf("M %0.0f %0.f %s", $mid*$H2P, $ydepth + $yzero, $hash);
    }

    return $path . '"/>';
    
}

sub bjd2utcjd {
    # Given an input BJD_TDB time of an event at the solar system
    # barycenter, arriving from sky direction RA, Dec, return a
    # Julian Date specifying the UTC time that would be observed
    # on Earth.  The time is corrected for: 
    #
    # Light travel time difference (Romer delay); and 
    # Difference between UTC and TT, given by the constant offset of
    #   32.184 seconds between TT and TAI, and the number of leap
    #   seconds added, currently 37 as of August 2020;
    # It does *not* correct for:
    # - The position of the observer on Earth relative to the
    #   geocenter (~20 ms)
    # - the difference between TDB and TT, i.e. the Einstein delay
    #   that is predominantly a sinusoid of ~3.4 ms 
    # - Other effects at the ~ms level or less; see Eastman et
    #   al. 2010 PASP 122:935,
    #   https://ui.adsabs.harvard.edu/abs/2010PASP..122..935E
    # For testing and other code, see also
    # http://astroutils.astronomy.ohio-state.edu/time/ 
    #
    # Input RA and Dec are assumed to be in radians; returned value
    # is a JD value corresponding to Earth-observed UTC. 

    use Astro::PAL qw(palDtt palEpv);

    # speed of light in AU/sec (from IAU AU and SI def. of c):
    use constant C => 0.002003988804100003979;

    my ($bjd, $ra, $dec) = @_;

    # Get the x, y, z coordinates of the Earth, relative to the solar
    # system barycenter.  These vector components are in an
    # equatorially-based frame, and are in units of AU:

    my ($helio_pos, $helio_vel, $bary_pos, $bary_vel) =
	palEpv($bjd - 2400000.5);
    my ($xbary, $ybary, $zbary) = @$bary_pos;

    # Convert from the target's RA and Dec to the unit vector of its
    # position in this x,y,z frame:
    my $x = cos($dec) * cos($ra);
    my $y = cos($dec) * sin($ra);
    my $z = sin($dec);

    # The dot product of these gives the projection of the
    # Earth-barycenter vector in the direction of the target, so we
    # can calculate the light-travel time difference.  A positive
    # projection here means that the Earth is toward the same side of
    # the barycenter as the target is, and so would see the signal
    # earlier. Thus, this will represent an offset to be subtracted
    # from the BJD.
    my $r_proj = $x * $xbary + $y * $ybary + $z * $zbary;

    # Get the light travel time difference, and also account for the
    # offset between UTC and TT in seconds; palDtt gives TT - UTC:
    my $delta_t = $r_proj/C + palDtt($bjd - 2400000.5);

    # Offset returned value by both factors, in days:
    return $bjd - $delta_t/86400;
}

sub refine_ha_limits {

# Given input minimum and maximum hour angle limits, and a start and
# end time, find the sub-intervals where the limits are met. The
# assumption is that this is for an under-the-pole case, so that the
# starting and ending HA are OK, but somewhere in the middle the
# target crosses from +12 to -12.  Return start1, end1, start2, end2 -
# all DateTimes that define the start and end of the two valid
# intervals.  Thus, the time from end1 to start2 is when the hour
# angle limits are violated.
#
# Input: hash reference with minimum_ha, maximum_ha, start, end,
# target.  start and end are DateTime objects, target is an
# Astro::Coords object.
#
# Return: start1, end1, start2, end2; all DateTimes.

    my ($args) = @_;

    my $target = $args->{'target'};
    my $time = $args->{'start'}->clone();
    $target->datetime($time);
    my $ha_start = $target->ha(format=>'hour');
    my $inc = DateTime::Duration->new( minutes => 1);
    $target->datetime($args->{'end'});
    my $ha_end = $target->ha(format=>'hour');

    # First, check the input assumptions:
    if (($ha_start < $args->{'minimum_ha'}) or
	($ha_start > $args->{'maximum_ha'}) or
	($ha_end   < $args->{'minimum_ha'}) or
	($ha_end   > $args->{'maximum_ha'}))
    {
	fatal_error("Not starting at a valid hour angle in" .
		    " refine_ha_limits. ha_start: $ha_start ha_end: $ha_end");
    } elsif (($ha_end > 0) or ($ha_start < 0)) {
	fatal_error("Target does not pass under pole in" .
		    " refine_ha_limits: ha_start: $ha_start ha_end: $ha_end");
    }

    # Those checks should verify that we are starting at a valid
    # HA. Save the start time:
    my $start1 = $time->clone();

    my $ha = $ha_start;
    while (($ha >= $args->{'minimum_ha'}) and ($ha <= $args->{'maximum_ha'})) {
	$time = $time + $inc;
	$target->datetime($time);
	$ha = $target->ha(format=>'hour');
    }

    # Now we should have the end of the first observable window:
    my $end1 = $time->clone();

    # Now skip over the unobservable part:

    while (($ha < $args->{'minimum_ha'}) or ($ha < $args->{'maximum_ha'})) {
	$time = $time + $inc;
	$target->datetime($time);
	$ha =  $target->ha(format=>'hour');
    }

    # This should be the start of the second observable window:
    my $start2 = $time->clone();
    my $end2 = $args->{'end'}->clone();

    return ($start1, $end1, $start2, $end2);

}

sub num_only {
    # Take input and return a string that includes only
    # characters that match the pattern we expect for 
    # numbers.  In addition to digits, we allow plus and 
    # minus signs, both period and comma (both could be 
    # decimal separators depending on locale), and colon
    # to allow for colon-separated sexagesimal coords. 
    # Whitespace is also allowed. 

    my $input = shift @_;
    if (defined($input)) {
	$input =~ s/[^\d+-.,:\s]//g;
	return $input;
    } else {
	return "";
    }
}
