#!/usr/bin/perl

# Web interface to provide a form for calculating transit visibility. 

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


use CGI;
use CGI::Cookie;
use Math::Trig;

use JSON qw(decode_json); 

use warnings;
use strict;

# Some observatory names have non-ASCII characters: 
use utf8;
use Observatories qw(%observatories_asia
		     %observatories_western_north_america
		     %observatories_australia
		     %observatories_europe
		     %observatories_africa
		     %observatories_south_america
		     %observatories_eastern_us
		     );

# Get the user's approxiomate location from IP address: 
my $info = `curl --silent https://ipinfo.io/json`; 
my ($lat, $lon) = split(",", (decode_json $info)->{loc});

#  See if they have cookies set for default values of observatory
#  coordinates and other parameters:
my %cookies = CGI::Cookie->fetch;

# For inclusion in the text, get the number of transiting planets by
# just counting lines in our target file:
my $target_file = 'transit_targets.csv';
my $n_planets = `wc -l $target_file`;
# Get just the numeric part:
$n_planets =~ s/^\s*(\d+) .*$/$1/;
# Ignore the header line: 
$n_planets -= 1;

# Same for TESS file: 
my $n_planets_tess = `wc -l toi_targets.csv`;
$n_planets_tess =~ s/^\s*(\d+) .*$/$1/;
$n_planets_tess -= 1;

# Same for Exoplanet Watch
my $n_planets_exowatch = `wc -l exoplanet_watch_targets.csv`;
$n_planets_exowatch =~ s/^\s*(\d+) .*$/$1/;
$n_planets_exowatch -= 1;


# Declare the settings variables that we'll use:
my ($observatory_string, $observatory_latitude, $observatory_longitude,
    $observatory_timezone, $days_to_print, $days_in_past,
    $minimum_start_elevation, $minimum_end_elevation, 
    $minimum_ha, $maximum_ha, $baseline_hrs,
    $minimum_depth, $minimum_priority, $maximum_V_mag, $show_unc,
    $use_utc, $use_AND, $twilight, $max_airmass, $min_plot_el,
    );


# In getting values from the cookies, the logic may seem a little
# redundant here.  But it turns out that it is possible for the cookie
# to exist, without it actually having a value.  So even after we
# assign the variable from the cookie, we still check to see if it is
# defined, and if not, give it a default value.

if (defined $cookies{'observatory_string'}) {
    $observatory_string = $cookies{'observatory_string'}->value;
} 
if (not defined $observatory_string) {
    $observatory_string = '';
}

# If they don't have a cookie set for latitude and longitude, 
# then default to what we get from their IP address:
if (defined $cookies{'observatory_latitude'}) {
    $observatory_latitude = $cookies{'observatory_latitude'}->value;
} 
if (not defined $observatory_latitude) {
    $observatory_latitude = $lat;
}

if (defined $cookies{'observatory_longitude'}) {
    $observatory_longitude = $cookies{'observatory_longitude'}->value;
}
if (not defined $observatory_longitude) {
    $observatory_longitude = $lon;
}

if (defined $cookies{'observatory_timezone'}) {
    $observatory_timezone = $cookies{'observatory_timezone'}->value;
}
if (not defined $observatory_timezone) {
    $observatory_timezone = '';
}

if (defined $cookies{'Use_UTC'}) {
    $use_utc = $cookies{'Use_UTC'}->value;
}
if (not defined $use_utc) {
    $use_utc = 0;
}

if (defined $cookies{'Show_uncertainty'}) {
    $show_unc = $cookies{'Show_uncertainty'}->value;
}
if (not defined $show_unc) {
    $show_unc = 1;
}

my $unc_checked = $show_unc ? "checked" : "";    

if (defined $cookies{'Use_AND'}) {
    if ($cookies{'Use_AND'}->value eq 'and') {
	$use_AND = 1; 
    } else {
	$use_AND = 0;
    }
} else {
    $use_AND = 0;
}

if (defined $cookies{'days_to_print'}) {
    $days_to_print = $cookies{'days_to_print'}->value;
}
if (not defined $days_to_print) {
    $days_to_print = 3;
}

if (defined $cookies{'days_in_past'}) {
    $days_in_past = $cookies{'days_in_past'}->value;
}
if (not defined $days_in_past) {
    $days_in_past = 0;
}

if (defined $cookies{'minimum_start_elevation'}) {
    $minimum_start_elevation 
	= $cookies{'minimum_start_elevation'}->value;
}
if (not defined $minimum_start_elevation) {
    $minimum_start_elevation = '30';
}

if (defined $cookies{'minimum_end_elevation'}) {
    $minimum_end_elevation 
	= $cookies{'minimum_end_elevation'}->value;
}
if (not defined $minimum_end_elevation) {
    $minimum_end_elevation = '30';
}

if (defined $cookies{'minimum_ha'}) {
    $minimum_ha = $cookies{'minimum_ha'}->value;
}
if (not defined $minimum_ha) {
    $minimum_ha = '';
}

if (defined $cookies{'maximum_ha'}) {
    $maximum_ha = $cookies{'maximum_ha'}->value;
}
if (not defined $maximum_ha) {
    $maximum_ha = '';
}

if (defined $cookies{'minimum_depth'}) {
    $minimum_depth = $cookies{'minimum_depth'}->value;
}
if (not defined $minimum_depth) {
    $minimum_depth = 0;
}


if (defined $cookies{'baseline_hrs'}) {
    $baseline_hrs = $cookies{'baseline_hrs'}->value;
}
if (not defined $baseline_hrs) {
    $baseline_hrs = 1;
}

if (defined $cookies{'minimum_priority'}) {
    $minimum_priority = $cookies{'minimum_priority'}->value;
}
if (not defined $minimum_priority) {
    $minimum_priority = 0;
}

if (defined $cookies{'maximum_V_mag'}) {
    $maximum_V_mag = $cookies{'maximum_V_mag'}->value;
}
if (not defined $maximum_V_mag) {
    $maximum_V_mag = ''
}

# Setting of Sun elevation that defines night:
if (defined $cookies{'twilight'}) {
    $twilight = $cookies{'twilight'}->value;
}
if (not defined $twilight) {
    $twilight = -12;
}

# Setting of maximum airmass to plot:
if (defined $cookies{'max_airmass'}) {
    $max_airmass = $cookies{'max_airmass'}->value;
}
# Make sure this has a sensible value: 
if ((not defined $max_airmass) or ($max_airmass < 1)) {
    $max_airmass = 2.4;
}

# Find elevation equivalent of the max airmass:
$min_plot_el = sprintf("%0.1f", 90 - rad2deg(asec($max_airmass)));

# If no cookie was set in one or more cases, then the above variables
# have all been given sensible defaults by now, so some starting
# values will be filled in.

# Now use this set of data to create two arrays, one giving the labels
# for the dropdown, and one giving the values associated with that
# label.  For the value, we concatentate the three individual fields
# and separate them with semicolons, for later parsing in the script
# that finds the events. 

my ($key, $value);
my @obs_labels = ();
my @obs_values = ();

my $timezone_used;


my @observatory_list = ( 
			 \%observatories_africa,
			 \%observatories_asia,
			 \%observatories_australia,
			 \%observatories_europe,
			 \%observatories_eastern_us,
			 \%observatories_western_north_america,
			 \%observatories_south_america,
			 );

my @observatory_label = ( "Africa",
			  "Asia",
			  "Australia / New Zealand",
			  "Europe",
			  "North America - East",
			  "North America - Central, West, and Hawaii",
			  "South America",
			  );




my $obs_ref;
foreach $obs_ref (@observatory_list) {
    my %obs = %$obs_ref;
    my $category = shift @observatory_label;
    push @obs_values, " ";
    push @obs_labels, "<optgroup label=\"$category\">";
    foreach $key (sort(keys %obs)) {
    
	if (defined $obs{$key}->{timezone}) {
	    $timezone_used =  $obs{$key}->{timezone};
	} else {
	    # Make a timezone string based on hours from UTC:
	    $timezone_used = sprintf("%+03d00",
				     $obs{$key}->{timezone_integer});
	}
	$value = sprintf("%s;%s;%s;%s", $obs{$key}->{latitude}, 
			 $obs{$key}->{longitude}, $timezone_used,
			 $key);
	push @obs_values, $value;
	push @obs_labels, $key;
    }
    push @obs_values, " ";
    push @obs_labels, "</optgroup>";
}

# And at the end of the list, we include an option for manual entry: 

push @obs_values, " ";
push @obs_labels, "<optgroup label=\"Manual coordinate entry:\">";
my $manual_entry_label = "Enter specific latitude/longitude/timezone";
my $manual_entry_value = "Specified_Lat_Long";
push @obs_values, $manual_entry_value;
push @obs_labels, $manual_entry_label;
push @obs_values, " ";
push @obs_labels, "</optgroup>";


# Get the index number of the final entry in the list, which is the
# one for manually-specified latitude or longitude; we put this number
# into a Javascript call below, so that we can select this element at
# the same time we show the latitude/longitude entry boxes.
my $specified_index = $#obs_values - 1;

my $q = CGI->new();

#print $q->header;
print $q->header(-type => 'text/html',
		 -charset => 'utf-8');


# If referred from the Exoplanet Watch page, set a variable that
# will result in that target option being checked; otherwise
# the NASA Exoplanet Archive option is selected: 

my $Archive_checked = "Checked";
my $ExoWatch_checked = "";

if ($ENV{'HTTP_REFERER'} =~ /exoplanet-watch/) {
    $Archive_checked = "";
    $ExoWatch_checked = "Checked";
}

# Add some Javascript functions to the header; these will let 
# us show/hide some elements on the fly, as needed; and they also pull
# in source code for the date-picker widget.


print << "END_1";

<html>
<head>
<meta content="text/html; charset=utf-8" http-equiv="content-type">

<meta property="og:url"                content="https://astro.swarthmore.edu/transits/" />
<meta property="og:type"               content="website" />
<meta property="og:title"              content="Plan exoplanet transit observations" />
<meta property="og:description"        content=" This form calculates
observability of the known transiting exoplanets or TESS Objects of Interest
 (TOIs) are observable from a given location at a given time.
 The output includes transit time and elevation, and links to further
 information about each object, including finding charts and airmass
 plots." />
<meta property="og:image" content="https://astro.swarthmore.edu/transits/transit_finder_example_small.png" />

<script type="text/javascript">

   function hide(obj) {
       obj1 = document.getElementById(obj);
       obj1.style.display = 'none';
   }

   function show(obj) {
       obj1 = document.getElementById(obj);
       obj1.style.display = 'block';
   }

   function show_lat_long(optionValue) {
       if(optionValue=='Specified_Lat_Long') {
	   show('lat_long');
       } else {
	   hide('lat_long');
       }
   }

   function show_hide(optionValue,showValue,elementID) {
       if(optionValue==showValue) {
	   show(elementID);
       } else {
	   hide(elementID);
       }
   }

</script>

<script type="text/javascript" 
    src="./src/date-picker-v5/js/lang/en.js">
</script>

<script type="text/javascript" 
    src="./src/date-picker-v5/js/datepicker.packed.js">
</script>

<link href="./src/date-picker-v5/css/datepicker.css" 
    rel="stylesheet" type="text/css" />


<title>Transit Finder</title>
    
<link rel="stylesheet" href="page_style.css" type="text/css">

<!-- Add some styles that are used to show/hide certain elements
    dynamically if Javascript is supported.  Put these in-line rather
    than in the above external style sheet for portability, since
    these are important to the functioning of the page, not just
    appearance.  This way, the page will function properly even if the
    external sheet cannot be loaded.
-->

<style type="text/css">

.hidden {
	display:none;
}

.showing {
	display:block;
}

.show_hide {
	display:none;
}

label {
    width: 200px;
    display: block;
    vertical-align: middle;
    text-align: right;
    float:left;
}

.right {
  width: 40px;
  text-align: right;
}

input[type=submit] {
  height:30px; 
  width:80px;
  border-radius: 6px; 
  text-align: center;
}

/* The Modal (background) */
.modal {
  display: none; /* Hidden by default */
  position: fixed; /* Stay in place */
  z-index: 1; /* Sit on top */
  padding-top: 100px; /* Location of the box */
  left: 0;
  top: 0;
  width: 100%; /* Full width */
  height: 100%; /* Full height */
  overflow: auto; /* Enable scroll if needed */
  background-color: rgb(0,0,0); /* Fallback color */
  background-color: rgba(0,0,0,0.4); /* Black w/ opacity */
}


/* Modal Content */
.modal-content {
  position: relative;
  background-color: #fefefe;
  margin: auto;
  padding: 0;
  border: 1px solid #888;
  width: 80%;
  box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2),0 6px 20px 0 rgba(0,0,0,0.19);
  animation-name: animatetop;
  animation-duration: 0.4s
}

/* Modal Header */
.modal-header {
  padding: 2px 16px;
  color: white;
}

/* Modal Body */
.modal-body {padding: 2px 16px;}

/* Modal Footer */
.modal-footer {
  padding: 2px 16px;
  color: white;
}

/* The Close Button */
.close {
  color: #888;
  float: right;
  font-size: 28px;
  font-weight: bold;
}

.close:hover,
.close:focus {
  color: black;
  text-decoration: none;
  cursor: pointer;
}

</style>


<!-- In case the browser does not support Javascript, or has it turned
    off, here we set an alternate style.  When Javascript is enabled,
    we show or hide the manual-entry boxes for latitude, longitude,
    and timezone automatically by using a script to change the CSS
    attributes of the <DIV> that contains those boxes.  If Javascript
    is off, we want them always to be showing, since they cannot be
    toggled. So here, we set the CSS style associated with the
    "hidden" class to actually be the same as "showing", overriding
    the declarations just above. 
-->

<noscript>
<style type="text/css">
    
    .hidden {
      display:block;
    }

</style>
</noscript>



</head>
<body>
<h2>Find Exoplanet Transits</h2>

<p> This form calculates which transits of the $n_planets known
 transiting exoplanets or $n_planets_tess TESS Objects of Interest
 (TOIs) are observable from a given location at a given time.  Specify
 a time window, an observing location (either an observatory from the
 list or choose "Enter latitude/longitude" at the end of the list),
 and optionally any filters (e.g. minimum transit depth or elevation).
 The output includes transit time and elevation, and links to further
 information about each object, including finding charts and airmass
 plots.  (There are also stand-alone pages for generating finding
 charts (<a
 href="https://astro.swarthmore.edu/finding_charts.cgi">annotated
 JPGs</a> or using <a href="aladin_finder.html">Aladin Lite</a>) and <a
 href="https://astro.swarthmore.edu/airmass.cgi">airmass plots</a> for any target.)  </p>

<span style="color:purple"> 
<em> 
Latest updates (<a href="updates.html">full update list</a>):<br> 
<ul>
<li> October 2022: Aladin finder charts now use Gaia DR3 data, and
    show Gaia variable star and eclipsing binary candidates.
</li>
<li> October 2022: You can now plan your night of observing by selecting
    the transits you plan to observe, which will hide any events that
    overlap with the selected event(s) (taking into account the
					out-of-transit baseline),
    leaving only those that don't overlap.  Use the checkboxes next to
the object name.
</li>
</ul>
</em>
</span>

<FORM METHOD="GET" ACTION="print_transits.cgi"> 

<h3>Target list:</h3>
<div class="indent p-style">
(All target lists are updated nightly.)<br/>
<INPUT TYPE="radio" NAME="single_object" VALUE="0" onclick="show_hide(this.value,'1','ephem_block')"
$Archive_checked
/> NASA Exoplanet Archive database ($n_planets planets; <a
				    href="transit_targets.csv">CSV
				    file</a>)  <br/>
<INPUT TYPE="radio" NAME="single_object" VALUE="2" onclick="show_hide(this.value,'1','ephem_block')"
/> TESS Objects of Interest ($n_planets_tess TOIs; <a
				    href="toi_targets.csv">CSV
			     file</a>; <span style="color:#6699cc;cursor:pointer" id="about-tess">
			   Apply to join the TESS Follow-up Program</span>)
<div class="modal" id="tess-sg1-info">
 <div class="modal-content">
  <div class="modal-header">
    <span class="close">&times;</span>
    <h2>About TESS Followup</h2>
  </div>
  <div class="modal-body">
    <p>
       While all TESS Objects of Interest (TOIs) are made public
       through this ephemeris prediction tool, the <a
       href='https://tess.mit.edu/followup/apply-join-tfop'
       target='_blank'>TESS Follow-up Observing Program (TFOP)</a> is
       a mission-led effort to coordinate ground-based follow-up
       observations of TOIs by professional, student, and citizen
       astronomers. A separate but similar ephemeris prediction tool
       is maintained for the TFOP team that includes daily updates to
       the status and disposition of each TOI, along with a
       description of observations needed for each active TOI. The
       TFOP team welcomes all observers with time-series photometry
       experience to submit applications to join TFOP Sub Group 1
       (SG1). A description of the TFOP application process is
       provided <a
       href='https://tess.mit.edu/followup/apply-join-tfop'
       target='_blank'>here</a>.
    </p>
  </div>
 </div>
</div>
<br/>
<INPUT TYPE="radio" NAME="single_object" VALUE="3" onclick="show_hide(this.value,'1','ephem_block')"
$ExoWatch_checked /> <a
href="https://exoplanets.nasa.gov/exoplanet-watch/about-exoplanet-watch/overview/"
target='_blank'>Exoplanet Watch</a> targets ($n_planets_exowatch planets; <a
				    href="exoplanet_watch_targets.csv">CSV
			     file</a>)
<br/>
<INPUT TYPE="radio" NAME="single_object" VALUE="1" onclick="show_hide(this.value,'1','ephem_block')"
/> Single object
    with given ephemeris (date and elevation filters below still
    apply).<br/>
<p>
<div id="ephem_block" class="show_hide">
<i>Note: to search for a specific known transiting exoplanet, don\'t use this.  Choose
"NASA Exoplanet Archive database" above, then enter the target name below in the
box labeled "Only show targets with names matching this string."  Use
this only if you want to manually enter the ephemeris for some
other target (or try an alternate ephemeris for a known target). </i>
</p>

<div id="ephemeris" style="margin-left:2mm;">

<p>
<label class="ephem"> RA (J2000): &nbsp; </label> 
<input type="text" size="15" class="ephem" name="ra"> (hh:mm:ss or decimal <em>hours</em>)
</p>
<p>
<label class="ephem"> Dec (J2000): &nbsp;</label> 
<input type="text" size="15" class="ephem"  name="dec"> (dd:mm:ss or decimal degrees)
</p>
<p>
<label class="ephem"> BJD of mid-transit: &nbsp; </label>
<input type="text" size="15" class="ephem"
    name="epoch"  style="text-align:center" />
</p>
<p>
<label class="ephem">Period (days): &nbsp; </label>
 <input type="text" size="15" class="ephem"
    name="period"  style="text-align:center" />
</p>
<p>
<label class="ephem">Transit duration (hours): &nbsp;</label>
<input type="text" size="15" class="ephem"
    name="duration"  style="text-align:center" />
</p>
<p>
<label class="ephem">Transit depth (ppt): &nbsp;</label>
<input type="text" size="15" class="ephem"
    name="depth"  style="text-align:center" />
</p>
<p>
<label class="ephem">Target name: &nbsp;</label>
<input type="text" size="15" class="ephem"
    name="target"  style="text-align:center" /> (<em>optional, for labeling only</em>)
</p>
</div>
</div>
</div>


END_1



# Now print out the dropdown for observatories, selecting the one
# specified by the cookie (if any):

my $i = 0;  # Index to step through the list of values
my $observatory;

print $q->h3("Observatory:");
print "<div class='indent'>\n";
print $q->p("Choose an observatory, or choose \"manual coordinate
entry\" at end of list:");
print '<div class="p-style">';
print "<SELECT id=\"obs\" name=\"observatory_string\"  ";
#print " onchange=\"show_lat_long(this.value)\">\n";
print " onchange=\"show_hide(this.value,'Specified_Lat_Long','lat_long')\">\n";

foreach $observatory (@obs_labels) {
    $value = $obs_values[$i];
    if ($observatory =~ /optgroup/i) {
	print "$observatory\n";
    } else {
	print "   <OPTION value=\"$obs_values[$i]\"";
	if ($value eq $observatory_string) {
	    # Matches the cookie - set this to be the selected option:
	    print " selected = \"selected\" ";
	}
	print ">$observatory</OPTION>\n";
    }
    $i++;
}

# If the initial setting we read from the cookie is that for manual
# entry, we will set those lat/long/timezone boxes to be showing by
# default; otherwise they are hidden.  This hiding/showing is
# accomplished by giving different CSS classes to the DIV containing
# those boxes:

my $lat_long_class;
if ($observatory_string =~ /$manual_entry_value/) {
    $lat_long_class = "showing";
} else {
    $lat_long_class = "hidden";
}

print "</SELECT></div>\n\n";

# Set the correct checkbox to be checked on or off by default, based
# on their past preferences from the cookie:
my ($utc_on_string, $utc_off_string);
if ($use_utc) {
    $utc_on_string = "Checked";
    $utc_off_string = "";
} else {
    $utc_off_string = "Checked";
    $utc_on_string = "";
}

# Similarly for AND vs OR on elevation constraints:
my ($AND_on_string, $AND_off_string);
if ($use_AND) {
    $AND_on_string = "Checked";
    $AND_off_string = "";
} else {
    $AND_off_string = "Checked";
    $AND_on_string = "";
}


print << "END_2";

<p> <INPUT TYPE="radio" NAME="use_utc" VALUE="1" $utc_on_string/> 
Use UTC &nbsp;/&nbsp;
<INPUT TYPE="radio" NAME="use_utc" VALUE="0" $utc_off_string/> 
Use observatory\'s local time.
</p>
</div>

<DIV id="lat_long" class="$lat_long_class" style="margin-left:2cm;">

<!-- Add an extra message to the user if scripting is disabled and
    these boxes are not toggled on/off automatically by the drop-down
    menu. 
-->

<noscript>
<p />
<p> <i> Note: the latitude/longitude/timezone entry boxes below are
    ignored unless "$manual_entry_label" is selected in the menu
    above. </i>
</p>
</noscript>

<p />
Observatory latitude (degrees): <INPUT NAME="observatory_latitude"
    size="8" value="$observatory_latitude"/> (North is positive.)
<br />
Observatory longitude (degrees): <INPUT NAME="observatory_longitude"
    size="8" value="$observatory_longitude"/> (East is
positive.) <br />

Observatory timezone:
 <SELECT name="timezone">

<p />

END_2

# The observatory timezone is used to convert UT to local time
# (including corrections for daylight savings time.  Some likely
# possible values (for the US) are America/New_York, America/Chicago,
# America/Phoenix, America/Denver, America/Los_Angeles, or
# Pacific/Honolulu.  If you need to add more names to the list and
# need the proper string for them, you can run:

#  perl -e 'use DateTime; \
#     print join("\n", DateTime::TimeZone->names_in_country( "US")); ' 

# from the command line to get a list of possible values for a given
# country, replacing 'US' with a different two-letter country code if
# desired.

# Now build up the select options list for the timezone selector,
# using the cookie to set the default value.

# Note that, for manual entry, the observatory latitude/longitude
# entry and the observatory timezone entry are *not* linked at all -
# it's quite possible to, e.g., list transits occurring at an
# observatory in Australia in terms of their time in EDT.  This can be
# useful, but also potentially confusing.

my @zones = ("UTC",      
	     "EST5EDT", 
	     "CST6CDT", 
	     "MST7MDT", 
	     "America/Phoenix",
	     "PST8PDT", 
	     "HST", 
	     "WET",
	     "CET",
	     "EET",
	     "Africa/Johannesburg",
             "Asia/Moscow",
             "Asia/Kolkata",
             "Asia/Shanghai",
             "Asia/Tokyo",
             "Australia/Brisbane",
	     );     

my @zone_titles = ( "UTC",
		    "U.S. - Eastern Time", 
		    "U.S. - Central Time", 
		    "U.S. - Mountain Time", 
		    "U.S. - Arizona (Mountain time but no DST)", 
		    "U.S. - Pacific Time", 
		    "U.S. - Hawaii", 
		    "Western European Time",
		    "Central European Time", 
		    "Eastern European Time",
		    "South African Standard Time",
		    "Moscow Standard Time", 
		    "Indian Standard Time", 
		    "China Standard Time", 
		    "Japan Standard Time", 
		    "Australian Eastern Standard Time",
		    ); 

my $zone;
$i = 0;  # Index to step through the list of values
foreach $zone (@zones) {
    print "   <OPTION value=\"$zone\" ";
    if ($observatory_timezone eq $zone) {
	# Matches the cookie - set this to be the selected option:
	print " selected = \"selected\" ";
    }
    print " > $zone_titles[$i] </OPTION>\n";
    $i++;
}

print "</SELECT>\n";

print "</DIV> <p />\n";

# Now print the rest of the form:
print << "END_3";

</p>

<h3>Date window:</h3>
<div class="indent">
<p title="Entering 'today' searches 24 hours from current time; specifying a
date starts search at local noon at observatory on that date.">
Base date for transit list (mm-dd-yyyy or <i>'today'</i>): 
<input type="text" value="today" size="10"
    id="start_date" name="start_date"  style="text-align:center" />
</p>

<script type="text/javascript">
  datePickerController.createDatePicker(
	     {formElements:{"start_date":"m-ds-d-ds-Y"}}
					);
</script>

<p>
From that date, show transits for the next 
 <INPUT NAME="days_to_print" VALUE="$days_to_print" size="4" autofocus /> days.  
<br />
(Also include transits from the previous 
 <INPUT NAME="days_in_past" VALUE="$days_in_past" size="4"/> days.) 
</p> 
</div>

<h3>Constraints:</h3>

<h4> Elevation: </h4>
<div class="indent">
<p>
Only show transits with an elevation (in degrees) of at least: 
</p>
 
<table style="border-spacing:0"><tr>
<td>at ingress:</td><td style="padding:2"> <INPUT NAME="minimum_start_elevation" VALUE="$minimum_start_elevation"
    size="2"/> </td> <td rowspan=2 style="border-top:1px solid black; border-bottom:1px solid black">&nbsp;</td>
    <td rowspan=2 style="border-left:1px solid black"> &nbsp; Combine
    constraints with <INPUT TYPE="radio" NAME="and_vs_or" VALUE="and"
 $AND_on_string
/> AND <INPUT TYPE="radio" NAME="and_vs_or" VALUE="or" $AND_off_string
    /> OR.</td></tr>
<tr><td>at egress:</td><td style="padding:2"> <INPUT NAME="minimum_end_elevation"
    VALUE="$minimum_end_elevation" size="2"/> </td></tr>
</table>  

<p> Unspecified elevation constraints default to 0. Constraints are
    evaluated <em>at night</em>, i.e. to be shown as observable an event has to meet
    that elevation constraint during nighttime hours. </p>
</div>

<p>
<INPUT TYPE="submit" VALUE="Submit">
</p>

<h4> Hour angle: </h4>
<div class="indent">
 <p> Only show transits with hour angle between <INPUT NAME="minimum_ha" VALUE="$minimum_ha" size="2"/> 
and <INPUT NAME="maximum_ha" VALUE="$maximum_ha" size="2"/> hours.  Constraints are evaluated only at ingress and egress.  Unspecified HA constraints default to &plusmn;12 (i.e. no constraint). 
</p>
</div>


<h4> Out-of-transit baseline: </h4>
<div class="indent">
 <p> Observability (with above elevation, daylight, and
     HA constraints) will also be shown at points up to 
     <INPUT NAME="baseline_hrs" VALUE="$baseline_hrs" size="2"/>
    hours before ingress and after egress to show how much 
    out-of-transit baseline can be observed.  (This can be set to a
    minimum of 0.5 hours, but an hour or more is recommended.)
</p>
<p style="padding-left: 24px; text-indent: -24px;"> <input
    type="checkbox" name="show_unc" value="1" $unc_checked> Extend baseline by ephemeris uncertainty.</p>
</div>

<h4> Space observing: </h4> 
<div class="indent">
<p style="padding-left: 24px; text-indent: -24px;"> <input type="checkbox" name="space" value="1"> Ignore all elevation, hour angle, and 
    day/night constraints; show all transits.  Useful for space-based
    observing (but can generate <em>lots</em> of output if no target
    constraints specified). </p>
</div>

<h4> Depth: </h4> 
<div class="indent">

<p>
Only show transits with a depth of at least <INPUT
    NAME="minimum_depth" VALUE="$minimum_depth" size="3"/> parts per
    thousand (ppt).
</p>

</div>

<h4> V magnitude: </h4> 
<div class="indent">

<p>
Only show targets brighter than V = <INPUT
    NAME="maximum_V_mag" VALUE="$maximum_V_mag" size="2"/>. 
</p>

</div>

<h4> Name: </h4> 
<div class="indent">

<p>
Only show targets with names matching this string: <INPUT
    NAME="target_string"  size="28"/>.<br />
<i>(Not case sensitive; can be a Perl regular expression.)</i></p>
</div>

<p>
<INPUT TYPE="submit" VALUE="Submit">
</p>

<h3>Output format and labeling:</h3>
<p>
Output results as: <br />
<INPUT TYPE="radio" NAME="print_html" VALUE="1" Checked/> HTML table <br />
<INPUT TYPE="radio" NAME="print_html" VALUE="2" /> CSV file for
    parsing by script. <br />
<INPUT TYPE="radio" NAME="print_html" VALUE="0"/> CSV file
for calendar import. (Save resulting output to a text file,
then import into your observing calendar, e.g., <a
href="http://www.google.com/support/calendar/bin/answer.py?hl=en&answer=37118">
import into Google Calendar.)</a></p>

<p>Day/night definition: start night at Sun altitude of &nbsp;

<select name="twilight">

END_3

# List the options for Sun altitude, and construct the drop down list,
# marking the user's previously-selected value as the chosen one:
my $sun_el;
my @sun_els = (-1, -6, -12, -18);
my @sun_titles = ("&nbsp;&nbsp;&minus;1 degrees (sunset)",
		  "&nbsp;&nbsp;&minus;6 degrees (civil twilight)",
		  "&minus;12 degrees (nautical twilight)",
		  "&minus;18 degrees (astronomical twilight)"
		  );                           

$i = 0;  # Index to step through the list of values
foreach $sun_el (@sun_els) {
    print "   <OPTION value=\"$sun_el\" ";
    if ($twilight eq $sun_el) {
	# Matches the cookie - set this to be the selected option:
	print " selected = \"selected\" ";
    }
    print " > $sun_titles[$i] </OPTION>\n";
    $i++;
}

print << "END_4";

</SELECT>

    <br />
The above choice determines both which events are displayed (since
part of the transit must be at night), and which parts of an event are 
<span style="color:MediumVioletRed">color-coded to indicate
    daytime</span>. 
</p>


<p>Maximum airmass to show in airmass plots: &nbsp;

 <INPUT NAME="max_airmass" VALUE="$max_airmass" size="4" /> 
<br /> (Current airmass value of $max_airmass is elevation of $min_plot_el degrees.)
</p>

<p>
<INPUT TYPE="submit" VALUE="Submit">
</FORM></p>

<p><hr/></p>

<p> If this tool is useful for your research, please consider citing it, e.g. 
<a href="https://ui.adsabs.harvard.edu/abs/2013ascl.soft06007J/abstract"> 
Jensen E. L. N. 2013. <i>Tapir: A Web Interface for Transit/Eclipse
    Observability</i>, Astrophysics Source Code Library ascl:1306.007</a>.
</p>

<p>
This page uses input ephemeris data from the <a
href="https://exoplanetarchive.ipac.caltech.edu/">NASA Exoplanet
    Archive</a> and <a
    href="https://exofop.ipac.caltech.edu/tess/">ExoFOP-TESS</a>. 
The finding charts provided here make use of images from the Digitized Sky
Survey, which are subject to <a
href="http://archive.stsci.edu/dss/copyright.html">copyright</a>, and can be acknowledged <a
href="http://archive.stsci.edu/dss/acknowledging.html">like this</a>. 
</p>

<p>
 This
tool is part of <a
href="http://astro.swarthmore.edu/~jensen/tapir.html">the Tapir
package</a> for planning astronomical observations; the <a
href="https://github.com/elnjensen/Tapir">source code</a> is
freely available.  
</p>

<p>
This page was created by <a
href="http://astro.swarthmore.edu/~jensen/">Eric Jensen</a>. 
Feedback welcome!  Send <a
href="mailto:ejensen1\@swarthmore.edu?Subject=Feedback on transit form"
>here</a>.
</p>

</body>

<script type="text/javascript">

// Vars and functions for the modal dialog
// These have to come after the code for the dialog is in place. 
    var modal = document.getElementById("tess-sg1-info");

// Get the button that opens the modal
    var btn = document.getElementById("about-tess");

// Get the <span> element that closes the modal
    var span = document.getElementsByClassName("close")[0];

// When the user clicks on the button, open the modal
    btn.onclick = function() {
	modal.style.display = "block";
    }

// When the user clicks on <span> (x), close the modal
    span.onclick = function() {
	modal.style.display = "none";
    }

// When the user clicks anywhere outside of the modal, close it
    window.onclick = function(event) {
	if (event.target == modal) {
	    modal.style.display = "none";
	}
    } 

// Make sure the ephemeris block is showing only if selected:
    target_list = document.querySelector('input[name="single_object"]:checked').value;
    show_hide(target_list, 1, 'ephem_block');

// Likewise for the observatory coordinate manual entry: 
    obs_selected = document.getElementById('obs').value;
    show_hide(obs_selected,'Specified_Lat_Long','lat_long');


</script>


</html>

END_4
