#!/usr/bin/perl

use CGI;
use CGI::Cookie;

use warnings;
use strict;

#  See if they have cookies set for default values of observatory
#  coordinates and other parameters:
my %cookies = CGI::Cookie->fetch;

# Declare the settings variables that we'll use:
my ($field_height, $field_width, $detector_height, $detector_width, 
    $show_detector, $detector_on_string, $detector_off_string,
    $invert, $invert_string, $no_invert_string,
    );


if (defined $cookies{'field_height'}) {
    $field_height = $cookies{'field_height'}->value;
} 
if (not defined $field_height) {
    $field_height = '';
}

if (defined $cookies{'field_width'}) {
    $field_width = $cookies{'field_width'}->value;
} 
if (not defined $field_width) {
    $field_width = '';
}


if (defined $cookies{'detector_height'}) {
    $detector_height = $cookies{'detector_height'}->value;
} 
if (not defined $detector_height) {
    $detector_height = '';
}

if (defined $cookies{'detector_width'}) {
    $detector_width = $cookies{'detector_width'}->value;
} 
if (not defined $detector_width) {
    $detector_width = '';
}

if (defined $cookies{'show_detector'}) {
    $show_detector = $cookies{'show_detector'}->value;
} 
if (not defined $show_detector) {
    $show_detector = '';
}

if ($show_detector) {
    $detector_on_string = "Checked";
    $detector_off_string = "";
} else {
    $detector_off_string = "Checked";
    $detector_on_string = "";
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

my $q = CGI->new();

print $q->header;

print << "END_1";

<html>
<head>
  <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type">

<title>Annotated Finding Charts</title>
    
<link rel="stylesheet" href="page_style.css" type="text/css">

</head>
<body>
<h2>Make annotated finding charts</h2>

<p> 
This form allows you to make annotated finding charts for a given
astronomical target, by specifying either the coordinates, or an
object name to be resolved by Simbad or NED.  The finding charts use
data from <a
href="http://gsss.stsci.edu/SkySurveys/SkySurveys.htm">the Digitized
Sky Survey</a>, and they are annotated with the object coordinates, a
1-arcminute circle in the center for scale, and the object name if
provided, as in <a href="finding_charts/HD_209458_b.jpg">this
example</a>.  
</p>

<FORM METHOD="GET" ACTION="create_finding_chart.cgi"> 

END_1

# Now print the rest of the form:
print << "END_3";


<p>
Target name:
<input type="text" size="15"
    name="target"  style="text-align:center" />
<i>&nbsp;(Will be resolved by Simbad/NED if no coordinates given
	  below. Otherwise, it is used as a label for the 
	  plot but not for coordinates.)</i>
</p>

<p>
RA (J2000): <INPUT TYPE="text" name="ra"><br />
Dec (J2000): <INPUT TYPE="text" name="dec">
</p>

<h3>Optional:</h3>

<p>
Field width (arcmin): <INPUT TYPE="text" name="field_width" size="2"
    value="$field_width"> 
&nbsp; <i>Default: 40 arcmin. Max: 75 arcmin.</i><br />
Field height (arcmin): <INPUT TYPE="text" name="field_height" size="2"
    value="$field_height">
&nbsp; <i>Default: same as width. Max: 75 arcmin.</i><br />
   
</p>

<p>
Show outline of detector (with size specified below):<br />
<INPUT TYPE="radio" NAME="show_detector" VALUE="1" $detector_on_string
    /> Show
&nbsp;/&nbsp;<INPUT TYPE="radio" NAME="show_detector" VALUE="0" 
    $detector_off_string /> Don\'t show <br /> 
</p>

<p>
Detector width (arcmin): <INPUT TYPE="text" name="detector_width" size="2"
    value="$detector_width"> 
<br />
Detector height (arcmin): <INPUT TYPE="text" name="detector_height" size="2"
    value="$detector_height"> 
&nbsp; <i>Default: same as width.</i><br />
</p>

<p>
<INPUT TYPE="radio" NAME="invert" VALUE="0" $no_invert_string
    /> Dark background (black sky, white stars) <br />
<INPUT TYPE="radio" NAME="invert" VALUE="1" 
    $invert_string /> White background (white sky, black stars; 
					better for printing)
</p>



<p>
<INPUT TYPE="submit" VALUE="Submit">
</p>
</FORM>

<p> The finding charts provided here make use of images from the Digitized Sky
Survey, which are subject to the copyright in <a
href="http://archive.stsci.edu/dss/copyright.html">this copyright summary</a>.
Please consider <a
href="http://archive.stsci.edu/dss/acknowledging.html">acknowledging</a> their
use in your work.  </p>

<p>
This page was created by <a
href="http://astro.swarthmore.edu/~jensen/">Eric Jensen</a>.  This
tool is part of <a
href="http://astro.swarthmore.edu/~jensen/tapir.html">the Tapir
package</a> for planning astronomical observations; the <a
href="https://github.com/elnjensen/Tapir">source code</a> is
freely available.  
</p>

<p>
Feedback welcome!  Send <a
href="mailto:ejensen1\@swarthmore.edu?Subject=Feedback on finding chart form"
>here</a>.
</p>
</body>

</html>

END_3
