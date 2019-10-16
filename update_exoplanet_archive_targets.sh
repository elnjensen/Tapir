#!/bin/bash

# Script to download the NASA Exoplanet Archive database for processing to 
# make a target list for the public transit finder. 
# Eric Jensen, 2019-08-26

# Filename base for target file: 
TARG_BASE=exoplanet_archive_transits_full

NEW_FILE=${TARG_BASE}_new.txt
TARG_FILE=${TARG_BASE}.txt
MAG_FILE=${TARG_BASE}_mags.txt
MAG_FILE_TEMP=${TARG_BASE}_mags_temp.txt

OUTPUT_FILE=transit_targets.csv

# Working directory: 
DIR=/home/httpd/html/transit_testing/

cd $DIR

# Get file, and sort it by all except the first line.  Save as a temporary file: 
curl --silent --fail 'https://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?table=exomultpars&select=mpl_name,mpl_orbper,mpl_orbpererr1,mpl_orbpererr2,mpl_orbsmax,mpl_orbincl,ra_str,dec_str,mst_rad,mpl_rads,mpl_trandep,mpl_trandur,mpl_trandurerr1,mpl_trandurerr2,mpl_tranmid,mpl_tranmiderr1,mpl_tranmiderr2,mpl_imppar,mpl_ratdor,mpl_ratror,mpl_tsystemref&where=(mpl_tranflag=1)' | awk 'NR<2{ print; next }{ print | "sort" }' > $NEW_FILE


# If non-zero size and different from the old file, replace the old file: 
if [ -s $NEW_FILE ] && ! cmp --silent $TARG_FILE $NEW_FILE
then
    # Files are different; replace: 
    mv $NEW_FILE $TARG_FILE
    chmod o+r $TARG_FILE 
    # Also download the supplemental information from the other table: 
    curl --silent --fail 'https://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?table=exoplanets&select=pl_name,st_optmag,st_optband,gaia_gmag,pl_trandur,pl_trandep,pl_rads,st_rad,pl_ratror&where=(pl_tranflag=1)' | awk 'NR<2{ print; next }{ print | "sort" }' > $MAG_FILE_TEMP
    if [ -s $MAG_FILE_TEMP ]
    then
	mv $MAG_FILE_TEMP $MAG_FILE
	chmod o+r $MAG_FILE

	# Make sure both contain the same targets: 
	diff <(perl -na -F"," -e 'print "$F[0]\n" if ($. > 1)' $TARG_FILE |uniq) <(perl -na -F"," -e 'print "$F[0]\n" if ($. > 1)' $MAG_FILE |uniq)

	# Have both files, do the processing: 
	./parse_exoplanets_csv_nasa.pl $TARG_FILE > $OUTPUT_FILE
	chmod o+r  $OUTPUT_FILE
    else
	/bin/rm -f $MAG_FILE_TEMP
	echo "Successfully downloaded target file, but failed to get magnitudes file."
	exit
    fi 
else
    # Get rid of the redundant new file: 
    /bin/rm -f $NEW_FILE
fi
