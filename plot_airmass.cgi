#!/usr/bin/perl 

# Script to create an SVG plot of airmass vs. time for an astronomical
# target.  Input parameters are provided by airmass.cgi, which calls
# this script. 

# Copyright 2012 Eric Jensen, ejensen1@swarthmore.edu.
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
use DateTime::Format::Epoch::JD;
use SVG::TT::Graph::TimeSeries;
use CGI;
use CGI::Cookie;
use LWP::Simple;

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
    # Add a period to the name for later printing ease:
    $observatory_name .= ". ";
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

$timezone = $temporary_timezone;

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

push @cookies, define_cookie('invert', 
			     $invert);


my $jd = $q->param("jd");
my $jd_start = $q->param("jd_start");
my $jd_end = $q->param("jd_end");

# Start date:
my $start_date_string = $q->param("start_date");
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


my $ra = $q->param("ra");
my $dec = $q->param("dec");
my $target_input = $q->param("target");

if (($ra eq '') and ($target_input ne '')) {
    # No RA given, try to resolve name with Simbad:
    # First vet the name against a regular expression; since we pass
    # it back out in a URL, we want to be careful about what is in
    # that string:
    if ($target_input =~ m%\A([A-Za-z0-9\-\+\.\s\*\[\]\(\)\/\'\"]+)\Z%) {
	my $target_name = $1;
	# Convert spaces in the name to plusses:
	$target_name =~ s/ +/\+/g;
	my $simbad_url
	    = "http://vizier.cfa.harvard.edu/viz-bin/nph-sesame/" 
	    . "-oxp/SN?${target_name}";
	my $simbad_output = get($simbad_url);

	# Try to match a pattern in the output to get coords:
	if ($simbad_output 
	    !~ m%<jpos>(\d\d:\d\d:\d\d\.?\d*)\s+
	               ([+-]?\d\d:\d\d:\d\d\.?\d*)</jpos>%x) { 
	    my $err_title =  "Error - no coordinates";
	    my $err_message = "No RA given and could not parse/resolve"
		. "name: $target_input";
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

my $target = new Astro::Coords( ra => $ra,
				dec => $dec,
				type => 'J2000',
				);

if (not defined($target)) {
    my $err_title = "Could not parse coordinates";
    my $err_message = "Could not parse the coordinates RA = [$ra]" 
	. " and/or Dec = [$dec].<br />  (Note: square brackets are not part"
	. " of the input, but are used to show whether the coords "
	. " have spaces or may be empty strings.";
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
	# Start at noon UTC on requested day:
	$now = DateTime->new(
			     year => $year,
			     month => $month,
			     day => $day,
			     hour => '12',
			     time_zone => 'UTC',
			     );
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

my $start_date = $start->ymd();

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

# Title to print
my $title = "Airmass plot";
if ($target_input ne '') {
    $title .= " for $target_input";
}
my $subtitle = "RA = $ra, Dec = $dec\; $observatory_name "
    . "Lat, long = $observatory_longitude, $observatory_latitude";

my $graph = SVG::TT::Graph::TimeSeries->new({
    'height'              => 700,
    'width'               => 1000,
    'stagger_x_labels'    => 0,
    'rotate_x_labels'     => 1,
    'show_data_points'    => 1,
    'show_data_values'    => 1,
    'rollover_values'     => 1,
    'x_label_format'      => '%H:%M',
    
    'area_fill'           => 0,
    'min_scale_value'     => 2.4,
    'max_scale_value'     => 1,
    'scale_divisions'     => 0.2,
    'timescale_divisions' => '2 hours',

    'show_x_title'        => 1,
    'x_title'             => "Time in zone $timezone on $start_date",

    'show_y_title'        => 1,
    'y_title'             => 'Airmass',

    'show_graph_title'    => 1,
    'graph_title'         => $title,
    'show_graph_subtitle' => 1,
    'graph_subtitle'      => $subtitle,

    'tidy'                => 0,
    'key'                 => 0,
    'style_sheet'         => $stylesheet,
});



my $time = $start->clone();

my @data = ();

while ($time <= $end) {
    $target->datetime($time);
    my $airmass = $target->airmass();
    $time->set_time_zone($timezone);
    # Create a mouseover label for the datapoint:
    my $time_label =  $time->hms();
    # Strip the seconds:
    $time_label =~ s/:\d\d$//;
    # Strip a leading zero if present:
    $time_label =~ s/^0//;
    my $label = sprintf("%s, %0.2f",  $time_label, $airmass);
    push @data, [$time->datetime(), $airmass, $label];
    $time->set_time_zone('UTC');
    $time->add( minutes=>5 );
}

$graph->add_data(
		 { data => \@data,
	       }
		 );

# Now create a new dataset for lines to show the sunrise and sunset
# times: 

my @sunset_data = ();
$sunset->set_time_zone($timezone);
push @sunset_data, ($sunset->datetime(), 100);
push @sunset_data, ($sunset->datetime(), -1);

$graph->add_data({
    data => \@sunset_data,
    title => 'Sunset',
});

my @sunrise_data = ();
$sunrise->set_time_zone($timezone);
push @sunrise_data, ($sunrise->datetime(), 100);
push @sunrise_data, ($sunrise->datetime(), -1);

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
    $transit_start_label = $transit_start->hms;
    $transit_start_label =~ s/:\d\d$//;
    if ($transit_start >= $start) {
	$transit_start_frac = ($transit_start->epoch - $start->epoch)/$span;
	push @start_data, ($transit_start->datetime(), 100);
	push @start_data, ($transit_start->datetime(), -1);
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
    $transit_end_label = $transit_end->hms;
    $transit_end_label =~ s/:\d\d$//;
    if ($transit_end <= $end) {
	push @end_data, ($transit_end->datetime(), 100);
	push @end_data, ($transit_end->datetime(), -1);
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
		       dataPointLabel1 |
		       transitRectMouseIn |
		       transitLabel)/
		       class=${1}${2}_inverted/gx;
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
    
