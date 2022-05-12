#!/bin/bash

# Script to download the NASA Exoplanet Archive database for processing to 
# make a target list for the public transit finder. 
# Eric Jensen, 2019-08-26
# Revised for new Exoplanet Archive tables, 05-06-2022

# Filename base for target file: 
TARG_BASE=exoplanet_archive_transits_full

NEW_FILE=${TARG_BASE}_new.txt
TARG_FILE=${TARG_BASE}.txt
COMPOSITE_FILE=${TARG_BASE}_composite.txt
COMPOSITE_FILE_TEMP=${TARG_BASE}_composite_temp.txt

OUTPUT_FILE=transit_targets.csv

# Working directory: 
DIR=/home/httpd/html/transits/

cd $DIR

# Get file, and sort it by all except the first line.  Save as a temporary file: 
curl --silent --fail 'https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+pl_name,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_orbsmax,pl_orbincl,rastr,decstr,ra,dec,st_rad,pl_radj,pl_trandep,pl_trandur,pl_trandurerr1,pl_trandurerr2,pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_imppar,pl_ratdor,pl_ratror,sy_vmag,sy_gaiamag+from+ps+where+tran_flag=1&format=csv' | awk 'NR<2{ print; next }{ print | "sort" }' > $NEW_FILE


# If non-zero size and different from the old file, replace the old file: 
if [ -s $NEW_FILE ] && (! [ -s $OUTPUT_FILE ] || ! cmp --silent $TARG_FILE $NEW_FILE)
then
    # Files are different, or we don't have a target file at all. 
    # Echo differences; comment out next line if you want silent output:
    diff $TARG_FILE $NEW_FILE
    # Replace the old file: 
    mv $NEW_FILE $TARG_FILE
    chmod o+r $TARG_FILE 

    curl --silent --fail 'https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+pl_name,pl_orbper,pl_orbpererr1,pl_orbpererr2,pl_orbsmax,pl_orbincl,rastr,decstr,ra,dec,st_rad,pl_radj,pl_trandep,pl_trandur,pl_trandurerr1,pl_trandurerr2,pl_tranmid,pl_tranmiderr1,pl_tranmiderr2,pl_imppar,pl_ratdor,pl_ratror,sy_vmag,sy_gaiamag+from+pscomppars+where+tran_flag=1&format=csv' | awk 'NR<2{ print; next }{ print | "sort" }' > $COMPOSITE_FILE_TEMP
    if [ -s $COMPOSITE_FILE_TEMP ]
    then
	mv $COMPOSITE_FILE_TEMP $COMPOSITE_FILE
	chmod o+r $COMPOSITE_FILE

	# Make sure both contain the same targets: 
	diff <(perl -na -F"," -e 'print "$F[0]\n" if ($. > 1)' $TARG_FILE |uniq) <(perl -na -F"," -e 'print "$F[0]\n" if ($. > 1)' $COMPOSITE_FILE |uniq)


	# Have both files, do the processing: 
	./parse_exoplanets_csv_nasa.pl $TARG_FILE > $OUTPUT_FILE
	chmod o+r  $OUTPUT_FILE
    else
	/bin/rm -f $COMPOSITE_FILE_TEMP
	echo "Successfully downloaded target file, but failed to get composite parameters file."
	exit
    fi 
else
    # Get rid of the redundant new file: 
    /bin/rm -f $NEW_FILE
fi
