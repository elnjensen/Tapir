#!/usr/bin/perl

# Perl code to access a Google doc with target info and
# reformat the data into an easy-to-parse format for use by the
# transit finder code. 

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


use strict;
use warnings;

use Net::Google::Spreadsheets;

# Two important things to note about setting up your Google
# spreadsheet, both of which are set by the Google API (not coding
# choices here):  (1) The first row of the spreadsheet is a header
# row, and the entries in this row set the variable names returned for
# each column; see the example spreadsheet included
# (example_target_spreadsheet.csv); (2) a blank row in the spreadsheet
# is taken to be the end of the data stream, i.e. if you have a blank
# row in your sheet, no subsequent rows of data will be returned. 

# Login credentials need to be passed in; be careful about who has
# read access to this file, and/or re-write to ask for these
# credentials at run time.  Note that you do not have to store this in
# a web-accessible directory on your server - you could, e.g., have
# this script run periodically from cron and redirect its output into
# a text file on your webserver.  This interface requires that the
# plain-text username and password be sent to the server.  If you use
# this, you might want to create a separate Google account that you
# use only for this purpose.

my $service = Net::Google::Spreadsheets->new(
    username => 'my_google_username@gmail.com',
    password => 'my_google_password',
					     );
	

# We have to find the right spreadsheet (which can contain multiple
# worksheets), and then within that spreadsheet, get the proper
# worksheet.   See the Net::Google::Spreadsheets docs for methods of
# querying for your whole list of spreadsheets and seeing their titles
# and/or keys. 


my $spreadsheet_title = 'Target list';
my $worksheet_title = 'Current targets';

my $spreadsheet = $service->spreadsheet({
    title => $spreadsheet_title,
});

my $worksheet = $spreadsheet->worksheet({
    title => $worksheet_title,
});

# Get the rows from the worksheet:
my @rows = $worksheet->rows;

my $row;

# String that we will use to divide fields; we want something other
# than a plain comma, since we want to allow commas as a valid part of
# the Comments field.
my $delimiter = ",.";

# Now cycle over the rows, printing out the relevant fields.  When the
# Google spreadsheet is accessed via this interface, the keys for each
# field are taken from the headers for each column, but with spaces
# and parentheses stripped away, and converted to lowercase.  For
# example, a column headed "Duration (hrs)" becomes "durationhrs".  

foreach $row (@rows) {
    my $rowref = $row->content;

    my $phot_requested = trim($rowref->{photometryrequested});
    my $format = "%s $delimiter " x 10 . "%s\n";
    if ($phot_requested != 0) {
	my $comments = trim($rowref->{comments});
	# Strip any newlines from the comments:
	$comments =~ s/\n//g;
	# Convert embedded spaces into colons in the RA and Dec:
	my $ra_string = trim($rowref->{ra});
	$ra_string =~ s/(\d)\s+(\d)/$1:$2/g;		
	my $dec_string = trim($rowref->{dec});
	$dec_string =~ s/(\d)\s+(\d)/$1:$2/g;		

	printf($format, trim($rowref->{target}), $ra_string, $dec_string,
	       trim($rowref->{vmag}), trim($rowref->{tc}), 
	       trim($rowref->{p}), trim($rowref->{durationhrs}), 
	       $comments, trim($rowref->{priority}),
	       trim($rowref->{depthmmag}), $phot_requested);
    }
}


sub trim {

# Trim leading and trailing whitespace from a string.  We use \A and
# \Z to anchor the beginning and end of the string, since they span
# across newlines.

    my $string = shift @_;
    $string =~ s/\A\s*//;    
    $string =~ s/\s*\Z//;

    return $string; 

}
