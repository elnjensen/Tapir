#!/usr/bin/perl

# Code to read in a file of targets for eclipse/transit observations,
# find upcoming events, sort them according to date, and print the
# results, either as HTML, or in CSV format to be read
# into Google Calendar or another calendar program.  Input parameters
# provided by transits.cgi, which calls this script. 


# Copyright 2012-2016 Eric Jensen, ejensen1@swarthmore.edu.
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


use Astro::Coords;
use Astro::Telescope;

use DateTime;
use DateTime::Duration;
use DateTime::Set;
use DateTime::Format::Epoch::JD;

use HTML::Template::Expr;
use CGI;
use CGI::Cookie;
use URI::Escape;

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


############# Variables for local configuration ##############

# Put things here that are likely to need to be changed in order to
# use this code for a different purpose:

# Template for the HTML output page:
my $template_filename = 'target_table.tmpl';
# File containing target info; include path as needed.
my $target_file = 'transit_targets.txt';

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
    $temporary_timezone, $observatory_timezone, $observatory_name); 

# Check to see if the entered string contains the text that indicates
# we should ignore it and use individual fields instead, or if we
# should try to parse it.

if ($observatory_string !~ /$flag_for_manual_entry/) {
    ($observatory_latitude, $observatory_longitude,
     $temporary_timezone, $observatory_name) 
	= split(/;/, $observatory_string);
} else {
    $observatory_longitude = $q->param("observatory_longitude");
    $observatory_latitude = $q->param("observatory_latitude");
    $temporary_timezone = $q->param("timezone");
    $observatory_name = "";
}

# The timezone string gets used in an 'eval' statement by
# DateTime::Timezone at some point, so we need to untaint it here by
# checking it against a regular expression.  We have to allow a '/'
# here, even though it is a path separator, because it is a legitimate
# part of some timezone names. 
if ($temporary_timezone =~ m%^\s*([_/+\-0-9A-Za-z]+)$%) {
    $observatory_timezone = $1;
} else {
    die "Unrecognized timezone: [$temporary_timezone]\n";
}

# Check to see if they set the parameter to use UTC no matter what:
my $use_utc = $q->param("use_utc");
if ((not defined $use_utc) or ($use_utc eq "")) {
    $use_utc = 0;
}

if ($use_utc) {
    $observatory_timezone = 'UTC';
}

# Desired time windows for data:

# Start date:
my $start_date_string = $q->param("start_date");
if ((not defined $start_date_string) or ($start_date_string eq "")) {
    $start_date_string = 'today';
}

# Days in the future to print (including start date):
my $days_to_print = $q->param("days_to_print");
if ((not defined $days_to_print) or ($days_to_print eq "")) {
    $days_to_print = 1;
}

# Days in the past (based from start date) to print:
my $days_in_past = $q->param("days_in_past");

# If they didn't specify a backward-looking window, then only show
# future eclipses:
if ((not defined $days_in_past) or ($days_in_past eq "")) {
  $days_in_past = 0;
}

# Minimum mid-transit elevation to show; default to zero:
my $minimum_elevation = $q->param("minimum_elevation");
if ((not defined $minimum_elevation) or ($minimum_elevation eq "")) {
  $minimum_elevation = 0;
}

# Minimum start/end elevation to show; default to 0:
my $minimum_start_end_elevation = $q->param("minimum_start_end_elevation");
if ((not defined $minimum_start_end_elevation) 
    or ($minimum_start_end_elevation eq "")) {
  $minimum_start_end_elevation = 0;
}

# Minimum priority to show; default to zero:
my $minimum_priority = $q->param("minimum_priority");
if ((not defined $minimum_priority) or ($minimum_priority eq "")) {
  $minimum_priority = 0;
}

# Minimum depth (in millimags) to show; default to zero:
my $minimum_depth = $q->param("minimum_depth");
if ((not defined $minimum_depth) or ($minimum_depth eq "")) {
  $minimum_depth = 0;
}

# Target name string to match (can be a regex):
my $target_string = $q->param("target_string");
if (not defined $target_string) {
    $target_string = '';
} else {
# Strip leading and trailing whitespace on this string:
    $target_string =~ s/^\s*(\S+)\s*$/$1/;
}

# Whether to show the ephemeris data:
my $show_ephemeris = $q->param("show_ephemeris");

# Whether the output will be printed as an HTML table; if this
# parameter is not set, then the output is printed in a
# comma-delimited form suitable for import into a calendar program,
# e.g. Google Calendar.
my $print_html =  $q->param("print_html");
# If they don't pass the parameter at all, print HTML rather than CSV:
if (not defined $print_html) {
    $print_html = 1;
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

my $minimum_elevation_cookie = CGI::Cookie->
  new(-name  =>  'minimum_elevation',
      -value   =>  "$minimum_elevation",
      -expires =>  $cookie_expires,
      -domain  =>  $cookie_domain,
      -path    =>  $cookie_path,
     );

my $minimum_start_end_elevation_cookie = CGI::Cookie->
  new(-name => 'minimum_start_end_elevation',
      -value   =>  "$minimum_start_end_elevation",
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

# Now set up objects that will let us calculate the times of sunrise
# and sunset, necessary for determining observability.

my $sun = new Astro::Coords(planet => "sun");

# Associate the observatory coordinates with this object by defining a
# telescope object for our coordinates. The library requires latitude
# and longitude in radians; the constant DD2R (decimal degrees to
# radians) is defined by Astro::PAL.  We specify an altitude of 0,
# since we need to say something; presumably this could be specified
# on input if we wanted to be even more precise about rise and set
# times.

my $deg2rad = Astro::PAL::DD2R;
my $telescope = new Astro::Telescope(Name => "MyObservatory", 
				  Long => $observatory_longitude*$deg2rad,
				  Lat => $observatory_latitude*$deg2rad,
				  Alt => 0,
				 );
$sun->telescope($telescope);


# Calculate the set of sunrise and sunset times that we will use later
# for testing transit observability.  We make a list of these times
# here, so that we can pass them in to the subroutine and re-use them
# for each subsequent target.

# To do this, we need to find the date around which we are basing the
# calculation.  

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
	    $hint = "Maybe you listed days before months?. ";
	} 
	die "Could not parse date [$start_date_string]; " 
	    . "must be 'today' or in MM-DD-YYYY format. $hint";
    }
    # Start at noon UTC on requested day:
    $base_date = DateTime->new(
			 year => $year,
			 month => $month,
			 day => $day,
			 hour => '12',
			 time_zone => 'UTC',
			 );
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
  my $next_sunset = $sun->set_time(horizon => 
				Astro::Coords::NAUT_TWILIGHT);
  my $next_sunrise = $sun->rise_time(horizon => 
				  Astro::Coords::NAUT_TWILIGHT);
  $sunsets = $sunsets->union( $next_sunset ); 
  $sunrises = $sunrises->union( $next_sunrise ); 


  # Increment by a day and go back to the beginning of the loop.
  # Actually, since the time of sunset and sunrise shift a little
  # bit day to day, if we increment by a day, and if we happen to be
  # doing this exactly at sunset or sunrise, we could miss an event
  # (e.g., the next sunrise could come 23h59m later and we increment
  # by 24h).  To be on the safe side, increment by a little less
  # than 24 hours.  If we end up calculating some duplicate times 
  # (which we will eventually if we have a long enough span) it
  # doesn't really matter, since DateTime::Set recognizes duplicate
  # values and doesn't actually add another one to the set.

  $current_date->add( hours => 23, minutes => 30 );
}


# Print out the appropriate header for either the calendar output or
# the HTML page:
my $print_calendar;

if (not $print_html) {
  $print_calendar = 1;
  print $q->header("text/plain");
  my $header_text = "Subject,Start Date,Start Time,End Date," .
    "End Time,All Day Event,Description\n";
  print $header_text;
} else {  # HTML output
  $print_calendar = 0;
  # Print the HTML header, including the cookies.  This output is
  # where the cookies actually are returned the user's browser and set.
  print $q->header(-type => "text/html",
		   -cookie => [$latitude_cookie, 
			       $longitude_cookie, 
			       $utc_cookie,
			       $observatory_cookie,
			       $minimum_elevation_cookie,
			       $timezone_cookie, 
			       $days_cookie,
			       $minimum_start_end_elevation_cookie, 
			       $days_in_past_cookie, 
			       $minimum_priority_cookie, 
			       $minimum_depth_cookie]
		  );
  print $q->start_html( -title => "Upcoming transits",
			);
}  # End printing headers.


# Some logic that would allow us to print secondary eclipses rather
# than primary transits; currently our input form does not allow this
# to be set, but could be changed here.  The logic to use it is
# implemented below - it just adds half a period to every predicted
# primary eclipse from the ephemeris.  Of course it's possible to
# specify ephemerides directly in the input for the secondary eclipses
# themselves.
my $do_secondary_eclipses = 0;

# Now, the main part of the code, for dealing with transits.  First,
# we need to set up some variables we'll use.

# Set up a hash that contains input parameters describing the
# observatory, dates, and so on - parameters that are not
# target-specific but which govern which events are observable and/or
# desired: 

my %constraints = (
		   days_to_print=>$days_to_print,
		   days_in_past=>$days_in_past,
		   do_secondary_eclipses=>$do_secondary_eclipses,
		   observatory_latitude => $observatory_latitude,
		   observatory_longitude => $observatory_longitude,
		   observatory_timezone => $observatory_timezone,
		   minimum_elevation => $minimum_elevation,
		   minimum_start_end_elevation 
		      => $minimum_start_end_elevation,
		   sunrises => $sunrises,
		   sunsets => $sunsets,
		   telescope => $telescope,
		   debug => $debug,
		   base_date => $base_date,
		   );



# Initialize the arrays we'll use to sort the eclipse times and
# the text to print:
my @eclipse_times = ();
my @eclipse_info = ();
my @eclipse_input_data = ();
my @non_eclipse_info = ();

# Separate code fetches the target info, and then stores it in a text
# file.  Here we read in the text file and parse it. 

# Read the file. Could include a different path here; be sure this
# is readable by whatever process runs the CGI script.

# Try to open the file:
my $status = open FILE, $target_file;
# If we fail to open the file, then send a message to the browser and
# quit.
if ($status == 0) {
  my $message = "Reading the target file $target_file generated "
    . "an error:\n$!\n";
  fatal_error($message);
}

# Read and close the file; array @lines has one line of the datafile
# per array entry.
my @lines = <FILE>;
close FILE;

# Initialize a few variables for keeping track of errors:
my $error_line_count = 0;
my @error_names_list = ();


# Now, loop over the lines of the input, assuming one target per line:

my $line;

TARGET_LOOP:
foreach $line (@lines) {

  # Skip lines that are commented out:
  if ($line =~ /^ *#/) {
    next TARGET_LOOP;
  }

  # Skip empty lines (only whitespace):
  if ($line =~ /^\s*$/) {
    next TARGET_LOOP;
  }

  # Pass the data line to a subroutine that parses it into separate
  # fields, and returns a reference to a hash containing that
  # information in named fields.  It also returns a cleaned-up version
  # of the input line that looks nicer for display.

  my ($target_ref, $cleaned_line) = parse_target_line($line);

  # Combine the hash of target-specific info with the
  # previously-created has of general observatory circumstances, to
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
    if ($target_info{name} !~ /$target_string/i) {
      next TARGET_LOOP;
    }
  }


  # Make sure the necessary fields are there (check against empty
  # strings) and if not, increment error count and go to next field.
  # The "None" used here is specific to the output generated from the
  # Google spreadsheet Python feed that is used to create the input
  # datafile; fields that are empty in the spreadsheet end up as
  # "None" here instead.

  my $error = 0;  # Start by assuming no error;

  # Must have coords no matter what:
  if ( ($target_info{ra_deg} eq "") or ($target_info{dec_deg} eq "") ) {
      $error = 1;
  }

  # Only have to have ephemeris info if it's a periodic target, type 1
  # or type 3. 
  if ( ( ($target_info{phot_requested} == 1) or 
	 ($target_info{phot_requested} == 3) )
       and
       ( ($target_info{epoch} =~ /None/) or ($target_info{period} =~ /None/)
	 or ($target_info{eclipse_width} =~ /None/) or
	 ($target_info{period} == 0) ) ) {
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
  # subroutine that calculates eclipses:
  if ( ($target_info{phot_requested} == 1) or
       ($target_info{phot_requested} == 3) ) {

      # See if the depth is too low to bother with; this filter only
      # applies to periodic targets, so is inside the above 'if':
      if ($target_info{depth} < $minimum_depth) {
	  next TARGET_LOOP;
      }

      my ($eclipse_time_ref,$eclipse_info_ref) = get_eclipses(\%target_info);

      # Take the references to the returned lists of eclipse strings and
      # times, and add those arrays to our growing lists:
      push @eclipse_times, @$eclipse_time_ref;
      push @eclipse_info, @$eclipse_info_ref;
  }

  # Now we also need to check for observability for "any time"
  # targets; here we don't check for specific eclipses, just for
  # whether the maximum altitude of the target during the night
  # exceeds the threshold set by the user.  We use the
  # $minimum_elevation parameter here to do double-duty for
  # mid-transit elevation and for minimum elevation overall for the
  # "any time" targets.

  if ( ($target_info{phot_requested} == 2) or
       ($target_info{phot_requested} == 3) ) {
      my %local_hash = %target_info;
      my ($target_info_ref) = get_observability(\%local_hash);
      push @non_eclipse_info, @$target_info_ref;
  }

    
}  # end of TARGET_LOOP loop over input file


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
    print $q->p("The following $phrase incomplete data" .
		" and $verb not used: $target_error_string");
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
# use the array values of the array @eclipse_times .  The syntax of
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

if ($print_html) {
  # Print the title text for the output page:
  my $day_word;
  if ($days_to_print <= 1) {
    $day_word = "day";
  } else {
    $day_word = "days";
  }

  my $past_string;
  if ($days_in_past > 0) {
      $past_string = " and the past $days_in_past days";
  } else {
      $past_string = '';
  }
  print $q->h2("Upcoming events for the next $days_to_print $day_word"
	       . " $past_string from $start_date_string;"
	       .  " start/end given in timezone "
	       . "$observatory_timezone.");


  # In order to let events on the same night have a leading column
  # that spans multiple rows (i.e. to just list that night's date
  # once), we need to loop through the whole array and tabulate how
  # many events we have on each night.  We create a new entry in the
  # data array, called "similar_count".  If a given event is the first
  # one on that night, similar_count is given a value of the total
  # number of events that night (so at least 1, but possibly more).
  # If it is not the first that night, similar_count gets a value of
  # zero.  So for example, for a night with three events, followed by
  # a night with only one, the four entries for similar_count would
  # be: [3 0 0 1].  We can then use this in the template to make one
  # of the entries span three rows (the current plus the next two
  # following rows).

  # Remember that each entry of list @sorted_eclipse_info is itself a
  # hash reference.

  # Get the last index of our list:
  my $last_index = $#sorted_eclipse_info;
  # And start at the beginning of the list:
  my $i=0;

  my ($save_current_index, $current_count, $previous_string);
  while ($i <= $last_index ) {
    # First time through the loop we are always at the
    # first of one or more similar entries:
    $save_current_index = $i;
    $current_count = 1;
    # Save the date string we'll compare to in order to see if the
    # following events are on the same date:
    $previous_string = $sorted_eclipse_info[$i]->{sunset_local_date};
    # Go to next element:
    $i++;
    # See if the following elements have the same date:
    while ( ($i <= $last_index) and 
	    ($sorted_eclipse_info[$i]->{sunset_local_date} eq 
	     $previous_string) ) 
      {
	# Found a similar value, so increment our count:
	$current_count++;
	# Note that *this* item is not first of its sequence:
	$sorted_eclipse_info[$i]->{similar_count} = 0;
	$i++;
      } # End of while loop over those similar to previous
    # Have found all similar items, so record the count:
    $sorted_eclipse_info[$save_current_index]->{similar_count} = 
      $current_count;
  } # End of while loop over all events


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
		     observatory_string => uri_escape($observatory_string),
		     timezone => $observatory_timezone,
		     show_ephemeris => $show_ephemeris,
		    );
  print $template->output();
  print $q->end_html;

} else {  # Matches "if $print_html" - if not, it's CSV output.
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
  my $ra_deg = $param_ref->{ra_deg};
  my $dec_deg = $param_ref->{dec_deg};
  my $ra_string = $param_ref->{ra_string};
  my $dec_string = $param_ref->{dec_string};
  my $name = $param_ref->{name};
  my $vmag = $param_ref->{vmag};
  my $epoch = $param_ref->{epoch};
  my $period = $param_ref->{period};
  my $eclipse_width = $param_ref->{eclipse_width};
  my $days_to_print = $param_ref->{days_to_print};
  my $days_in_past = $param_ref->{days_in_past};
  my $do_secondary_eclipses = $param_ref->{do_secondary_eclipses};
  my $observatory_timezone = $param_ref->{observatory_timezone};
  my $comments = $param_ref->{comments};
  my $priority = $param_ref->{priority};
  my $depth = $param_ref->{depth};
  my $sunsets = $param_ref->{sunsets};
  my $sunrises = $param_ref->{sunrises};
  my $telescope = $param_ref->{telescope};
  my $minimum_elevation = $param_ref->{minimum_elevation};
  my $minimum_start_end_elevation 
    = $param_ref->{minimum_start_end_elevation};
  my $debug = $param_ref->{debug};
  my $base_date = $param_ref->{base_date};

  # Before we can calculate eclipse visibility, we need to set up
  # some basics, like the current date and time.

  my $thisjd = DateTime::Format::Epoch::JD->format_datetime($base_date); 

  if ($debug) {
    carp "Base date is JD $thisjd\n";
  }

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

  # If we're tracking secondary rather than primary eclipses, we
  # just offset the epoch by half a period:
  my $offset;
  if ($do_secondary_eclipses) {
    # Looking for secondary eclipses; add a half-period offset
    $offset = $period * 0.5;
  } else {
    $offset = 0.;
  }

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

  my $eclipse_half_width_hours = int($eclipse_width/2.);
  my $eclipse_half_width_minutes = int(60.* (($eclipse_width/2.) - 
					    $eclipse_half_width_hours));
  my $eclipse_half_duration = DateTime::Duration->
    new(
	hours => $eclipse_half_width_hours,
	minutes => $eclipse_half_width_minutes,
       );

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
  my $eclipse_iteration = 0;
  my $max_eclipses_to_try = 2000;

 ECLIPSE_LOOP:
  while ($eclipse_iteration < $max_eclipses_to_try) {
    # Calculate JD of next eclipse:
    my $eclipse_jd = $new_epoch + $period*$eclipse_iteration + $offset;

    # Have we gone past the specified time window yet?  If so, we
    # exit from the loop:
    if ($eclipse_jd > $thisjd + $days_to_print) {
      last ECLIPSE_LOOP;
    }

    # Is the eclipse before our time window? If so,
    # just increment to next eclipse and jump back to the start of
    # the loop:
    if ( $eclipse_jd <= ($thisjd - $days_in_past) ) {
      $eclipse_iteration++;
      next ECLIPSE_LOOP;
    }

    # Convert the eclipse midpoint from JD to a DateTime object: 
    my $dt = DateTime::Format::Epoch::JD->parse_datetime($eclipse_jd);
    $dt->set_time_zone('UTC');

    # Now that we have the time object, we can ask the key
    # question: is this eclipse at night, or during the day? We
    # test that for all three of the start, middle, and end of the
    # eclipse, so that we can show partially-visible eclipses:

    # Get DateTime objects for start and end of eclipse:
    my $dt_start = $dt->clone->subtract_duration($eclipse_half_duration);
    my $dt_end = $dt->clone->add_duration($eclipse_half_duration);

    # To test for daytime for a given event, we calculate the
    # following sunset and the following sunrise.  If the next
    # sunset comes before the next sunrise, then it's daytime. 

    my $next_sunset = $sunsets->next($dt_start);
    my $next_sunrise = $sunrises->next($dt_start);
    my ($is_daytime_start, $is_daytime_mid, $is_daytime_end);

    # The previous calls to "next" will return a defined value as
    # long as the DateTime we're using is within the set.  This
    # should always be true, but to be on the safe side, check for
    # undefined values and throw an error if they occur:
    if ( not (defined($next_sunset) and defined($next_sunrise)) ) { 
      fatal_error("At date $dt_start, "
		  . "next sunset or sunrise was undefined." );
    }
    $is_daytime_start = ($next_sunset < $next_sunrise);

    # Now we do the same thing for the middle and end of the
    # event, though we add a couple of checks to avoid more sunset
    # calculations than we need, since they are the most
    # time-consuming part of the code.

    # If we know the start is in the daytime, AND if the middle is
    # before the sunset we just calculated, then we can figure out
    # that the middle is in daytime, too, without calculating
    # another pair of rise/set times.  But if not, we just go
    # ahead and calculate it as above.

    if ( $is_daytime_start and ($dt < $next_sunset) ) {
      $is_daytime_mid = 1;
    } else {
      $next_sunset = $sunsets->next($dt);
      $next_sunrise = $sunrises->next($dt);
      if ( not (defined($next_sunset) and defined($next_sunrise)) ) { 
	fatal_error("At date $dt, "
		    . "next sunset or sunrise was undefined." );
      }
      $is_daytime_mid = ($next_sunset < $next_sunrise);
    }

    # Similarly, if it's nighttime for the mid-eclipse AND the end
    # of the eclipse comes before the previously-calculated next
    # sunrise, then we know it's nighttime at the end of the
    # eclipse, too, without doing the calculation.  

    if ( (not $is_daytime_mid) and ($dt_end < $next_sunrise) ) {
      $is_daytime_end = 0;
    } else {
      $next_sunset = $sunsets->next($dt_end);
      $next_sunrise = $sunrises->next($dt_end);
      if ( not (defined($next_sunset) and defined($next_sunrise)) ) { 
	fatal_error("At date $dt_end, " 
		    . "next sunset or sunrise was undefined." );
      }
      $is_daytime_end = ($next_sunset < $next_sunrise);
    }

    if (not ($is_daytime_mid 
	     and $is_daytime_start 
	     and $is_daytime_end)) {   

      # Part of eclipse is at night - go ahead!

      # Above we have tested whether or not the eclipse falls
      # within our time window, and then whether or not part of
      # it falls at night.  The final test to select observable
      # events is to determine whether the elevation is high
      # enough. 

      # First, we set up a coordinate object that will allow us
      # to calculate the elevation of the target at different
      # times: 

      my $target = new Astro::Coords( ra => $ra_deg,
				      dec => $dec_deg,
				      type => 'J2000',
				      units => 'degrees',
				    );
      $target->telescope($telescope);

      # Then use this to get elevations at the relevant times: 
      $target->datetime($dt_start);
      my $el_start_deg = $target->el(format=>'deg');
      $target->datetime($dt);
      my $el_mid_deg = $target->el(format=>'deg');
      $target->datetime($dt_end);
      my $el_end_deg = $target->el(format=>'deg');


      # To be shown as an observable eclipse, either the start
      # OR the end has to be above a minimum elevation (defaults
      # to zero) AND the middle has to be above a (possibly
      # different) minimum elevation:

      if ((($el_start_deg >= $minimum_start_end_elevation) or
	   ($el_end_deg >= $minimum_start_end_elevation)) and
	  ($el_mid_deg >= $minimum_elevation)) {

	# Then the eclipse should be visible!

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
	# evening date.  This calculation returns a string like
	# "-0500" that gives the approximate number of hours
	# that we are offset from UTC; such a string can be
	# used in place of a timezone name:

	my $timezone_offset = sprintf("%+03d00",
				      $observatory_longitude*24./360.);

	# Get the correct local sunset date for the
	# eclipse. We set the time to the mid-point of the
	# eclipse, and then check conditions to see if the
	# evening sunset associated with this date comes
	# before or after that.

	my ($sunrise_object, $sunset_object);
	if (($is_daytime_start) and ($is_daytime_mid)) {
	  # Find next sunset:
	  $sunset_object = $sunsets->next($dt)->clone;
	} else {
	  # Find previous sunset
	  $sunset_object = $sunsets->previous($dt)->clone;
	}

	if (($is_daytime_mid) and ($is_daytime_end)) {
	  # Find previous sunrise
	  $sunrise_object = $sunrises->previous($dt)->clone;
	} else {
	  # Find next sunrise
	  $sunrise_object = $sunrises->next($dt)->clone;
	}


	# Now that we have the right sunset, we can set it to
	# our shifted timezone and find the date associated
	# with it:
	$sunset_object->set_time_zone($timezone_offset);

	# Get the local date of sunset in this longitude-based
	# timezone: 
	my $sunset_local_date = $sunset_object->day_abbr . ". " .
	  sprintf("%02d-%02d-%04d", $sunset_object->month, 
		  $sunset_object->day, $sunset_object->year);


	# Get times of sunset and sunrise in desired timezone:
	$sunrise_object->set_time_zone($observatory_timezone);
	my $sunrise_time = $sunrise_object->hms;
	$sunset_object->set_time_zone($observatory_timezone);
	my $sunset_time = $sunset_object->hms;
	# Strip the seconds:
	$sunrise_time =~ s/:\d\d$//;
	$sunset_time =~ s/:\d\d$//;

	# Save the JD of sunset so we know which night we're
	# referring to, e.g. for an eclipse that just barely
	# starts before dawn and so might have the
	# *following* day's sunset closest to its midpoint:
	my $sunset_jd = DateTime::Format::Epoch::JD->
	  format_datetime($sunset_object);


	# Now get some other assorted dates and times that are
	# used in the output, in the timezone requested by the
	# user (presumably either the observatory timezone or
	# UTC):
	$dt->set_time_zone($observatory_timezone);
	my $local_time = $dt->hms;
	# Drop the trailing seconds in the output time string:
	$local_time =~ s/:\d\d$//;
	my $local_date = $dt->mdy;


	# Now find times of the start and end of eclipse:
	my $eclipse_full_width_hours = int($eclipse_width);
	my $eclipse_full_width_minutes 
	  = int(60.* ($eclipse_width -
		      $eclipse_full_width_hours));
	# String for printing the duration:
	my $eclipse_duration_string
	  = sprintf("%d:%02d",
		    $eclipse_full_width_hours, 
		    $eclipse_full_width_minutes);
	# DateTime objects for start and end:
	my $dt_start_local = $dt - $eclipse_half_duration;
	my $dt_end_local = $dt + $eclipse_half_duration;
	$dt_start_local->set_time_zone($observatory_timezone);
	$dt_end_local->set_time_zone($observatory_timezone);

	my $local_date_start = $dt_start_local->mdy;
	my $local_time_start = $dt_start_local->hms;
	my $local_date_end = $dt_end_local->mdy;
	my $local_time_end = $dt_end_local->hms;
	# Drop the trailing seconds in the output time strings:
	$local_time_end =~ s/:\d\d$//;
	$local_time_start =~ s/:\d\d$//;

	# Make up a hash with all the bits of info, to return:
	my %eclipse;

	# Eclipse start and end were defined as DateTime objects
	# above, but here we need them in JD:

	my $eclipse_start_jd = $eclipse_jd - 0.5 * $eclipse_width/24.;
	my $eclipse_end_jd = $eclipse_jd + 0.5 * $eclipse_width/24.;

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

	$eclipse{jd_start} = sprintf("%0.3f", $eclipse_start_jd
				     - 2450000);
	$eclipse{jd_end} = sprintf("%0.3f", $eclipse_end_jd
				   - 2450000);
	$eclipse{jd_mid} = sprintf("%0.3f", $eclipse_jd
				   - 2450000);
	$eclipse{start_time} = $local_time_start;
	$eclipse{start_el} = sprintf("%02d",$el_start_deg);
	$eclipse{start_date} = $local_date_start;
	$eclipse{mid_time} = $local_time;
	$eclipse{mid_el} = sprintf("%02d",$el_mid_deg);
	$eclipse{mid_date} = $local_date;
	$eclipse{end_time} = $local_time_end;
	$eclipse{end_el} = sprintf("%02d",$el_end_deg);
	$eclipse{end_date} = $local_date_end;
	$eclipse{sunrise_time} = $sunrise_time;
	$eclipse{sunset_time} = $sunset_time;
	$eclipse{sunset_local_date} = $sunset_local_date;
	$eclipse{coords} = $ra_string . " " . $dec_string;
	$eclipse{ra} = $ra_string;
	$eclipse{dec} = $dec_string;
	$eclipse{comments} = $comments;
	$eclipse{priority} = $priority;
	$eclipse{depth} = $depth;
	$eclipse{duration} = $eclipse_duration_string;
	# Count to be filled in after sorting:
	$eclipse{similar_count} = 0;

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
    $eclipse_iteration++;
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
  my $ra_deg = $param_ref->{ra_deg};
  my $dec_deg = $param_ref->{dec_deg};
  my $ra_string = $param_ref->{ra_string};
  my $dec_string = $param_ref->{dec_string};
  my $name = $param_ref->{name};
  my $observatory_timezone = $param_ref->{observatory_timezone};
  my $comments = $param_ref->{comments};
  my $priority = $param_ref->{priority};
  my $sunsets = $param_ref->{sunsets};
  my $sunrises = $param_ref->{sunrises};
  my $telescope = $param_ref->{telescope};
  my $minimum_elevation = $param_ref->{minimum_elevation};
  my $debug = $param_ref->{debug};
  my $base_date = $param_ref->{base_date};


  my $target = new Astro::Coords( ra => $ra_deg,
				  dec => $dec_deg,
				  type => 'J2000',
				  units => 'degrees',
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
  if ( $max_target_elevation >= $minimum_elevation ) {
      # Make a clone of the input parameters, which we will return
      # with just a few more fields added:
      my %info = %$param_ref;
      $info{max_elevation} = sprintf("%d",$max_target_elevation);
      $max_elevation_time->set_time_zone($observatory_timezone);
      $info{max_elevation_time} = $max_elevation_time->hms;
      # Strip the seconds:
      $info{max_elevation_time} =~ s/:\d\d$//;
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

sub RA_hms_to_deg {

  # Convert input (3-element list of RA hours, minutes, seconds of time)
  # to RA in degrees.  First convert to hours, then multiply by 15 to
  # get degrees.

  my($ra_hr, $ra_min, $ra_sec) = @_;

  if (($ra_hr >= 24) or ($ra_min >= 60) or ($ra_sec >= 60)) {
    die "At least one RA element out of range in RA_hms_to_deg: " .
      "$ra_hr, $ra_min,$ra_sec\n"; 
  }
  my $ra_hr_total = $ra_hr + ($ra_min + ($ra_sec/60.))/60.;
  my $ra_deg = $ra_hr_total * 15.;
  return($ra_deg);
}

sub Dec_dms_to_deg {

  # Convert input (3-element list of Dec degrees, arcminutes, arcseconds)
  # to Dec in degrees.

  my($dec_deg, $dec_min, $dec_sec) = @_;

  if (($dec_deg >= 90) or ($dec_min >= 60) or ($dec_sec >= 60)) {
    die "At least one DEC element out of range in DEC_dms_to_deg: " .
      "$dec_deg, $dec_min,$dec_sec\n"; 
  }
  my $sign = 0;

  # Get the declination sign.  Don't just compare numerically, because
  # the degree field might be "-00".  Instead, do a string comparison to
  # check for a minus sign at the beginning.  NOTE: if the variable with
  # the input $dec_deg was "-00" but has been manipulated mathematically
  # and assigned to (as opposed to string assignments) prior to being
  # passed to the subroutine, it will not retain the leading "-".  Just
  # in case, check it both ways - this gives the best chance of success.

  if (($dec_deg =~ /^\s*-/) or ($dec_deg < 0)) {
    $sign = -1;
    $dec_deg = -1 * $dec_deg;
  } else {
    $sign = 1;
  }
  my $dec_deg_total = $dec_deg + ($dec_min + ($dec_sec/60.))/60.;
  return($dec_deg_total*$sign);
}

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
    $note .= "Notes: $t{comments}. "; 
    if (defined $t{finding_chart}) {
	$note .= "Finding chart at $t{finding_chart}. ";
    }
    # Add the note to the final entry.  It needs to be enclosed in
    # double quotes, or any embedded commas will be interpreted as
    # field separators:
    $eclipse_entry .= '"' . $note . '"' . "\n";

    return $eclipse_entry;
    
}

sub parse_target_line {

    # Subroutine to take a raw line of text from the input target file,
    # and split it up into the desired fields.

    # Input: single text string with target info.
    # Output: (1) reference to a hash that contains the various pieces of
    # information in named fields; and (2) a cleaned-up version of the
    # input line that is more suitable for display to the user. 

    # Get the input line:
    my $line = shift @_;
    

    # Specify the record separator, and use it to split up the line
    # into fields; This record separator (a comma followed by a
    # period) makes it straightforward to allow commas to be embedded
    # within fields themselves.  Spaces on either side of the field
    # separator are not significant, i.e. they are ignored.  Here we
    # need to escape the period in the record separator so we can use
    # it in a regular expression below.

    my $rec_separator = ',\.';
    
    # Clean out the weird record separator for nicer display;
    my $cleaned_line = $line;
    # Replace record separator with just a comma:
    $cleaned_line =~ s/$rec_separator/,/g;
    chomp($cleaned_line);
    
    # Now, on to actually processing the data line:
    # Split out the fields from the input into array @F; note that
    # we're allowing possible white space around the record separator,
    # which won't end up being recorded in the field values:
    my @F = split(/ *$rec_separator */, $line);
    
    # Now store the field values in more descriptive variable names,
    # in a hash that we will eventually return.

    # The fields, by column number (starting with 0):
    #  0: target name
    #  1: RA in h:m:s (colon- or space-delimited)
    #  2: Dec in d:m:s (colon- or space-delimited)
    #  3: V mag (or other mag)
    #  4: JD for central transit (i.e. zero point of the ephemeris) +/-
    #     uncertainty (e.g. "2455867.42 +/- 0.05"); currently the 
    #     uncertainty part is optional and unused.
    #  5: Period in days, +/- uncertainty, e.g. "2.131 +/- 0.001" ;
    #     currently the uncertainty part is optional and unused.
    #  6: Transit duration, in hours
    #  7: Comments on the target; these are not used in the processing,
    #     but they are passed along to the output.
    #  8: Priority.  Not required, but can be used as a filter.
    #  9: Depth of the transit in millimag.  Not used in calculations but
    #     can be a filter for which events to display.
    # 10: Code that specifies type of photometry requested.  A value
    #     of 1 means a periodic event; 2 means non-periodic, i.e. 
    #     ignore period and epoch fields and only try to calculate
    #     overall observability during the night (e.g. for
    #     out-of-transit observations); and 3 means both (1+2), i.e.
    #     this object has periodic events defined by the given 
    #     ephemeris, but should also be listed in the output for
    #     "any time" or out-of-transit observations. 
    

    # Use "t" (for "target") as the name of our hash for this target: 
    my %t;

    $t{name} = $F[0];
    my $ra_input = $F[1];
    my $dec_input = $F[2];
    $t{vmag} = $F[3];
    $t{epoch} = $F[4];
    $t{period} = $F[5];
    $t{eclipse_width} = $F[6];
    $t{comments} = $F[7];
    $t{priority} = $F[8];
    $t{depth} = $F[9];

    # We default to everything being assumed to be a
    # periodic/eclipsing/transiting event if it's not specified:
    if (defined $F[10]) {
	$t{phot_requested} = $F[10];
    } else {
	$t{phot_requested} = 1;
    }

    # Now do some processing of these raw input values.
    # Strip any leading or trailing spaces from the name:
    $t{name} =~ s/^\s*(\w+)\s*$/$1/;


    # Epoch and period can both include uncertainties.  Separate them
    # out here, although we aren't currently using them in the
    # calculations.  This regular expression searches for two numbers
    # (perhaps with embedded decimal place) separated by the string
    # "+/-" or "+-" :
    my ($epoch_uncertainty, $period_uncertainty);
    if ($t{epoch} =~ /([\d.]+)\s*\+\/?-\s*([\d.]+)/) {
	$t{epoch} = $1;
	$t{epoch_uncertainty} = $2;
    }

    if ($t{period} =~ /([\d.]+)\s*\+\/?-\s*([\d.eE+-]+)/) {
	$t{period} = $1;
	$t{period_uncertainty} = $2;
    }


    # Extract coords from the colon-delimited strings, or possibly
    # space-delimited strings. 
    my ($ra_h, $ra_m, $ra_s, $ra_deg);
    my ($dec_d, $dec_m, $dec_s, $dec_deg, $dec_sign);
    
    if ($ra_input =~ /\d:\d+:\d/) { # RA is h:m:s colon-separated
	($ra_h, $ra_m, $ra_s) = split(":", $ra_input);
	$t{ra_deg} = RA_hms_to_deg($ra_h, $ra_m, $ra_s);
    } elsif ($ra_input =~ /\d+ +\d+ +\d+/) {  # RA is h m s space-separated
	($ra_h, $ra_m, $ra_s) = split(" ", $ra_input);
	$t{ra_deg} = RA_hms_to_deg($ra_h, $ra_m, $ra_s);
    } else {  # RA is not in a recognizable format; set it to an empty
	      # string which we'll trap as an error later.
	$t{ra_deg} = "";
    }
    
    if ($dec_input =~ /\d:\d+:\d/) {   # Dec is d:m:s colon-separated
	($dec_d, $dec_m, $dec_s) = split(":", $dec_input);
	$t{dec_deg} = Dec_dms_to_deg($dec_d, $dec_m, $dec_s);
    } elsif ($dec_input =~ /\d+ +\d+ +\d+/) {  # Dec is d m s space-separated
	($dec_d, $dec_m, $dec_s) = split(" ", $dec_input);
	$t{dec_deg} = Dec_dms_to_deg($dec_d, $dec_m, $dec_s);
    } else {  # Dec is not in a recognizable format; set it to an empty
	      # string which we'll trap as an error later.
	$t{dec_deg} = "";
    }
    

    # Save a string that has the sign of the declination.  We need this
    # because if the declination is between 0 and -1 degree then we
    # can't get the sign directly by just checking the whole degrees
    # part of the input, since "-00" is not less than zero (when
    # compared as a number).

    if ($t{dec_deg} < 0) {
	$dec_sign = "-";
    } else {
	$dec_sign = "+";
    }

    # Strings for nicely-formatted printing later.  These have the
    # correct leading zeroes, signs, etc.:

    $t{ra_string} = sprintf("%02d:%02d:%05.2f", $ra_h, $ra_m, $ra_s);
    $t{dec_string} = sprintf("%s%02d:%02d:%04.1f", $dec_sign, 
			     abs($dec_d), $dec_m, $dec_s);

    return \%t, $cleaned_line;

}  # End of sub parse_target_line


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
    $name =~ s/\s+/_/g;

    my $target_page_url = "http://exoplanets.org/detail/$name";

    my $target_page_label = "Exoplanets.org";

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
    # with the finding chart.

    my $name = $target_ref->{name};
    # Replace spaces with underscores:
    $name =~ s/\s+/_/g;
    return "finding_charts/$name.jpg";

}
