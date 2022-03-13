#!/usr/bin/perl

# Web interface for calculating airmass vs. time for a given target. 

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

use warnings;
use strict;

use Observatories qw(%observatories_asia
		     %observatories_western_north_america
		     %observatories_australia
		     %observatories_europe
		     %observatories_africa
		     %observatories_south_america
		     %observatories_eastern_us
		     );


#  See if they have cookies set for default values of observatory
#  coordinates and other parameters:
my %cookies = CGI::Cookie->fetch;

# Declare the settings variables that we'll use:
my ($observatory_string, $observatory_latitude, $observatory_longitude,
    $observatory_timezone, $days_to_print, $days_in_past, $minimum_elevation,
    $minimum_start_end_elevation, $minimum_depth, $minimum_priority,
    $use_utc, $invert, $invert_string, $no_invert_string,
    $max_airmass, $min_plot_el,
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

# Only set the lat / long from the cookie if they want the manual 
# value and don't have the full string defined.
if ( ($observatory_string eq '') or 
     ($observatory_string eq "Specified_Lat_Long") ) {
    if (defined $cookies{'observatory_latitude'}) {
	$observatory_latitude = $cookies{'observatory_latitude'}->value;
    } 
    if (defined $cookies{'observatory_longitude'}) {
	$observatory_longitude = $cookies{'observatory_longitude'}->value;
    }
    if (defined $cookies{'observatory_timezone'}) {
	$observatory_timezone = $cookies{'observatory_timezone'}->value;
    }

}

if (not defined $observatory_latitude) {
    $observatory_latitude = '';
}

if (not defined $observatory_longitude) {
    $observatory_longitude = '';
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

if (defined $cookies{'invert'}) {
    $invert = $cookies{'invert'}->value;
}
if (not defined $invert) {
    $invert = 0;
}

if ($invert) {
    $invert_string = "Checked";
    $no_invert_string = "";
} else {
    $no_invert_string = "Checked";
    $invert_string = "";
}


# Setting of maximum airmass to plot:
if (defined $cookies{'max_airmass'}) {
    $max_airmass = $cookies{'max_airmass'}->value;
}
if (not defined $max_airmass) {
    $max_airmass = 2.4;
}

# Find elevation equivalent of the max airmass:
$min_plot_el = sprintf("%0.1f", 90 - rad2deg(Math::Trig::asec($max_airmass)));

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

print $q->header;
print "<link rel=\"icon\" href=\"airmass.ico\" />\n";

# Add some Javascript functions to the header; these will let 
# us show/hide some elements on the fly, as needed; and they also pull
# in source code for the date-picker widget.

print << "END_1";

<html>
<head>
  <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type">

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

   function toggle_visibility(id) {
       var e = document.getElementById(id);
       if(e.style.display == 'block') {
	   e.style.display = 'none';
	   document.getElementById('obs').options[0].selected = "selected";   
       }
       else {
	   e.style.display = 'block';
	   document.getElementById('obs').options[$specified_index].selected = "selected";   
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


<title>Airmass Plots</title>
    
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
<h2>Plot airmass</h2>

<p> 
This form allows you to make a plot of airmass vs. time for a given
    astronomical target, by specifying either the coordinates, or an
    object name to be resolved by Simbad or NED.
</p>

<FORM METHOD="GET" ACTION="plot_airmass.cgi"> 

END_1

# Now print out the dropdown for observatories, selecting the one
# specified by the cookie (if any):

my $i = 0;  # Index to step through the list of values
my $observatory;

print $q->p("Choose an observatory, or manual latitude/longitude entry:");
print '<div class="p-style">';
print "<SELECT id=\"obs\" name=\"observatory_string\"  ";
print " onchange=\"show_lat_long(this.value)\">\n";

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

print "</SELECT>\n\n";

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

print << "END_2";

<p/>
<p> <INPUT TYPE="radio" NAME="use_utc" VALUE="1" $utc_on_string/> 
Use UTC &nbsp;/&nbsp;
<INPUT TYPE="radio" NAME="use_utc" VALUE="0" $utc_off_string/> 
Use observatory\'s local time.
</p>
</div>

<DIV id="lat_long" class="$lat_long_class">

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
	     "EET",     
	     "CET",     
	     "WET",
	     "Australia/Brisbane",
	     "Africa/Johannesburg",
	     );     

my @zone_titles = ( "UTC",
		    "U.S. - Eastern Time", 
		    "U.S. - Central Time", 
		    "U.S. - Mountain Time", 
		    "U.S. - Arizona (Mountain time but no DST)", 
		    "U.S. - Pacific Time", 
		    "U.S. - Hawaii", 
		    "Eastern European Time",
		    "Central European Time", 
		    "Western European Time",
		    "Australian Eastern Standard Time",
		    "South African Standard Time"
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

<p>
Date for airmass plot (mm-dd-yyyy or <i>'today'</i>): 
<input type="text" value="today" size="15"
    id="start_date" name="start_date"  style="text-align:center" />
</p>

<script type="text/javascript">
  datePickerController.createDatePicker(
	     {formElements:{"start_date":"m-ds-d-ds-Y"}}
					);
</script>

<p>
Target name:
<input type="text" size="15"
    name="target"  style="text-align:center" />
<i>&nbsp;(Will be resolved by Simbad/NED if no coordinates given.)</i>
</p>

<p>
RA (J2000): <INPUT TYPE="text" name="ra"> (hh:mm:ss or decimal
					  <em>hours</em>)
</p>
<p>
Dec (J2000): <INPUT TYPE="text" name="dec"> (dd:mm:ss or decimal degrees)
</p>

<p>

<INPUT TYPE="radio" NAME="invert" VALUE="0" $no_invert_string
    /> Dark background <br />
<INPUT TYPE="radio" NAME="invert" VALUE="1" 
    $invert_string /> White background (better for printing) <br /> 
</p>


<p>Maximum airmass to show in airmass plots: &nbsp;

 <INPUT NAME="max_airmass" VALUE="$max_airmass" size="4" /> 
<br /> (Current airmass value of $max_airmass is elevation of $min_plot_el degrees.)
</p>

<p>
<INPUT TYPE="submit" VALUE="Submit">
</p>
</FORM>

<p> This page was created by <a
href="http://astro.swarthmore.edu/~jensen/">Eric Jensen</a>.  This
tool is part of <a
href="http://astro.swarthmore.edu/~jensen/tapir.html">the Tapir
package</a> for planning astronomical observations; the <a
href="https://github.com/elnjensen/Tapir">source code</a> is
freely available.  </p>

<p>
Feedback welcome!  Send <a
href="mailto:ejensen1\@swarthmore.edu?Subject=Feedback on airmass form"
>here</a>.
</p>
</body>

<script type="text/javascript">
// Make sure visibility is correct on load for the observatory coordinate manual entry: 
    obs_selected = document.getElementById('obs').value;
    show_lat_long(obs_selected);
</script>


</html>

END_3
