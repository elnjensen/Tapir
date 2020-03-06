# Tapir: Observation planning software

A longer description, and links to examples of the code in use
(including interfaces for plotting transit visibility, making airmass
plots, and making finding charts) can be found at
http://astro.swarthmore.edu/~jensen/tapir.html .


There are two main parts to the software: the form that accepts the
input parameters (observing location, any constraints), and the code
that takes this input, calculates the visibility of events, and
generates the output.  In addition, there are some supporting files,
notably a few style sheets (.css files) and an HTML template file
(.tmpl) that control the appearance of the output.  In addition, there
is separate code that generates the airmass plots and finding charts. 

## Prerequisites:

All of the code is in Perl (except for a little bit of Javascript in
the input form), and requires that the following Perl packages be
installed in order to run:

* `DateTime` - this may be installed by default in your Perl distribution,
but even so you may need to update to the latest version.  Perl has a
very flexible mechanism for handling date and time arithmetic,
including timezones, so most times are represented as DateTime objects
internally in the code.

* `DateTime::Set` - tools for creating sets of DateTime objects (in our
case, sunrises and sunsets over the desired time window).

* `DateTime::Format::Epoch` - needed for converting DateTime objects to
JDs. 

* `Astro::PAL` - the successor to the Starlink SLAlib routines.
* `Astro::Coords`

* `HTML::Template`
* `HTML::Template::Expr`

All of these packages may have prerequisites of their own.  If you
install them using the `cpan` application that is available with most
Perl distributions, the prerequisites should be handled
automatically. 


### Optional prerequisites:

* `SVG::TT::Graph`:  Required for the code for making the airmass plots. 

* `Net::Google::Spreadsheets`: If you use the script for fetching a Google docs spreadsheet, you'll
need this.  (Authentication for this has recently gotten very complicated - I'm working on a better solution here.) 

* `Tie::Handle::CSV`: If you use the script for parsing
the exoplanets.org CSV file, you'll need this. 

* `Date-Picker`: If you want to have a nice pop-up calendar widget for selecting dates
in the interface for specifying the date range to be considered, you
can download and install the `Date-Picker` widget from
http://www.frequency-decoder.com/2009/09/09/unobtrusive-date-picker-widget-v5 

The actual download link is toward the bottom of the page:
http://www.frequency-decoder.com/demo/date-picker-v5/date-picker-v5.zip 

There is a call to this in the supplied default input form, assuming
it is installed in a subdirectory called `src` below the directory
where the form is installed.  To use, just unpack the zip file into
that `src` subdirectory, and make sure everything is readable by users
of your webserver:
`chmod -R o+rx src/`

For my own installation, I also edited the file
`src/date-picker-v5/js/lang/en.js` to make Sunday be displayed as the
first day of the week: `firstDayOfWeek:6`  It was set to O (Monday) by
default. 

To use a different localization, change the call in the header of the
input form to load a different language file from that subdirectory. 

If you run the code for creating finding charts, you'll need the tools
`convert` and `identify` from `ImageMagick` to be installed and in your
path. 


## Setup:

For the input form, there shouldn't be much setup needed - just put it
in the same directory as the other files.  If you change the name of
the code that calculates the transits, you'll need to change it here,
too, as the target of the form.   If you want to change the appearance
of the input form, or add observatories, you can edit this file.  Note
that it is not just an HTML file, but rather an mixture of Perl code
and HTML; though most of the form is hard-coded and is easily edited
here, the exact form is generated on the fly by execution of the Perl
code.  This allows, for example, filling in the user's default
selections for observatory location, transit elevation, etc., by
reading the stored cookies and using them to set the form values. 

For the transit-calculating code, you'll find a section near the top
of the file that gives instructions for customizing it for your
setup.  You need to change a few variables there to point to your
target file and to give your contact info for error messages.  You
also may need to edit a few subroutines at the end of the file to
specify where your finding charts (if any) are, and how to format
links to web pages giving more information about your targets.  (Note:
the default output template includes links to finding charts on
SkyMap.org, and to target info at Simbad and 2MASS - if that's enough
for your purposes, you can set both of these functions to return
`undef`.   Most importantly, you'll need to look at the routine that
parses a line of input from the datafile into separate fields that
gives target information (coords, ephemeris, etc.).  You'll need
either to make sure that your input file conforms to that expected
format, or to change the format there to match your file.  

Regarding target format files, I've also supplied two auxiliary
scripts that give examples of how to access target info from other
locations on the web and convert them to the format expected by this
script.  One can access a target list that is stored in a Google Docs
spreadsheet, using the column headings to identify the fields.  The
second parses the CSV file supplied by exoplanets.org into this target
format.  (To see an implementation of the script that uses the latter
target list, go to http://astro.swarthmore.edu/transits.cgi .)  If you
wanted to avoid storing a local target list altogether, and only use
an on-line spreadsheet, it wouldn't be too hard to combine the code
that fetches and parses the Google spreadsheet with the code in the
main routine - you'd just need to replace the file open / file read
calls in the main routine with a call to the separate
spreadsheet-reading code.  (If anyone does this in a way that makes it
easy to choose either mode, please send me a patch!) 

Though the main focus of the code is periodic events like transits or
eclipses, it can also handle non-periodic events.  For these "any
time" targets, the code just calculates whether or not they are above
some minimum elevation at some point during the night.  To designate a
target as non-periodic, give it a value of "2" in the "photometry
requested" field.  A value of "1" denotes a periodic target, and a
value of "3" is both "1" and "2", i.e. a target for which the transit
ephemeris should be used to report transits, but for which overall
visibility should be calculated and reported as well, e.g. for
out-of-transit monitoring. 

The appearance of the output (the table of upcoming transits) is
largely governed by a template file, `target_table.tmpl`, so this is the
place to customize the output if you don't like the defaults.  See the
documentation for `HTML::Template` for more details, but briefly, this
file specifies HTML code with special tags that are replaced by the
values of Perl variables at run time.  There are loops in the template
file that are executed at run time over all visible targets, i.e. the
code in the template is for one given row, but it is repeated as many
times as necessary, with the values filled in for a particular target.
There is an `HTML::Template` tutorial at
http://www.perlmonks.org/?node_id=65642 .


## Utility scripts and files included:

`get_finding_charts.pl`: this standalone script is used to produce the
annotated finding charts linked from the output transit list.  It can
take as input the same format of target file that the main script
uses, so you can generate finding charts all in one batch once you've
assembled your target list.  By default, it also skips over any
targets in a file for which a finding chart already exists, so you can
run it periodically on your target file (e.g. from a cron job) to have
it create new finding charts as new targets are added.  Make the file
executable (chmod +x get_finding_charts.pl) and run it with the --help
switch to see the usage details and options. 

`finding_charts.cgi` and `create_finding_chart.cgi`: these provide a
standalone web interface to the script mentioned in the previous
entry, for creating finding charts.  See
http://astro.swarthmore.edu/finding_charts.cgi for an example.  If you
want to avoid generating and storing local copies of finding charts
for your targets, you could replace the links in the default HTML
template to links that call `create_finding_chart.cgi` with appropriate
parameters, to generate them on-the-fly as needed (though this will be
slower than having a chart already created and stored). 

`plot_airmass.cgi` and `airmass.cgi`: The script `plot_airmass.cgi` produces 
the airmass plots linked from the web interface for the transit
listings, but it can be used in standalone mode as well via the
`airmass.cgi` script, which provides an input form to specify
coordinates or an object name.

`parse_google_spreadsheet.pl`:  This script can fetch a target list that
is stored in a Google spreadsheet, and convert it to the format
expected by the transit-plotting script.  This provides a convenient
way to have a target list that is editable by widely-dispersed
collaborators, but also to have a locally-stored target list on the
webserver that is quickly accessible by the scripts.  You can run this
script periodically from cron to keep the local target file up to
date. 

`example_target_spreadsheet.csv`: Example target spreadsheet in CSV
(comma-separated value) format.  This shows the layout of the target
spreadsheet that is expected by default by the previous
script. There's no reason you have to keep this format, but it can
give you a quick start; if you import this doc into your Google
account to create a Google docs (now Google Drive) spreadsheet, you'll
have the columns easily set up and ready to go.

`parse_exoplanets_csv.pl`: Perl script to parse the CSV file of known
transiting planets from exoplanets.org into the format expected by the
transit-plotting code.  URL for the CSV file is 
http://exoplanets.org/csv/exoplanets.csv

`airmass.ico`: small icon file displayed with the airmass plots.


## Copying: 

This code is free software, and it is released under the terms of the
GNU General Public License.  See the file COPYING.txt for more
details. 

## Citing: 

If you find this code useful for your work, please consider citing the
Astronomy Source Code Library entry, https://ui.adsabs.harvard.edu/abs/2013ascl.soft06007J .

## Acknowledgments:

Many thanks to the authors of various packages that made this work
possible, especially Tim Jenness for Astro::Coords, Astro::Telescope,
and Astro::PAL, and the various contributors to the DateTime and
HTML::Template packages. 

Thanks to Jason Wright and his team for the exoplanets.org database,
and to STScI for providing access to the Digitized Sky Survey. 


## Feedback:

If you use this code and find it useful, or if you have any bug fixes
or suggestions for improvement, I'd appreciate it if you would let me
know.  I developed it for my own and my collaborators' use, but it
would make me happy to know that others are finding it useful, too.
Please send me an e-mail at ejensen1@swarthmore.edu. 

If you have any questions about getting this set up and working on
your system, please let me know, and I'll do my best to help (though
my response time may vary depending on the time of year, and will
definitely be slower during September- mid-December and mid-January -
May when I'm teaching). 

Enjoy!

Eric Jensen



