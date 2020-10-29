#!/bin/sh

# Simple script to fix permissions on files to make 
# them web-accessible after a checkout or merge:

# Scripts need to be readable and executable:
chmod o+rx acp_plan.cgi transits.cgi get_finding_charts.pl plot_airmass.cgi print_transits.cgi 

# Templates, modules, javascript, and stylesheets just need to be readable: 
chmod o+r airmass_stylesheet.css csv_text.tmpl jquery.dataTables.css Observatories.pm page_style.css target_table.tmpl aladin.html aladin-tess.js aladin_finder.html vizier_mirrors.js 

# Directories need to be readable and executable, including the current dir:
chmod o+rx finding_charts src .


