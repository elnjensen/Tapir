#!/usr/bin/perl -nw

# Script to create finding charts by grabbing DSS images.
# Reads an input file, constructs a URL from the coordinates, fetches
# the image from the DSS server, and saves the image.  Optionally, it
# can resolve an object name via Simbad and get the coordinates that
# way.  Can be run from the command-line, or called by the web
# interface create_finding_charts.cgi.

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

# The finding charts provided here make use of images from the
# Digitized Sky Survey, which are subject to the copyright summary at
# http://archive.stsci.edu/dss/copyright.html.  Please consider
# acknowledging their use in your work, as described at
# http://archive.stsci.edu/dss/acknowledging.html.


# Requirements:

#  perl, ImageMagick (for 'convert' and 'identify' commands).
# If you need a version of ImageMagick for Mac OSX, you can get it
# from the main ImageMagick site, or there is an easy-to-use installer
# at http://cactuslab.com/imagemagick/.
#   
# Also requires the Perl packages LWP::Simple and Getopt::Long, but I
# believe that those are part of the standard distribution for most if
# not all Perl installations.


# Created by Eric Jensen, Swarthmore College, Swarthmore, PA USA
# Contact me at ejensen1@swarthmore.edu with any questions, comments,
# feature additions, or bug fixes.

#
# Usage:   get_finding_charts.pl inputfile
#     Alternatively, it can read coords from standard input, e.g.
#          grep "HD" my_coord_file | get_finding_charts.pl
#     to only make a finding chart for stars in your list with HD
#     names. 
# It can also resolve names, so you could also do
#          echo "T Tau" | get_finding_charts.pl
# to have it resolve the name "T Tau" into coordinates, and then make
# a finding chart with default parameters. 

# Expected format for input text file; columns should be separated by
# commas or ",." (comma plus period).
# Column 0:    object name; just used to name the output file
#              and label the image.
# Column 1: RA in h:m:s (J2000), colon-separated
# Column 2: Dec in d:m:s (J2000), colon-separated
# -or-
# Just a Simbad-resolvable object name, one per line.  The script
# tries to figure out what kind of input each line is; if there are
# fewer than three comma-separated fields on a given line, it tries to
# interpret that whole line as an object name and resolve it with
# Simbad.

# Command-line options are explained in the 'usage' subroutine just
# below.  For most of these, you can change the defaults below in the
# script.

use warnings;
use strict;

sub usage
{
    my $program;
    ($program = $0) =~ s,.*/,,;

    print STDERR << "END_OF_HELP";

Usage: $program coordfile
   or: echo \"Star name\" | $program

where 'coordfile' is a text file of comma-separated fields, with 
field 1 being the object name, field 2 the RA, and field 3 the Declination.
Coordinates are assumed J2000, in sexagesimal, colon-separated format.
Example input line:

GG Tau , 04:32:30.34 ,  +17:31:40.6

Text after these three fields is ignored.

Options:

 --coordinates: Resolve name to coords only, no finding chart.
 --height: Field height (N-S) in arcminutes.
 --width:  Field width (E-W) in arcminutes.
 --directory: Directory for output.
 --hardlink-from-dir: Check to see if the chart already exists in the
                      specified directory, and if so, hardlink to 
                      that file rather than creating a new one.
 --suffix: Suffix for output image; if recognized by ImageMagick, it
     sets the image type, i.e. you can use
          "--suffix .png" to get a PNG output image; but 
          "--suffix .foo" will give an error since it doesn\'t know
          how to convert to image format "foo".
 --stdout: Write image data to standard output, not to a file. 
 --detector-width: Show outline of CCD detector on chart, with
                   specified width in arcmin.  If no height is
                   given, defaults to same as width.
 --detector-height: Show outline of CCD detector on chart, with
                    specified width in arcmin.
 --guider: Show outline of guider chip on chart.
 --invert: Black stars on a white sky.
 --force: Overwrite pre-existing output file of the same name.
 --verbose: More verbose output about what is happening.
 --quiet: Don\'t print any status messages.
 --sleep: Sleep the specified number of seconds between successive
          finding charts; useful if you don\'t want to overtax an 
	  image server with rapid-fire queries, and don\'t care 
	  much about how long it takes you to make a bunch of charts.
 --skip: Number of lines to skip at the beginning of the input. Useful 
         if your input file has headers that aren\'t commented out.
 --help: Print this help.

END_OF_HELP

}


our ($coords_only, $show_detector, $show_guider, $new_suffix,
    $field_width, $field_height, $jpeg_quality_string,
    $jpeg_quality, $white_background, $text_color,
    $circle_color, $circle_color2, $detector_color, $guider_color,
    $remove_underscores, $detector_string, $guider_string,
    $scale_bar_length, $output_directory, $initial_circle_radius, $verbose,
    $detector_width, $detector_height, $guider_width, $guider_height,
    $guider_offset_x, $guider_offset_y, $print_help, $sleep_seconds,
    $original_input, $force_overwrite, $to_stdout, $quiet, $skip,
    $skipped, $hardlink_from_dir,
    );

BEGIN {

    use Getopt::Long;
    use LWP::Simple qw(get getstore is_error);
    use Digest::MD5 qw ( md5_hex );

# Read in any command-line options:
    my $success = GetOptions("coordinates" => \$coords_only, 
			    "directory=s" => \$output_directory,
			    "hardlink-from-dir=s" => \$hardlink_from_dir,
			    "guider" => \$show_guider,
			    "force" => \$force_overwrite,
			    "stdout" => \$to_stdout,
			    "help" => \$print_help,
			    "verbose" => \$verbose,
			    "quiet" => \$quiet,
			    "height=f" => \$field_height,
			    "width=f" => \$field_width,
			    "detector-height=f" => \$detector_height,
			    "detector-width=f" => \$detector_width,
			    "suffix=s" => \$new_suffix,
			    "sleep=f" => \$sleep_seconds,
			    "invert!" => \$white_background,
			    "skip=f" => \$skip,
			    );
    
    if ($print_help or not $success) {
	usage();
	exit;
    }

# Here you can change some settings:
    
# Default is that we don't show detector outline, unless
# they specify a valid width for it below:
    $show_detector = 0;
# Detector width in arcminutes, if we want to show it:
    if (defined $detector_width) {
	if ($detector_width > 0) {
	    $show_detector = 1;
	    if ((not defined $detector_height) or 
		($detector_height <= 0)) {
		$detector_height = $detector_width;
	    }
	}
    }	

# Likewise for the guider chip.  All in arcminutes, positive to the
#    right for x and up for y:
    $guider_width = 3.328;
    $guider_height = 3.975;
    $guider_offset_x = 27.5;
    $guider_offset_y = 5.0;

# Field width in arcmin:
    if (not defined($field_width)) {
	$field_width = 40;
    }


# If we're going to show the guider, we need the field to be big
# enough.  Set it to be 5% greater than the minimum required width
# based on guider size and offset:

    my $min_width = 2 * ($guider_offset_x + 0.5*$guider_width);
    my $min_height = 2 * ($guider_offset_y + 0.5*$guider_height);

# Neither one of these may be quite right, depending on how the guider
# is positioned, especially if it is offset by some substantial amount
# in both x and y, i.e. not at right angles to the chip.  What we
# really want is the farthest point, so add in quadrature:

    my $min_size = 1.05 * sqrt($min_width**2 + $min_height**2);
    # But round up to the nearest arcminute:
    $min_size = int($min_size + 1);

    if ($show_guider and ($field_width < $min_size) ) {
	print STDERR "Setting field width to $min_size arcmin in order "
	    . "to show guiding circle.\n" unless ($quiet);
	$field_width = $min_size;
    }

    if (not defined($field_height)) {
	$field_height = $field_width;
    }

    if ($show_guider and ($field_height < $min_size) ) {
	print STDERR "Setting field height to $min_size arcmin in order "
	    . "to show guiding circle.\n" unless ($quiet);
	$field_width = $min_size;
    }


# Length of scale bar to draw in arcmin:
    $scale_bar_length = 10;

# Use a shorter bar for smaller fields:
    if ($field_width <= 15) {
	$scale_bar_length =  ($field_width < 5) ? $field_width : 5 ;
    }

# Directory to save images (absolute or relative path):
    if (defined($output_directory)) {
	if (not -e $output_directory) {
	    die "Output directory \"$output_directory\" does not exist.";
	}
    } else {
	$output_directory = '.';
    }

# Here you can set the default output file format by choosing the 
# appropriate suffix to specify the file format.  Suffix can be
# any format ImageMagick understands. 

# Set defaults:
    if (defined($new_suffix)) {
	# If there's no leading period, add one:
	if ($new_suffix !~ /^\./) {
	    $new_suffix = "." . $new_suffix;
	}
    } else {
	$new_suffix = '.jpg';
    }

# Quality of the JPEG files (if using JPEG); if the output files are
# too big (in bytes, not angular size) for your purposes, try lowering 
# this value:

    $jpeg_quality = "50";

# Since the 'quality' flag only applies to JPEG, define a string here
# that will be empty if we're not using JPEG, so that it doesn't cause
# an error when included in the command:
if ($new_suffix =~ /jpe?g/i) {
    $jpeg_quality_string = "-quality $jpeg_quality";
} else {
    $jpeg_quality_string = "";
}

# If you want to invert the image (white background and black stars),
# set $white_background to "1".  If you do that, you'll want to change
# the annotation color, since yellow on white doesn't show up.  (Tweak
# colors here as desired.)

# Color for the larger, 1 arcminute circle:
    $circle_color2 = "orange";

    if ($white_background) {
	$text_color = "blue";
	$circle_color2 = "orange3";
    } else {
	$text_color = "yellow";
    }

# Color for the circle on the center of the image:
    $circle_color = "red";

# Color for the outline of the CCD:
    $detector_color = "OrangeRed";

# Color for the outline of the guider chip, and the circle with it:
    $guider_color = "pink";

# Radius of the central circle in pixels:
    $initial_circle_radius = 8;

# By default, we remove underscores from object names and replace them
# with spaces.  Set this to 0 to leave the input strings untouched.

    $remove_underscores = 1;

# See if we need to skip any lines in the input: 
    if (defined $skip) {
	$skip = int($skip);
    } else {
	$skip = 0;
    }
    # Number skipped so far: 
    $skipped = 0;

}

########## End of BEGIN block - basic customization is all above
########## here.


# The big picture is that we need to get the coordinates and then
# construct the URL to use in order to get the image, then annotate
# the image as needed.  Here's an example URL, which works as of
# 07-21-2009:
# http://archive.stsci.edu/cgi-bin/dss_search?v=poss2ukstu_red&r=09+57+05.45&d=-70+35+02.8&e=J2000&h=10.0&w=10.0&f=gif&c=none&fov=NONE&v3=

# Skip input lines that are blank or commented out:
next if ((/^\s*$/) or (/^\#/));

if ($skipped < $skip) {
    $skipped++;
    next;
}

# Some CSV files may have quoted fields; get rid of any embedded
# double quotes: 
s/\"//g;

# Split the input line on commas; also allow ",." as a possibility,
# since that's the delimeter used by the target file for my
# transit-visibility plotting code:
my @fields = split(/,\.? */);


# If there are fewer than three fields on an input line, assume that
# that line contains an object name, and try to resolve it with Simbad
# to get coords:

my ($ra1, $ra2, $ra3, $dec1, $dec2, $dec3, 
    $object_name, $save_name, $name, 
    );

if (scalar(@fields) < 3) {
    $original_input = $_;
    $object_name = $_;
    chomp($object_name);
    # Get rid of any leading or trailing spaces:
    $object_name =~ s/^ *//g;
    $object_name =~ s/ *$//g;
    $save_name = $object_name;
    # For the URL, spaces in a name have to be converted; use underscores:
    $object_name =~ s/ +/_/g;
    # Now construct the URL, and fetch it.  The 'get' function
    # is part of the LWP::Simple library.
    my $simbad_url
	    = "http://vizier.cfa.harvard.edu/viz-bin/nph-sesame/" 
	    . "-oxp/SN?${object_name}";
    if ($verbose) {
	print STDERR "Attempting to resolve name to coords via URL "
	    . "\n $simbad_url \n";
    }
    my $simbad_output = get($simbad_url);
    # The line with "<jpos>" is the one we want for coords:
    if ($simbad_output 
	!~ m%<jpos>\s*(\d\d:\d\d:\d\d\.?\d*)\s+
	         ([+-]?\d\d:\d\d:\d\d\.?\d*)\s*</jpos>%x) { 
	print STDERR "Could not parse/resolve input line: \n$original_input";
	next;
    } else {
	($ra1, $ra2, $ra3) = split(":", $1);
	($dec1, $dec2, $dec3) = split(":", $2);
	$name = $object_name;
	# Note that in printing out the coordinates, here and below
	# where we use them for a URL, we treat $dec1 as a string
	# rather than a number; this preserves the special case
	# of "-00" which otherwise would not show up as negative
	# if treated as a number.
	if (not $quiet) {
	    printf STDERR "Resolved name %s into coordinates: " . 
		"%02d %02d %05.2f %3s %02d %04.1f\n", $save_name, 
		$ra1, $ra2, $ra3, $dec1, $dec2, $dec3;
	}

    }
} else { # Had multiple input fields, at least: Name, RA, and dec
# Rename the input fields (which are already split into the @fields
# array) for readability:
    
    $name = $fields[0];
    # Get rid of any leading or trailing spaces:
    $name =~ s/^ *//g;
    $name =~ s/ *$//g;
    ($ra1, $ra2, $ra3) = split(":", $fields[1]);
    ($dec1, $dec2, $dec3) = split(":", $fields[2]);

    # See note above about treating $dec1 as a string.
    if (not $quiet) {
	printf STDERR "For star %s, using coordinates: " . 
	    "%02d %02d %05.2f %3s %02d %04.1f\n", $name, 
	    $ra1, $ra2, $ra3, $dec1, $dec2, $dec3;
    }
}

# Make sure we got coordinates: 
if (not (defined($ra1) and defined($ra2) and defined($ra3) and
	 defined($dec1) and  defined($dec2) and defined($dec3))) {
    printf STDERR "For star %s, could not parse coordinates: " . 
	    "%02d %02d %05.2f %3s %02d %04.1f\n", $name, 
	    $ra1, $ra2, $ra3, $dec1, $dec2, $dec3;
    next;
}

# If they only want coordinates, go to next entry:
next if ($coords_only);

# Construct the URL to fetch:
my $url =
    sprintf('http://archive.stsci.edu/cgi-bin/dss_search?v=' 
	    . 'poss2ukstu_red&r=%02d+%02d+%05.2f&d=%3s+%02d+%04.1f&e='
	    . 'J2000&h=%0.1f&w=%0.1f&f=gif&c=none&fov=NONE&v3=',
	    $ra1, $ra2, $ra3, $dec1, $dec2, $dec3, $field_height, 
	    $field_width);


# Construct the temporary filename to receive the downloaded image:
my $file = "/tmp/finding_chart_" . md5_hex($name, time()) . ".gif";

if (not defined $to_stdout) {
    $to_stdout = 0;
}

my $new_file;
if ($to_stdout) {
    # Use the suffix to construct the "filename" that tells 'convert'
    # to use that format, but to write to STDOUT, i.e. something like
    # "jpg:-".
    $new_file = $new_suffix . ":-";
    # Strip the leading period to get just the suffix, which tells us
    # the image format:
    $new_file =~ s/^\.//;
} else {
    my $print_name = $name;
    # In order for the name we create to play nicely with other
    # commands, we replace certain characters with underscores: 
    # spaces, parentheses, and slashes all get changed to
    # underscores: 
    $print_name =~ s%[ \s / \( \) ]+%_%g;
    # This could lead to underscores at the end of the name, which
    # we don't need:
    $print_name =~ s/_+$//;
    my $output_name = $print_name . $new_suffix;
    $new_file = $output_directory . "/" . $output_name;
    # Strip any double-slashes in the filename, e.g. if the
    # output_directory already had a trailing slash:
    $new_file =~ s%//%/%g;    

    # See if the file already exists and has non-zero size - if so,
    # we're done, just short-circuit the loop (unless the user has
    # specifically asked to overwrite):
    if ((-s $new_file) and not ($force_overwrite)) {
	print STDERR "File $new_file already exists!  (Use --force to overwrite.)"
	    . " Going to next target.\n";
	next;
    }

    # See if we need to check elsewhere for the file: 
    if ($hardlink_from_dir) {
	my $test_file = $hardlink_from_dir . $output_name;
	if (-s $test_file) {
	    print STDERR "File $test_file exists, creating " . 
		"hardlink to $new_file.\n";
	    my $status = link $test_file, $new_file or 
		die "Could not link file: $!\n";
	    next;
	}
    }
}


# Execute the command.  Again, we use a function from LWP::Simple 
# to fetch the image and save it in a file:

my $fetch_image_status = getstore($url, $file);
if (is_error($fetch_image_status)) {
    die "Failed to fetch image file to output file $file from " .
	"url $url:\nError was: $fetch_image_status";
}


# Give the user some feedback about what we're doing:
print STDERR  "Creating finding chart for object $name, output file"
    . " $new_file.\n" unless ($quiet);

# Get the image dimensions in pixels:

# First call the command line utility to get dimensions, and grep
# out the line that gives the image geometry:
my $image_dim_string = `identify -verbose $file`;

# That line should contain part of its output that looks like:
#    Page geometry: 2376x2381+0+0
# so split out those first two parts of the numeric string (groups of
# digits separated by a 'x' and preceding a '+') then assign them to
# width and height:

my ($image_width, $image_height);
if ($image_dim_string =~ m/Page geometry: *(\d+)x(\d+)\+/i) {
    $image_width = $1;
    $image_height = $2;
    if ($verbose) {
	print STDERR "Image height and width are: $image_width, $image_height \n";
    }
} else {
    die "Could not parse output from 'identify' command; is "
	. "ImageMagick installed?  Output is:\n$image_dim_string";
}


# Find the midpoint:

my $image_mid_x = 0.5 * $image_width;
my $image_mid_y = 0.5 * $image_height;


# Get image scale in pixels/arcmin:
my $pixels_per_arcmin = $image_width / $field_width;

# Scale the circle radius for the central object to be appropriate 
# for the field size:
my $circle_radius = $initial_circle_radius * ($field_width / 21.);

# Draw a 1-arcminute outer circle:
my $circle_radius_outer = $pixels_per_arcmin;


if ($show_detector) {
    # Calculate lower left (ll) and upper right (ur) corners of 
    # square showing detector:
    my $detector_half_width_pixels = $detector_width * 
	0.5 * $pixels_per_arcmin;
    my $detector_half_height_pixels = $detector_height * 
	0.5 * $pixels_per_arcmin;
    my $detector_ulx = $image_mid_x - $detector_half_width_pixels;
    my $detector_uly = $image_mid_y - $detector_half_height_pixels;
    my $detector_lrx = $image_mid_x + $detector_half_width_pixels;
    my $detector_lry = $image_mid_y + $detector_half_height_pixels;
    # Make these into a string for ImageMagick
    $detector_string = sprintf(" -fill none -stroke $detector_color "
			       . " -strokewidth 2.5 -draw "
			       . "\"rectangle %0.1f,%0.1f %0.1f,%0.1f\"",
			       $detector_ulx, $detector_uly,
			       $detector_lrx, $detector_lry);
} else {
   # Just a dummy empty string:
    $detector_string = " ";
}


if ($show_guider) {
    # Show two concentric rings indicating where the guider chip 
    # will be if the camera is rotated:

    # Radius for the inner circle:
    my $guider_radius_in = 52 * 0.5 * $pixels_per_arcmin;
    my $guider_coord_in = $image_mid_x + $guider_radius_in;
    # Radius for the outer circle:
    my $guider_radius_out = 60 * 0.5 * $pixels_per_arcmin;
    my $guider_coord_out = $image_mid_x + $guider_radius_out;
    
    # Make these into a string for ImageMagick; just need to specify 
    # center of circle and one point on it:
    my $guider_string_in = sprintf(" -stroke $guider_color -strokewidth 2 "
				   . "-draw \"circle %0.1f,%0.1f,%0.1f," 
				   ."%0.1f\" ",
				   $image_mid_x, $image_mid_y, 
				   $guider_coord_in, $image_mid_y);
    my $guider_string_out = sprintf(" -draw  \"circle " 
				    . "%0.1f,%0.1f %0.1f,%0.1f\" ",
				    $image_mid_x, $image_mid_y, 
				    $guider_coord_out, $image_mid_y);
    # Now create a box for the guide chip itself.  This is an
    # upright rectangle as shown in TheSky; if we wanted to get
    # fancier we could try to show the guider rotation, too.
    my $guider_half_width_x = $guider_width * 0.5 * $pixels_per_arcmin;
    my $guider_half_width_y = $guider_height * 0.5 * $pixels_per_arcmin;
    # Get guider center in y, keeping in mind that y increases
    # downward on the image:
    my $guider_center_x = $image_mid_x +
	($guider_offset_x * $pixels_per_arcmin);
    my $guider_center_y = $image_mid_y - 
	($guider_offset_y * $pixels_per_arcmin);
    my $guider_ulx = $guider_center_x - $guider_half_width_x;
    my $guider_lrx = $guider_center_x + $guider_half_width_x;
    my $guider_uly = $guider_center_y - $guider_half_width_y;
    my $guider_lry = $guider_center_y + $guider_half_width_y;
    my $guider_box = sprintf(" -draw \"rectangle %0.1f,%0.1f %0.1f,%0.1f\" ",
			       $guider_ulx, $guider_uly,
			       $guider_lrx, $guider_lry);
    $guider_string = " -fill none " . $guider_string_in
	. $guider_string_out . $guider_box;

} else {
   # Just a dummy empty string:
    $guider_string = " ";
}


# Set up coordinates for the central circle.  This isn't guaranteed to
# be on an object; it's just at whatever coordinate position is
# entered. 

my $circle_out_x = $image_mid_x + $circle_radius;
my $circle_out_y = $image_mid_y;

my $circle_out_x2 = $image_mid_x + $circle_radius_outer;
my $circle_out_y2 = $image_mid_y;

# and set up coords for a scale bar:
my $scale_bar_length_pixels = $scale_bar_length * $pixels_per_arcmin;
my $scale_bar_start = $image_width - 20 - $scale_bar_length_pixels;
my $scale_bar_end = $scale_bar_start + $scale_bar_length_pixels;
my $scale_bar_mid = $scale_bar_start + 0.5*$scale_bar_length_pixels;

# Position for the lower label; if the image is big, it gets shifted
# over too much and we need to compensate
my $label_start_x = $scale_bar_start;
if ($field_width > 40) {
    $label_start_x = $label_start_x - 
	0.3*($field_width - 40)*$pixels_per_arcmin;
} elsif (($field_width < 30) and ($field_width > 15)) {
    $label_start_x = $label_start_x + 
	0.15*(40 - $field_width)*$pixels_per_arcmin;
}

# Position for printing the coordinates:
my $bottom_y = $image_height - 15;

# Remove underscores from object names if desired:
my $object_label = $name;
if ($remove_underscores) {
    $object_label =~ s/_/ /g;
}

# Since in some circumstances, the name is passed in via a web form,
# and we are using it to construct a string that will be part of a
# shell command, clean it up a little bit:

# Get rid of double periods:
$object_label =~ s/\.{2,}/\./g;
# and semicolons:
$object_label =~ s/\;/_/g;


# Invert the image if desired; DSS server gives black background with
# white stars, but we can flip it.
my $invert_string;
if ($white_background) {
    $invert_string = " -negate";
} else {
    $invert_string = " ";
}

# Get a rough pointsize that scales with field width, so it doesn't
# end up looking too small:
my $pointsize = sprintf("%d", ($field_width/10.) * 14);
if ($verbose) {
    print STDERR "Point size is $pointsize\n";
}

my $offset_frac = 0.065;
if ($field_height < 40) {
    $offset_frac *= (40/$field_height)**0.7;
}
my $text_y1_offset = 1.1 * $image_height * $offset_frac;
my $text_y2_offset = 1.6 * $image_height * $offset_frac;
my $label_y_offset = 31 + 10.*$pointsize/14.;

if ($verbose) {
    print STDERR "Image scale (pixels per arcmin): $pixels_per_arcmin\n";
    print STDERR "Central x, y: $image_mid_x, $image_mid_y\n";
    print STDERR "Target circle outer x, y: $circle_out_x2, $circle_out_y2\n";
}

# Now label the image with some identifying info.  This is a long
# command, made up of the various bits that were put together over the
# course of the previous parts of the script. So let's build it up bit
# by bit here, to make it easier to change one part if desired:

my $convert_command = "convert $invert_string $jpeg_quality_string";
$convert_command .= " -font Helvetica -pointsize $pointsize";
$convert_command .= " -fill $text_color -stroke $text_color -strokewidth 3"; 

# This part draws the right angle for the N/E indicator.
# This exponent controls how the position of the indicator shifts 
# with field size:
my $scale_exponent = 0.75;
my $angle_x_start = 85 * ($field_width / 40.)**$scale_exponent;
my $angle_y_start = 45 * ($field_height / 40.)**$scale_exponent;

$convert_command .= " -draw \"line $angle_x_start,$angle_y_start "
    . " $angle_x_start,$angle_x_start\" "
    . " -draw \"line $angle_x_start,$angle_x_start "
    . " $angle_y_start,$angle_x_start\" ";

# Provide scaling of the letter positions with field size:
my $N_coords = sprintf("%d,%d", $angle_x_start - ($pointsize/3), 
		       43 * (($field_height / 40.)**$scale_exponent));
my $E_coords = sprintf("%d,%d", $angle_y_start - 0.65*$pointsize, 
		       87 * (($field_width / 40.)**$scale_exponent) 
		       + ($pointsize/3));
if ($verbose) {
    print STDERR "Coords for N are $N_coords and for E are $E_coords.\n";
}

# And here's the actual "N" and "E" text:
$convert_command .= " -strokewidth 1 -draw \"text $N_coords N\" "
    . " -draw \"text $E_coords E\" ";

# The label with the object name:
$convert_command .= " -draw \"text 80,$text_y1_offset '$object_label'\"";

# The label with the field dimensions:
$convert_command .=  " -draw \"text 80,$text_y2_offset "
    . "'$field_width\\' x $field_height\\'\" ";

# The scale bar:
$convert_command .= "-strokewidth 3 -draw \"line $scale_bar_start,15 " 
    . "$scale_bar_end,15\" ";

# The label for the scale bar:
$convert_command .= " -strokewidth 1 -draw \"text $scale_bar_mid," 
    . "$label_y_offset '$scale_bar_length\\''\" ";

# The coordinates:
$convert_command .= " -draw \"text 20,$bottom_y '$ra1 $ra2 $ra3 " 
    . "$dec1 $dec2 $dec3'\"";

# The circle for the central object:
$convert_command .= " -fill none -stroke $circle_color " .
    "-draw \"circle $image_mid_x,$image_mid_y $circle_out_x,$circle_out_y\"";

# The 1 arcmin circle for scale:
$convert_command .= " -strokewidth 2 -stroke $circle_color2 -draw " .
    "\"circle $image_mid_x,$image_mid_y $circle_out_x2,$circle_out_y2\"";

# The legend about the 1 arcmin circle:
$convert_command .= "  -strokewidth 1 -fill $circle_color2 -draw \"text " .
    "$label_start_x,$bottom_y 'Large circle is 1\\' radius'\"";

# The commands to draw the detector and guider (which could be empty
# strings if that option was not specified):
$convert_command .= " $detector_string $guider_string ";

# And then input and output filenames at the end:
$convert_command .=  " $file $new_file ";

# Now execute the command:
if ($verbose) {
    print STDERR "Executing convert command:\n $convert_command \n";
}
my $convert_status =  system($convert_command);


#my $convert_status =  system("convert $invert_string $jpeg_quality_string -font Helvetica -pointsize $pointsize -fill $text_color -stroke $text_color  -strokewidth 3  -draw \"line 85,45 85,85\" -draw \"line 85,85 45,85\" -strokewidth 1 -draw \"text 65,45 N\" -draw \"text 10,105 E\"  -draw \"text 80,$text_y1_offset '$object_label'\" -draw \"text 80,$text_y2_offset '$field_width\\' x $field_height\\'\" -strokewidth 3 -draw \"line $scale_bar_start,15 $scale_bar_end,15\" -strokewidth 1 -draw \"text $scale_bar_mid,$label_y_offset '$scale_bar_length\\''\" -draw \"text 20,$bottom_y '$ra1 $ra2 $ra3 $dec1 $dec2 $dec3'\" -fill none -stroke $circle_color -draw \"circle $image_mid_x,$image_mid_y $circle_out_x,$circle_out_y\" $detector_string $guider_string -stroke $circle_color2 -draw \"circle $image_mid_x,$image_mid_y $circle_out_x2,$circle_out_y2\"  -fill $circle_color2 -draw \"text $label_start_x,$bottom_y 'Large circle is 1\\' radius'\" $file $new_file");

if ($convert_status) {
    die "Could not annotate image; $!\n";
}

# Get rid of the temporary file:
my $delete_status = unlink($file);
if ($delete_status == 0) {
    die "Could not delete original image $file; $!\n";
}

if (defined($sleep_seconds)) {
    if ($verbose) {
	print STDERR "Sleeping for $sleep_seconds seconds...\n";
    }
    sleep(abs($sleep_seconds));
}

