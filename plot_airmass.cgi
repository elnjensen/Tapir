#!/usr/bin/perl

# Script to create an SVG plot of airmass vs. time for an astronomical
# target.  Input parameters are provided by airmass.cgi, which calls
# this script. 

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

# Updated 2017-10-24: fix bug relating to small decimal values in RA
# or Dec fields, which were being incorrectly interpreted as radians. 

# Updated 2018-03-12: reformat dates/times being passed into the
# plotting routine to be sure timezone information is embedded within
# the date string and thus will be interpreted correctly for
# plotting. 


use Astro::Coords;
use Astro::Telescope;
use Astro::PAL;
use DateTime::Format::Epoch::JD;
use DateTime::Format::RFC3339;
use SVG::TT::Graph::TimeSeries;
use CGI;
use CGI::Cookie;
use LWP::Simple;
use Math::Trig;
use HTML::Entities;

use strict;
use warnings;

my $q = CGI->new();
my @cookies = ();

# Contact info provided in the fatal_error subroutine:
my $script_contact_person = 'Eric Jensen, ejensen1@swarthmore.edu';

# Get some input settings from the URL:

my $observatory_string = $q->param("observatory_string");
my $flag_for_manual_entry = 'Specified_Lat_Long';

if ((not defined $observatory_string) or ($observatory_string eq "")) {
    $observatory_string = $flag_for_manual_entry;
}

push @cookies, define_cookie('observatory_string', 
			     $observatory_string);

my ($observatory_latitude, $observatory_longitude,
    $temporary_timezone, $timezone, $observatory_name); 

# Check to see if the entered string contains the text that indicates
# we should ignore it and use individual fields instead, or if we
# should try to parse it.

if ($observatory_string !~ /$flag_for_manual_entry/) {
    ($observatory_latitude, $observatory_longitude,
     $temporary_timezone, $observatory_name) 
	= split(/;/, $observatory_string);
    # Make sure name is encoded for printing, and 
    # add a period to the name for later printing ease:
    $observatory_name =  encode_entities($observatory_name) . ". ";
} else {
    $observatory_longitude = $q->param("observatory_longitude");
    $observatory_latitude = $q->param("observatory_latitude");
    $temporary_timezone = $q->param("timezone");
    $observatory_name = "";
    push @cookies, define_cookie('observatory_latitude', 
				 $observatory_latitude);
    push @cookies, define_cookie('observatory_longitude', 
				 $observatory_longitude);
    push @cookies, define_cookie('observatory_timezone', 
				 $temporary_timezone);
}

# Make sure latitude and longitude only have valid chars: 
$observatory_longitude = num_only($observatory_longitude);
$observatory_latitude = num_only($observatory_latitude);

$timezone = encode_entities($temporary_timezone);

if ($timezone eq '') {
    $timezone = "UTC";
}

# Check to see if they set the parameter to use UTC no matter what:
my $use_utc = $q->param("use_utc");
if ((not defined $use_utc) or ($use_utc eq "")) {
    $use_utc = 0;
}

push @cookies, define_cookie('Use_UTC', 
			     $use_utc);

if ($use_utc) {
    $timezone = 'UTC';
}


# Check to see if they set the parameter to invert colors:
my $invert = $q->param("invert");
if ((not defined $invert) or ($invert eq "")) {
    $invert = 0;
}

# Check to see if they set the parameter to plot Moon position:
my $plot_moon = $q->param("plot_moon");
if ((not defined $plot_moon) or ($plot_moon eq "")) {
    $plot_moon = 0;
}

# Check to see if they set the parameter to change airmass scale:
my $max_airmass = num_only($q->param("max_airmass"));
if ((not defined $max_airmass) or ($max_airmass eq "")) {
    $max_airmass = 2.4;
}

push @cookies, define_cookie('max_airmass', 
			     $max_airmass);

# Check to see if they set the parameter to plot right-hand labels:
my $elevation_labels = $q->param("elevation_labels");
if ((not defined $elevation_labels) or ($elevation_labels eq "")) {
    $elevation_labels = 1;
}

push @cookies, define_cookie('invert', 
			     $invert);


my $jd = num_only($q->param("jd"));
my $jd_start = num_only($q->param("jd_start"));
my $jd_end = num_only($q->param("jd_end"));

# Start date:
my $start_date_string = encode_entities($q->param("start_date"));
if ((not defined $start_date_string) or ($start_date_string eq "")) {
    $start_date_string = 'today';
}

# Given these default values so that if they are not present, they
# don't generate warnings later if we reference them.
if (not defined($jd)) {
    $jd = "";
}
if (not defined($jd_start)) {
    $jd_start = "";
}
if (not defined($jd_end)) {
    $jd_end = "";
}

# Sometimes abbreviated versions of the transit start/end times might
# be passed in; fix them.
if ($jd_start ne "") {
    if ($jd_start < 50000) {
	$jd_start += 2450000;
    } elsif ($jd_start < 2000000) {
	$jd_start += 2400000;
    }
}

if ($jd_end ne "") {
    if ($jd_end < 50000) {
	$jd_end += 2450000;
    } elsif ($jd_end < 2000000) {
	$jd_end += 2400000;
    }
}


my $ra = num_only($q->param("ra"));
my $dec = num_only($q->param("dec"));
my $target_input = encode_entities($q->param("target"));

# Choose an alternate Vizier mirror if one isn't working:
#my $vizier_mirror = "https://cdsweb.u-strasbg.fr/cgi-bin/";
my $vizier_mirror = "http://vizier.cfa.harvard.edu/cgi-bin/";

if (($ra eq '') and ($target_input ne '')) {
    # No RA given, try to resolve name with Simbad:
    # First vet the name against a regular expression; since we pass
    # it back out in a URL, we want to be careful about what is in
    # that string:
    if ($target_input =~ m%\A([A-Za-z0-9\-\+\.\s\*\[\]\(\)\/\'\"]+)\Z%) {
	my $target_name = $1;
	# Encode plusses in the name:
	my $plus_code = '%2B';
	$target_name =~ s/\+/$plus_code/g;
	# Convert spaces in the name to plusses:
	$target_name =~ s/ +/\+/g;
	my $simbad_url = $vizier_mirror . "nph-sesame/" 
	    . "-oxp/SN?${target_name}";
	my $simbad_output = get($simbad_url);

	# Try to match a pattern in the output to get coords:
	if ($simbad_output 
	    !~ m%<jpos>\s*(\d\d:\d\d[:.\d]*)\s+
                    ([+-]?\d\d:\d\d[:.\d]*)\s*</jpos>%x) { 
	    my $err_title =  "Error - no coordinates";
	    my $err_message = "No RA given and could not parse/resolve"
		. " name: $target_input \n"
		. "<p> The output from Vizier was: "
		. "<pre> $simbad_output </pre>" 
		. "<p> The query URL was: "
		. "<pre>$simbad_url</pre>";
	    fatal_error($err_title, $err_message);
	} else {
	    $ra = $1;
	    $dec = $2;
	}
    } else {
	my $err_title = "Error in object name";
	my $err_message = "Input does not look like an object name:"
	    . " <pre>$target_input</pre>." .
	    " If you feel this should have been resolvable by"
	    . " Simbad or NED, please contact $script_contact_person.";
	fatal_error($err_title, $err_message);
    }
} elsif ((($ra eq '') or ($dec eq '')) and ($target_input eq '')) {
    fatal_error("Error - no coordinates", 
		"Must provide either RA/Dec or an object name.");
}

my $sun = new Astro::Coords(planet => "sun");
my $moon = new Astro::Coords(planet => "moon");

# If the coords are in decimal form, and are less than 2 pi, then 
# they get interpreted by Astro::Coords as radians (which surely
# isn't the user's intent), so we need to identify when we have
# sexagesimal vs. decimal, and label accordingly.  We assume that
# sexagesimal can be either whitespace-delimited or colon-delimited. 
# If we're using decimal, then we multiply RA by 15 to convert from 
# hours to degrees, since declination will be in degrees, and we can't
# mix the two formats.  

my $coord_format; 
my $original_ra = $ra;

if ($ra =~ /\d[:\s]+\d/) {
    $coord_format = 'sexagesimal';
} else {
    $coord_format = 'degrees'; 
    $ra = $ra * 15;  # Convert from hours to degrees.
}


my $target = new Astro::Coords( ra => $ra,
				dec => $dec,
				type => 'J2000',
				units => $coord_format,
				);

if ((not defined($target)) or (($coord_format eq 'degrees') and ($original_ra >= 24))) {
    my $err_title = "Could not parse coordinates";
    my $err_message = "Could not parse the coordinates RA = [$original_ra]" 
	. " and/or Dec = [$dec].<br />  Note: square brackets are not part"
	. " of the input, but are used to show whether the coords "
	. " have spaces or may be empty strings. <br />"
	. "Also note that RA must be in <b>hours</b> (either decimal "
	. "or sexagesimal), not degrees, and therefore must be < 24." 
	. "RA and Dec must both be in the same format.";
    fatal_error($err_title, $err_message);
}

my $longitude_radians = $observatory_longitude * Astro::PAL::DD2R;
my $latitude_radians = $observatory_latitude * Astro::PAL::DD2R;

my $telescope = new Astro::Telescope(Name => "My observatory", 
				     Long => $longitude_radians,
				     Lat => $latitude_radians,
				     Alt => 0,
				     );

$sun->telescope($telescope);
$target->telescope($telescope);
$moon->telescope($telescope);

# Now set the time for which we'll do the calculation; if the user
# passed in a Julian Date (JD), use it; otherwise use the mm-dd-yyyy
# string passed in.  Failing either of these, use the current
# time.  In either case, we then find the nearest sunset to that
# time. 

my $now;

if ($jd =~ /\d+/) {  # JD is some set of numbers, use it:
    $now = DateTime::Format::Epoch::JD->parse_datetime( $jd );
    $now->set_time_zone('UTC');
} else { # Use the date string 
    if ($start_date_string =~ /^\s*today\s*$/i) {
	$now = DateTime->now( time_zone => 'UTC' );
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
		$hint = "Maybe you listed days before months? ";
	    } 
	    fatal_error("Error in date", 
			"Could not parse date [$start_date_string]; " 
			. "must be 'today' or in MM-DD-YYYY format. $hint");
	}
	# Start at local noon on requested day:
	$now = DateTime->new(
			     year => $year,
			     month => $month,
			     day => $day,
			     hour => '12',
			     time_zone => $timezone,
			     );
	# But change the time object to UTC for subsequent use:
	$now->set_time_zone('UTC');

    }  # End of block for non-'today' string
}  # End of block for parsing date string

$sun->datetime($now);

# Find the nearest sunset, and the sunrise after that:
my $sunset = $sun->set_time(event => 0,
			    horizon => Astro::Coords::NAUT_TWILIGHT,
			    );
$sun->datetime($sunset);
my $sunrise = $sun->rise_time(event => 1,
			      horizon => Astro::Coords::NAUT_TWILIGHT,
			      );

# Run from a little before sunset to a little after sunrise:
my $start = $sunset->clone->subtract(hours => 1, minutes => 30);
$start->truncate(to=>'hour');
# print "Start is $start\n";
my $end = $sunrise->clone->add(hours => 1, minutes => 30);
$end->truncate(to=>'hour');
# print "End is $end\n";

# Make a clone of the start date, which we'll switch to local time in
# order to get the correct local date of sunset:
my $start_date_local = $start->clone();
$start_date_local->set_time_zone($timezone);
my $start_date = $start_date_local->ymd();

# For making the plot pretty, calculate the fraction of the way
# through the time interval that sunset occurs:
my $span = $end->epoch - $start->epoch;
my $sunset_frac = ($sunset->epoch - $start->epoch)/$span;
my $sunrise_frac = ($sunrise->epoch - $start->epoch)/$span;
# Turns out that starting/ending the gradient right at these values
# doesn't look quite right, so stretch it a little:
my $scale = 1.35;
my $sunset_gradient = $scale * $sunset_frac;
my $sunrise_gradient = 1. - $scale*(1. - $sunrise_frac);


# Now address whether or not color scheme should be changed
# (light/inverted color scheme is better for printing)

my $stylesheet = 'airmass_stylesheet.css';

my ($day_color, $night_color);

if ($invert) {
    $day_color = "#1f1850";
    $day_color = "#1e90ff";
    $night_color = "#eeeeee";
} else {
    $day_color = "#00dded";
    $night_color = "#0f0850";
}





# Then use these values to set up a gradient background for the plot: 
my $gradient_def = <<END_GRADIENT;
<!-- Created with SVG-edit - http://svg-edit.googlecode.com/ -->
 <defs>
  <linearGradient gradientUnits="userSpaceOnUse" x1="0%" y1="0%" 
    x2="100%" y2="0%" id="blue_fade">
   <stop stop-color="$day_color" offset="0"/>
   <stop stop-color="$night_color" offset="$sunset_gradient"/>
   <stop stop-color="$night_color" offset="$sunrise_gradient"/>
   <stop stop-color="$day_color" offset="1"/>
  </linearGradient>
 </defs>
END_GRADIENT
    ;


my @data = ();
my @moon_data = ();
my ($ra_target, $dec_target) = $target->radec;

# Create an object we will use to reformat the datetime values into a
# format that the plotting routine will parse correctly, including an
# embedded timezone: 

my $formatter = DateTime::Format::RFC3339->new();

# Track minimum airmass, and record moon info at that point:
my $airmass_min = 1000;
my ($moon_pct, $moon_dist);

my $time = $start->clone();
$time->set_time_zone('UTC');

while ($time <= $end) {
    $target->datetime($time);

    my $airmass = $target->airmass();

    # Change timezone as needed for labeling: 
    $time->set_time_zone($timezone);
    # Create a mouseover label for the datapoint:
    my $time_label =  $time->hm();
    my $label = sprintf("%s, %0.2f",  $time_label, $airmass);
    my $datestring = $formatter->format_datetime($time);
    push @data, [$datestring, $airmass, $label];

    # Do the same thing for the Moon as well: 
    $moon->datetime($time);
    $sun->datetime($time);
    my $moon_airmass = $moon->airmass();
    my ($ra_moon, $dec_moon) = $moon->radec; 
    my ($ra_sun, $dec_sun) = $sun->radec; 


    # Moon illumination formula from Meeus, "Astronomical Algorithms".
    # Formulae 46.1 and 46.2 in the 1991 edition, using the
    # approximation cos(psi) \approx -cos(i).  Error should be no more
    # than 0.0014 (p. 316).

    my $moon_illum =  0.5 * (1. - sin($dec_sun)*sin($dec_moon) -
			     cos($dec_sun)*cos($dec_moon)*
			     cos($ra_sun - $ra_moon)) * 100;

    my $moon_distance_deg = Astro::PAL::palDsep($ra_moon,
						$dec_moon, 
						$ra_target,
						$dec_target) *
						    Astro::PAL::DR2D; 

    $label = sprintf("Moon %0.0f%% @ %0.0f&deg;",  $moon_illum,
		     $moon_distance_deg);
    push @moon_data, [$datestring, $moon_airmass, $label];

    # See if we want to save moon info: 
    if ($airmass <= $airmass_min) {
	$airmass_min = $airmass;
	$moon_pct = $moon_illum;
	$moon_dist = $moon_distance_deg;
    }

    # Time arithmetic is always safest in UTC: 
    $time->set_time_zone('UTC');
    $time->add( minutes=>5 );
}

# Create the graph, and start adding data: 

# Title to print
my $title = "Airmass plot";
if ($target_input ne '') {
    $title .= " for $target_input;";
}

$title .=  sprintf(" Moon %0.0f%% @ %0.0f&deg;", $moon_pct, $moon_dist);

my $subtitle = "RA = $original_ra, Dec = $dec\; $observatory_name "
    . "Lat, long = $observatory_latitude, $observatory_longitude";

my $date_label = "";
if ($timezone !~ /UTC/) {
    $date_label = "(local date at sunset)";
}

my $graph_width = 1000;

my $graph = SVG::TT::Graph::TimeSeries->new({
    'height'              => 700,
    'width'               => $graph_width,
    'stagger_x_labels'    => 0,
    'rotate_x_labels'     => 1,
    'show_data_points'    => 1,
    'show_data_values'    => 1,
    'rollover_values'     => 1,
    'x_label_format'      => '%H:%M',
    
    'area_fill'           => 0,
    'min_scale_value'     => $max_airmass,
    'max_scale_value'     => 1,
    'scale_divisions'     => 0.2,
    'timescale_divisions' => '2 hours',
    'timescale_time_zone' => $timezone,

    'show_x_title'        => 1,
    'x_title'             => "Time in zone $timezone on $start_date $date_label",

    'show_y_title'        => 1,
    'y_title'             => 'Airmass',

    'show_graph_title'    => 1,
    'graph_title'         => $title,
    'show_graph_subtitle' => 1,
    'graph_subtitle'      => $subtitle,

    'tidy'                => 0,
    'key'                 => 0,
    'key_position'        => 'bottom',
    'style_sheet'         => $stylesheet,
});




$graph->add_data(
		 { data => \@data,
		   title => "$target_input",
	       }
		 );

$graph->add_data(
		 { data => \@moon_data,
		   title => 'Moon',
	       }
		 );

# Now create a new dataset for lines to show the sunrise and sunset
# times: 

my @sunset_data = ();
$sunset->set_time_zone($timezone);
my $sunset_string = $formatter->format_datetime($sunset);
push @sunset_data, ($sunset_string, 100);
push @sunset_data, ($sunset_string, -1);

$graph->add_data({
    data => \@sunset_data,
    title => 'Sunset',
});

my @sunrise_data = ();
$sunrise->set_time_zone($timezone);
my $sunrise_string = $formatter->format_datetime($sunrise);
push @sunrise_data, ($sunrise_string, 100);
push @sunrise_data, ($sunrise_string, -1);

$graph->add_data({
    data => \@sunrise_data,
    title => 'Sunrise',
});

my $transit_start_label = "";
my $transit_start_frac = 0;

if ($jd_start ne "") {
    my @start_data = ();
    my $transit_start = 
	DateTime::Format::Epoch::JD->parse_datetime($jd_start);
    $transit_start->set_time_zone($timezone);
    $transit_start_label = $transit_start->hm;
    if ($transit_start >= $start) {
	$transit_start_frac = ($transit_start->epoch - $start->epoch)/$span;
	my $transit_start_string = $formatter->format_datetime($transit_start);
	push @start_data, ($transit_start_string, 100);
	push @start_data, ($transit_start_string, -1);
	$graph->add_data({
	    data => \@start_data,
	    title => 'Transit start',
	});
    } else {
	$transit_start_frac = 0;
    };

}

my $transit_end_label = "";
my $transit_end_frac = 0;

if ($jd_end ne "") {
    my @end_data = ();
    my $transit_end = DateTime::Format::Epoch::JD->parse_datetime($jd_end);
    $transit_end->set_time_zone($timezone);
    $transit_end_label = $transit_end->hm;
    if ($transit_end <= $end) {
	my $transit_end_string = $formatter->format_datetime($transit_end);
	push @end_data, ($transit_end_string, 100);
	push @end_data, ($transit_end_string, -1);
	$transit_end_frac = ($transit_end->epoch - $start->epoch)/$span;
	$graph->add_data({
	    data => \@end_data,
	    title => 'Transit end',
	});
    } else {
	$transit_end_frac = 1;
    };
}



# Get the SVG code:
my $svg = $graph->burn();

# Strip the header info before the actual SVG code:
$svg =~ s%^(.*)<svg%<svg%s;
# But save it because we may need it later:
my $xml_header = $1;

# Now add a few more things to it, before the end:

# Put in the gradient, at the beginning of the SVG code:
$svg =~ s%(<svg[^>]+>)%$1\n$gradient_def\n%;

# Replace the class definition of the graphBackground rectangle with
# the fill gradient that we designed above
$svg =~ s% class=\"graphBackground\"\s*/>% fill=\"url(\#blue_fade)\"/>%;

# If a start and end for a transit was specified, then we display a
# rectangle on the plot, along with code to change its shade and
# display a label if it is moused over:

if ( ($jd_start ne "") and ($jd_end ne "") ) {

# The <rect> element with the blue_fade (previously with the class 
# "graphBackground" until a few statements ago) is where the
# coordinates of the visible graph area are defined, so by matching
# against these, then we can determine the coordinate system to use to
# position some other elements on the plot:

    $svg =~ m/rect x=\"(\d+)\" y=\"(\d+)\" width=\"(\d+)\" height=\"(\d+)\" fill=\"url\(\#blue_fade/;

    # Now use the matches to the parenthesized expressions in that regex
    # to set our coordinates:
    my $graph_start_x = $1;
    my $graph_start_y = $2;
    my $graph_width = $3;
    my $graph_height = $4;

    my $transit_height= $graph_height;
    my $transit_width = ($transit_end_frac -
			 $transit_start_frac)*$graph_width;
    my $transit_start_x = ($graph_width*$transit_start_frac) 
	+ $graph_start_x;
    my $transit_start_y = $graph_start_y;

    my $transit_rect_base = 
	"<rect x=\"$transit_start_x\" y=\"$transit_start_y\" " .
	"width=\"$transit_width\" height=\"$transit_height\"" ;

    my $transit_rect_mouseout = $transit_rect_base 
	. " class=\"transitRectMouseOut\" />\n" ;

    my $transit_rect_mousein = $transit_rect_base 
	. " class=\"transitRectMouseIn\" />\n" ;

    my $label_x = $transit_start_x + 15;
    my $label_y = $transit_start_y + 20;

    # Try to keep the label from getting clipped at the end of the plot:
    if ($label_x > $graph_width - 180) {
	$label_x = $graph_width - 180;
    }

    my $transit_label = "<text x='$label_x' " 
	. "y='$label_y' class='transitLabel'>Transit from "
	. " $transit_start_label to $transit_end_label</text>";
    $transit_label =~ s/0([1-9]):/$1:/g;

    my $transit_group = "$transit_rect_mouseout"
	."<g class='transit_group'>$transit_rect_mousein"
	. "$transit_label \n </g>";

    # Finally, add in the code we just defined, right after the 
    # gradient fill:
    $svg =~ s%( fill=\"url\(\#blue_fade\)\"/>)%$1\n$transit_group%;

}

# If the user called for inverted color, we add a subclass to a number
# of the document elements that grabs an alternate color scheme from
# the stylesheet.  Look for the "_inverted" elements in the style
# sheet to change colors (except for the background of the whole plot,
# which is coded above). 

if ($invert) {
    $svg =~ s/class=([\"\'])
	              (line[123] |
		       dataPointLabel[12] |
		       transitRectMouseIn |
		       transitLabel)/
		       class=${1}${2}_inverted/gx;
}

my $moon_factor = 1.5*(1 + $moon_pct/100);
my $style = sprintf('style="stroke-width:%0.1fpx;stroke-dasharray:%0.1f %0.1f"',
		    $moon_factor, $moon_factor, 8-$moon_factor);
# Update line 2 style (Moon) with thickness reflecting phase:
$svg =~ s/(class=[\"\'] line2(_inverted)? [\"\'])/
		       ${1}$style/gx;

if ($elevation_labels) {
    # Get all matches to the left-hand axis labels (generated
    # automatically by SVG TT Graph) and use them to create corresponding
    # right-hand labels that are in elevation units:
    my @left_labels;
    @left_labels = ( $svg =~ m%text x=\"[\d\.]+\" y=\"[\d\.]+\" class=\"yAxisLabels\">[\d\.]+<%g);

    my $left_label;
    my $right_label_string = '';

    my $new_x = $graph_width - 2;

    foreach $left_label (@left_labels) {
	# Capture the coordinates with a regex:
	$left_label =~ m%text x=\"([\d\.]+)\" y=\"([\d\.]+)\" class=\"yAxisLabels\">([\d\.]+)%;
	my $xpos = $1;
	my $ypos = $2;
	my $airmass_val = $3;
	# Get the elevation for that airmass:
	my $elevation_val = 90 - rad2deg(asec($airmass_val));
	my $elevation_print = sprintf("%d", $elevation_val);
	my $right_label = "<text x=\"$new_x\" y=\"$ypos\"  " .
	    "class=\"yAxisLabels\">$elevation_print</text>\n";
	$right_label_string = $right_label_string . $right_label;
    }

    # Having constructed this list of right-hand labels, print them into
    # the code at the end: 
    $svg =~ s%(</svg>)%$right_label_string\n$1%;

    # If we've done this, we need to make the view box for the SVG a
    # little bigger so the right-hand labels don't get clipped:
    my $new_width = $graph_width * 1.02;
    $svg =~ s/viewBox=\"0 0 $graph_width (\d+)/viewBox=\"0 0 $new_width $1/;
    my $graph_height = $1;
    my $right_label_pos = $new_width * 0.99;
    my $right_label_ypos = sprintf("%0.1f", $graph_height * 0.5);

    # Add a right-hand y-axis label:
    $svg =~ s%(</svg>)% <text x=\"$right_label_pos\" y=\"$right_label_ypos\"
	transform=\"rotate\(90,$right_label_pos,$right_label_ypos\)\"
	class=\"yAxisTitle\">Elevation (degrees)</text>\n$1%;
}

# Finally, print a header and print the SVG code:

# Work around SVG handling by iPad, iPhone, 5.x and earlier versions
# of Safari, and 3.x and earlier versions of Firefox; these browsers
# support SVG, but not if it is in-lined with HTML; they need an XML
# header instead, and no content besides the SVG code:
if ($ENV{HTTP_USER_AGENT} =~ m/iPhone |
                               iPad |
                               Version\/[0..5](\.\d)?(\.\d)?\s+Safari |
                               Firefox\/[0..3]\./ix) {
    print $q->header(-type => "application/xhtml+xml; charset=utf-8",
		     -cookie => \@cookies,
		     );
    print $xml_header;
    print $svg;
} else {
# Otherwise embed SVG code in HTML, which allows a
# little nicer positioning:
    print $q->header(
		     -type => "text/html; charset=utf-8",
		     -cookie => \@cookies,
		     );
    print $q->start_html(-title => $title,
			 -style => $stylesheet,
			 -head => $q->Link({-rel => 'shortcut icon',
					    -href => 'airmass.ico',
					    -type => 'image/x-icon',
					}),
			 );
    print "<div style=\"text-align: center\">\n";
    print $svg;
    print "</div>\n";
    print $q->end_html;
}
# End of main routine.



sub fatal_error {

# Simple wrapper to allow us to die gracefully if a problem occurs, by
# printing out an HTML header and then a (hopefully) useful error
# message. 

    my ($title, $message) = @_;

    print $q->header(-type => "text/html; charset=utf-8");
    print $q->start_html(-title => $title);
    print $q->h2("Fatal error in input");
    print $q->p($message);
    print $q->end_html;
    die;
}

sub define_cookie {
    my ($cookie_name, $cookie_value) = @_;
    # Expire cookies after 3 months:
    my $cookie_expires = '+3M';
    my $cookie = CGI::Cookie->
	new(-name    => $cookie_name,
	    -value   => $cookie_value,
	    -expires => $cookie_expires,
	    );
    return $cookie;
}
    
sub DateTime::hm {
  # Just a simple shortcut for formatting ease, since the 
  # DateTime package doesn't provide a built-in method for 
  # only hours and minutes.  This also rounds to the nearest minute,
  # rather than truncating. 
  my $dt = shift;
  my ($h,$m,$s) = split(/:/, $dt->hms()); 
  $m++ if ($s >= 30); 
  # But if rounding up crosses an hour boundary, handle that:
  if ($m == 60) {
      $m = 0;
      $h = ($h == 23) ? 0 : $h + 1;
  }
  return sprintf("%d:%02d", $h, $m);
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
