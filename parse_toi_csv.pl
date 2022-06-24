#!/usr/bin/perl -w

use strict;
use warnings;

use Text::CSV qw(csv); 

# Fields we want for output: 
my @keys = ("name","RA","Dec","TOI","vmag","epoch","epoch_uncertainty", 
	    "period","period_uncertainty",
	    "duration","comments","depth","disposition","priority");

# Output will be an array of array references; start with the header: 
my @output_lines = (\@keys);


# Get the array of hash references from the input CSV stream: 
my $csv_lines = csv(in => *STDIN, 
		    allow_whitespace => '1',	   
		    headers =>"auto",
		    encoding => "UTF-8",
    ); 

foreach my $a (@$csv_lines) { 
    # Need to rename some of the fields within the hash.  This
    # standardization of header field names lets the main plotting
    # code handle different input files smoothly:

    $a->{duration} = $a->{"Duration (hours)"};
    $a->{period} = $a->{"Period (days)"};
    $a->{period_uncertainty} = $a->{"Period (days) err"};
    $a->{epoch} = $a->{"Epoch (BJD)"};
    $a->{epoch_uncertainty} = $a->{"Epoch (BJD) uncertainty"};

    # Need to have some key fields in order to be viable: 
    if ((not defined $a->{period}) or 
	($a->{period} == 0) or 
	(not defined $a->{epoch}) or 
	(not defined $a->{duration}))
    {
	next;
    }


    $a->{comments} = $a->{"Comments"};
    $a->{comments} .= " (updated " . 
	$a->{"Date Modified"} . ")";
    # Remove the HH:MM:SS, just keep the date: 
    $a->{comments} =~ s/ ?\d\d:\d\d:\d\d//;

    # Make the name from both the TIC ID and trailing part of the TOI: 
    my $toi_suffix;
    if ( $a->{"TOI"} =~ m/^\d+(\.\d{1,2})$/) {
	$toi_suffix = $1;
    } else {
	$toi_suffix = '';
    }
    $a->{name} = sprintf("TIC %s%s", $a->{"TIC ID"}, $toi_suffix); 
    $a->{vmag} = sprintf("%0.1f", $a->{"TESS Mag"});
    # Convert depth from ppm to ppt:
    $a->{depth} = sprintf("%0.2f", $a->{"Depth (ppm)"}/1000.); 
    $a->{disposition} = $a->{"TFOPWG Disposition"};
    $a->{priority} = $a->{"Master"};
    
    # Build up the line to output: 
    my @line=();
    foreach my $key (@keys) { 
	push @line, $a->{$key};
    }
    # Then store a reference to that line: 
    push(@output_lines, \@line);

}
    
# Finally, write this out to a CSV file: 
my $status = Text::CSV::csv(in => \@output_lines, 
			    out => *STDOUT,
			    encoding => "UTF-8",
); 
