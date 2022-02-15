#!/usr/bin/perl 

# Code to create a finding chart, and output it to a browser.  Input
# parameters come from finding_charts.cgi, and the finding chart is
# created by calling the script get_finding_charts.pl.

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
use LWP::Simple;
use Astro::Coords;
use HTML::Entities;

use strict;
use warnings;

my $q = CGI->new();
my @cookies = ();

# Contact info provided in the fatal_error subroutine:
my $script_contact_person = 'Eric Jensen, ejensen1@swarthmore.edu';

# Get some input settings from the URL:

my $ra = num_only($q->param("ra"));
my $dec = num_only($q->param("dec"));
my $field_width = num_only($q->param("field_width"));
my $field_height = num_only($q->param("field_height"));
my $show_detector = num_only($q->param("show_detector"));
my $detector_width = num_only($q->param("detector_width"));
my $detector_height = num_only($q->param("detector_height"));

# This gets checked later: 
my $target_input = $q->param("target");

# Check to see if they set the parameter to invert colors:
my $invert = num_only($q->param("invert"));
if ((not defined $invert) or ($invert eq "")) {
    $invert = 0;
}

push @cookies, define_cookie('invert', 
			     $invert);



my $target_name;

# Choose an alternate Vizier mirror if one isn't working:
my $vizier_mirror = "https://cdsweb.u-strasbg.fr/cgi-bin/";
#my $vizier_mirror = "https://vizier.cfa.harvard.edu/viz-bin/";

if (($ra eq '') and ($target_input ne '')) {
    # No RA given, try to resolve name with Simbad:
    # First vet the name against a regular expression; since we pass
    # it back out in a URL, we want to be careful about what is in
    # that string:
    if ($target_input =~ m%\A([A-Za-z0-9\-\+\.\s\*\[\]\(\)\/\'\"]+)\Z%) {
	$target_name = $1;
	# Convert spaces in the name to underscores:
	$target_name =~ s/ +/_/g;
	my $simbad_url = $vizier_mirror . "nph-sesame/" 
	    . "-oxp/SN?${target_name}";
	my $simbad_output = get($simbad_url);

	# Try to match a pattern in the output to get coords:
	if ($simbad_output 
	    !~ m%<jpos>\s*(\d\d:\d\d:\d\d\.?\d*)\s+
	               ([+-]?\d\d:\d\d:\d\d\.?\d*)\s*</jpos>%x) { 
	    my $err_title =  "Error - no coordinates";
	    my $err_message = "No RA given and could not parse/resolve"
		. " name: $target_input \n"
		. "<p> The output from Vizier was: "
		. "<pre> $simbad_output </pre>" ;
	    fatal_error($err_title, $err_message);
	} else {
	    $ra = $1;
	    $dec = $2;
	}
    } else {
	my $err_title = "Error in object name";
	my $err_input = encode_entities($target_input);
	my $err_message = "Input does not look like an object name:"
	    . " <pre>$err_input</pre>." .
	    " If you feel this should have been resolvable by"
	    . " Simbad or NED, please contact $script_contact_person.";
	fatal_error($err_title, $err_message);
    }
} elsif ((($ra eq '') or ($dec eq '')) and ($target_input eq '')) {
    fatal_error("Error - no coordinates", 
		"Must provide either RA/Dec or an object name.");
}

if (not defined $target_name) {
    if (defined $target_input) {
	if ($target_input =~ m%\A([A-Za-z0-9\-\+\.\s\*\[\]\(\)\/\'\"]+)\Z%) {
	    $target_name = $1;
	    # Get rid of double dots:
	    $target_name =~ s/\.{2,}/\./g;
	} else {
	    $target_name = 'Specified coords';
	}
    } else {
	$target_name = 'Specified coords';
    }
}

# Reformat RA and Dec as needed; may have plus signs if passed via
# URL; replace either plusses or spaces with colons, unless the plus
# is at the start of the string:
$ra  =~ s/[\s\+]+/:/g;
$dec =~ s/[\s]+/:/g;
$dec =~ s/(\d)[\+]+/$1:/g;

# Create an Astro::Coords object with these coords, simply to check
# and see if they are valid coordinates:
my $coords = new Astro::Coords( ra => $ra,
				dec => $dec,
				type => 'J2000',
				);

if ((not defined($coords)) or ($ra >= 24)) {
    my $err_title = "Could not parse coordinates";
    my $err_message = "Could not parse the coordinates RA = [$ra]" 
	. " and/or Dec = [$dec].<br />  Note: square brackets are not part"
	. " of the input, but are used to show whether the coords "
	. " have spaces or may be empty strings. <br />"
	. "Also note that RA must be in <b>hours</b> (either decimal "
	. "or sexagesimal), not degrees, and therefore must be < 24.";
    fatal_error($err_title, $err_message);
} else {
    ($ra, $dec) = $coords->radec();
}


my $default_field_width = 40;
my $max_field_size = 75;
# Simple regex for matching floating point numbers with optional surrounding 
# whitespace.  Doesn't match 3.0E1 notation, nor numbers with leading
# decimal points or signs, as (a) a number with a leading decimal
# point is too small for a field size, and (b) the sign is 
# unnecessary.
my $number_regex = qr{^\s*\d+\.?\d*\s*$};

# Check the field size:
if (defined $field_width) {
    # If empty string or only spaces, use default:
    if ($field_width =~ m/^\s*$/) {
	$field_width = $default_field_width;
    } elsif  ($field_width !~ $number_regex) {
	# Needs to look like a number:
	my $err_title = "Could not parse field width";
	my $err_message = "Could not parse the entered field width: "
	    . "[$field_width]." 
	    . " Please enter only digits (and possibly an optional "
	    . "decimal point).";
	fatal_error($err_title, $err_message);
    } else {
	# Field width is valid, so save as a cookie:
	push @cookies, define_cookie('field_width', 
				     $field_width);
    }

} else {
    $field_width = $default_field_width;
}  


if ($field_width > $max_field_size) {
    $field_width = $max_field_size;
}


if (defined $field_height) {
    # If empty string or only spaces, use default:
    if ($field_height =~ m/^\s*$/) {
	$field_height = $field_width;
    } elsif  ($field_height !~ $number_regex) {
	# Needs to look like a number:
	my $err_title = "Could not parse field height";
	my $err_message = "Could not parse the entered field height." 
	    . " Please enter only digits (and possibly an optional "
	    . "decimal point).";
	fatal_error($err_title, $err_message);
    } else {
	# Field height is valid, so save as a cookie:
	push @cookies, define_cookie('field_height', 
				     $field_height);
    }
} else {
    $field_height = $field_width;
}

# Check out whether they want to show the detector outline or not:
my $detector_string;
if ($show_detector) {
    push @cookies, define_cookie('show_detector', 
				     $show_detector);
    # Check to see if the width looks like a number:
    if ($detector_width !~ $number_regex) {
	my $err_title = "Could not parse detector width";
	my $err_message = "Could not parse the entered detector width." 
	    . " Please enter only digits (and possibly an optional "
	    . "decimal point).";
	fatal_error($err_title, $err_message);
    } else {
	# Detector width is valid, so save as a cookie:
	push @cookies, define_cookie('detector_width', 
				     $detector_width);
    }
    if (defined $detector_height) {
    # If empty string or only spaces, use default:
	if ($detector_height =~ m/^\s*$/) {
	    $detector_height = $detector_width;
	} elsif  ($detector_height !~ $number_regex) {
	    # Needs to look like a number:
	    my $err_title = "Could not parse detector height";
	    my $err_message = "Could not parse the entered detector height." 
		. " Please enter only digits (and possibly an optional "
		. "decimal point).";
	    fatal_error($err_title, $err_message);
	} else {
	    # Detector height is valid, so save as a cookie:
	    push @cookies, define_cookie('detector_height', 
					 $detector_height);
	}
    } else {
	$detector_height = $detector_width;
    }
    $detector_string = "--detector-width=$detector_width "
	. " --detector-height=$detector_height ";
} else {
    $detector_string = " ";
}

my $invert_string;
		     
if ($invert) {
    $invert_string = "--invert";
} else {
    $invert_string = "";
}

# At this point, we should have valid input, so get the image:
my $command = "echo \"$target_name ,. $ra ,. $dec\" | "
    . "./get_finding_charts.pl --directory \"/tmp\" --stdout --quiet "
    . " --height=$field_height --width=$field_width $detector_string"
    . " $invert_string";
my $image = `$command`;

# Finally, print a header and print the image data:

print $q->header(
		 -type => "image/jpg",
		 -cookie => \@cookies,
		 );
print $image;


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
