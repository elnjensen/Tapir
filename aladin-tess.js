/* Javascript functions to work with the Aladin Lite finder interface
   for the TESS transit finder, specifically the code in aladin.html.
   Some of these are standalone utility functions, but a number of
   them refer specifically to global variables or HTML elements in
   that file.  Placing them in a separate file here allows browsers to
   cache this part of the code, reducing bandwidth needed.

  Copyright 2012-2020 Eric Jensen, ejensen1@swarthmore.edu.
 
  This file is part of the Tapir package, a set of (primarily)
  web-based tools for planning astronomical observations.  For more
  information, see the README.txt file or
  http://astro.swarthmore.edu/~jensen/tapir.html .
 
  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.
 
  This program is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.
 
  You should have received a copy of the GNU General Public License
  along with this program, in the file COPYING.txt.  If not, see
  <http://www.gnu.org/licenses/>.

*/ 


function sleep(ms) {
    /* Simple sleep function - only works within async functions. See
       https://stackoverflow.com/questions/951021/what-is-the-javascript-version-of-sleep 
    */
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Asynchronously find the nearest Vizier mirror
// based on the user's IP address:
async function setVizier(ip='') {
    vizURL = await nearestVizierURL(ip);
    if (vizURL != '') {
	vizierServer = vizURL;
	console.log('Using Vizier server: ', vizURL);
	// Save it for next time: 
	localStorage.setItem('VizierURL', vizURL)
    }
}

async function getToiInfo(target) {
    // Query our local target list of TOIs to get the coordinates,
    // magnitude and transit depth.  Returns a JSON object.  If status
    // = 1, other fields should be populated. If status = 0, the
    // target was not found or the name could not be interpreted.

    let toidata;
    const result = await $.get('tess_transit_depth.cgi?name=' + target, 
			 success=function(data) {
			     toidata = data;
			 }
			 ).fail(function(jqXHR, textStatus, errorThrown) {
				 alert("Failed to call tess_transit_depth.");
				 console.log("Status, error: ", textStatus, errorThrown);
				 toidata = { "status": 0 };
			     });
    if (toidata.status) {
	console.log("Resolved target " + target + " in getToiInfo.");
    } else {
	console.log("Did not find target " + target + " in getToiInfo.");
    }
    console.log(toidata);
    return toidata;
}

async function resolveCoords(target) {
    // Try to resolve coordinates of the given target.  First we try
    // locally with our TOI file, and if that fails, we try Sesame.
    // As a side effect, if we succeed in resolving it locally, we
    // also set target magnitude and depth if they are not already
    // set.

    info = await getToiInfo(target);
    if (info.status) {
	// Got the values, set vars:
	// Convert RA from hours to degrees:
	ra_center = sexagesimalToDecimal(info.RA)*15.;
	dec_center = sexagesimalToDecimal(info.Dec);
	ra_string = ra_center;

	if (! depth) {
	    depth = parseFloat(info.depth);
	    depthDeltaMag = -2.5*Math.log10((depth)/1000.);
	}
	if (! Tmag) {
	    Tmag = parseFloat(info.Tmag);
	}
	if (! tic_number) {
	    tic_number = (info.name).replace(/^TIC */, '');
	    // Then possibly trailing .01, .02 etc., which ExoFOP doesn't like: 
	    tic_number = tic_number.split('.')[0];
	}
	have_center_coords=true;
    } else {
	// Didn't succeed there, try Sesame instead.  If the TIC name
	// passed had a trailing .01, .02, etc., remove it before
	// passing to Sesame since that won't be resolved in the TIC. 
	let matchname = target.replace(/^(TIC\s*\d+)\.\d+$/,'$1');
	Sesame.getTargetRADec(matchname,
			      function(d) {
				  ra_center=d.ra; 
				  dec_center=d.dec; 
				  ra_string = d.ra;
				  have_center_coords=true; 
				  console.log('Resolved '+matchname+': '+d.ra+', '+d.dec)
				      }, 
			      function(){alert('Could not resolve '+matchname+' into coordinates.')}
			      );
    }
}

async function findSurveyCoverage() {
    // Query the MOC server to determine which surveys cover this field,
    // so we know which options to offer in the menu.  This is an
    // asynchronous query, so other page loading continues while this
    // query executes.

    var moc_url = 'https://alasky.unistra.fr/MocServer/query?expr=' + 
	'(ID%3D*SDSS9*color||ID%3D*PanSTARRS*color*)&get=id&fmt=ascii&RA='+ 
	ra_center+'&DEC='+dec_center+'&SR=0.2&intersect=enclosed';

    $.ajax({
	    url: moc_url,
		method: 'GET',
		dataType: 'text',
		start_time: new Date().getTime(),
		success: function(surveys) {	    
		timeMS = new Date().getTime() - this.start_time;
		console.log('Request to ' + moc_url + ' took ' + 
			    timeMS + ' ms.');
		console.log('Request output: '+surveys);
		const disabledColor = '#AAAAAA'; // gray
		if (surveys.includes('PanSTARRS')) {
		    console.log('Pan-STARRS covers this field.');
		} else {
		    document.getElementById('panstarrs-button').checked=false;
		    document.getElementById('panstarrs-button').disabled='disabled';
		    document.getElementById('panstarrs-label').style.color=disabledColor;
		    console.log('No Pan-STARRS coverage.');
		}
		if (surveys.includes('SDSS')) {
		    console.log('SDSS covers this field.');
		} else {
		    document.getElementById('sdss-button').disabled='disabled';
		    document.getElementById('sdss-label').style.color=disabledColor;
		    console.log('No SDSS coverage.');
		}
	    },
		error: function(err) { 
		console.log('Could not complete request for MOC url '+moc_url);
	    }
	});
}

function setupCentralStar() {
    // Mark the central star if one was passed in.  We may update
    // coords later if they get shifted based on proper motion. 
    centralStar = A.catalog({name: 'Central star', sourceSize: 18, color: colors.centralStar});
    if (starname != '') {
	aladin.addCatalog(centralStar);
	// Set the popup text with some useful information and links:
	var popupCode =  '<em>Tmag:</em> ' + Tmag + '<br/><em>Transit depth:</em> ' +
	    depth  + ' ppt<br/><br/>';
	// ExoFOP URL:
	popupCode += '<a target="_blank" ' +
	    'href="https://exofop.ipac.caltech.edu/tess/target.php?id=' + 
	    tic_number + '">ExoFOP</a>';
	// Simbad URL:
	popupCode += ' <a target="_blank" href="http://simbad.u-strasbg.fr/simbad/sim-coo?' +
	    'output.format=HTML&Radius=15&Radius.unit=arcsec&Coord=' + 
	    field_center + '">Simbad</a>';
	
	centralStar.addSources([A.marker(ra_center, dec_center, 
					 {popupTitle: starname, 
						 popupDesc: popupCode}
					 )]);
    }
}



/* Query the TIC catalog first; we will use this to update the field center 
   coordinates to account for proper motion, so that all distances can 
   be calculated relative to that center at the current epoch. 
*/

function currentEpoch() {
    /* Return the current epoch in units of years, i.e. as a year with
     * a fractional part.  This allows calculation of number of years
     * since a given epoch for purposes of applying proper motion
     * corrections.
     */
    const currentYear = new Date().getUTCFullYear();
    const jan1 = new Date(Date.UTC(currentYear, 0));
    // Above times are in ms, so do conversion. 
    return currentYear + (Date.now() - jan1)*ms2year;
}


async function shiftCatalogTIC(sources) {
    /* Callback function to process the TIC catalog returned by a
       Vizier query.  Take a catalog of sources as input, and shift
       positions to the current epoch based on proper motions. Also
       updates the field center to the new coordinates (based on known
       TIC number of the central star, and recalculates the separation
       of each source from that center.  Sets a global boolean
       TIC_is_done to allow other functions to know when this update
       has completed.
    */

    // If there is no starname defined, then the only input was the
    // coordinates.  In that case, use the TIC source closest to the
    // center as the target star.  Also see if we can find it in the
    // local target file to get its depth and TOI number.
    if ((starname == '') && (sources.length > 0)) {
	console.log("No central star name passed in.");
	tic_number = sources[0].data.TIC;
	starname = 'TIC ' + tic_number;
	console.log("Setting from nearest TIC source: " + starname);
	Tmag = parseFloat(sources[0].data.Tmag);
	// Try to get further info from local target file: 
	info = await getToiInfo(starname);
	if (info.status && (! depth)) {
	    depth = parseFloat(info.depth);
	    depthDeltaMag = -2.5*Math.log10((depth)/1000.);
	}
	setupCentralStar();
    } else if ((! depth) || (! Tmag)) {
	// Could have a central star name but no depth and/or mag; see
	// if we can resolve that from local target file:
	info = await getToiInfo(starname);
	if (info.status) {
	    if (! depth) {
		depth = parseFloat(info.depth);
		depthDeltaMag = -2.5*Math.log10((depth)/1000.);
		console.log("No depth provided but found " + depth + " from local TOI file.");
	    }
	    if (! Tmag) {
		Tmag = parseFloat(info.Tmag);
	    }
	}
    }

    // If we still don't have a Tmag from the above, pull it from the
    // closest TIC source:
    if (! Tmag) {
	console.log("Setting Tmag from nearest TIC source: " + sources[0].data.TIC);
	Tmag = parseFloat(sources[0].data.Tmag);
    }

    const current_epoch = currentEpoch();
    // Will update this if/when we find the TIC entry for the central star: 
    var centralStarIndex = -1;
    for (i=0; i < sources.length; i++) {
	sources[i].data.i = i;
	// Get delta T mag: 
	T = parseFloat(sources[i].data.Tmag);
	if (isNaN(T) || Tmag == '') {
	    sources[i].data.DeltaT = '';
	} else {
	    sources[i].data.DeltaT = (T - Tmag).toPrecision(3);
	}
	if (sources[i].data.r_Pos.includes('gaia2')) {
	    epoch = 2015.5;
	} else if (sources[i].data.r_Pos.match(/tmm?gaia/)) {
	    // Matches either tmgaia or tmmgaia
	    epoch = 2015.0;
	} else if ((sources[i].data.r_Pos == '2mass') || 
		   (sources[i].data.r_Pos == '2MASSEXT')){
	    epoch = 1999.3;  // estimated from survey dates
	} else {
	    // We don't know epoch of coords: 
	    console.log('Source TIC ' + sources[i].data.TIC + 
			' has position source: ' 
			+ sources[i].data.r_Pos);
	    console.log('Epoch of coords is unknown, not applying proper motion.');
	    epoch = '';
	}
	// Use epoch of coords to get time span:
	span = current_epoch - epoch;
	pmRA = parseFloat(sources[i].data.pmRA);
	pmDE = parseFloat(sources[i].data.pmDE);
	RAorig = parseFloat(sources[i].data.RAOdeg);
	DEorig = parseFloat(sources[i].data.DEOdeg);
	if (isNaN(pmRA) || isNaN(RAorig) || epoch == '') {
	    sources[i].data.rashift = 0.;
	} else {
	    // pmRA has cos(dec) factored in, so account for
	    // that when shifting RA coordinate:
	    sources[i].ra = RAorig + pmRA*span*mas2deg/Math.cos(sources[i].dec * deg2rad);
	    sources[i].data.RaNow = sources[i].ra;
	    sources[i].data.rashift = (pmRA*span).toPrecision(3) + ' mas';
	};
	if (isNaN(pmDE) || isNaN(DEorig) || epoch == '') {
	    sources[i].data.decshift = 0.;
	} else {
	    sources[i].dec = DEorig + pmDE*span*mas2deg;
	    sources[i].data.DecNow = sources[i].dec;
	    sources[i].data.decshift = (pmDE*span).toPrecision(3) + ' mas';
	};
	// If this is the field-center star, update the center coords: 
	if (sources[i].data.TIC == tic_number) {
	    console.log("Found central star as source ", i);
	    centralStarIndex = i;
	    // Update the field center coordinates: 
	    ra_center = sources[i].ra;
	    dec_center = sources[i].dec;
	    center_coo = new Coo(ra_center, dec_center);
	    // If no T mag was passed in, get it from this catalog entry: 
	    if (Tmag == '') {
		Tmag = parseFloat(sources[i].data.Tmag);
		// Also update the popup for the central star symbol:
		let p = centralStar.sources[0].popupDesc;
		p = p.replace(/(<em>Tmag:<\/em> )(<br\/>)/, '$1' + Tmag + '$2');
		centralStar.sources[0].popupDesc = p;
	    }
	    // Make a note of the Gaia ID of this entry so we can
	    // exclude it from the list of blending stars later:
	    centralStar.gaia = sources[i].data.GAIA;
	    centralStar.Tmag = sources[i].data.Tmag;
	    // Most of the time this block won't run since i = 0;
	    if (i > 0) {
		alert("TIC entry matching entered name is not closest" + 
		      " to the center coords.  Please ask Karen or Eric" + 
		      " to check the coords for TIC " + 
		      sources[i].data.TIC + ".");
		// If it happens that the central star is not first in the list,
		// go back and update the previous entries: 
		for (j=0; j < i; j++) {
		    console.log("Updating _r for source ", j);
		    dist = center_coo.distance(new Coo(sources[j].ra,
						       sources[j].dec));	
		    // Convert distance from center to arcsec:
		    sources[j].data._r = (dist * 3600).toPrecision(3) + '"';
		}
	    }
	}
	// Update the distance from the center, using new coordinates: 
	dist = center_coo.distance(new Coo(sources[i].ra,
					   sources[i].dec));
	
	// Convert distance from center to arcsec:
	sources[i].data._r = (dist * 3600).toPrecision(3) + '"';

	// Save the deltaT and Tmag for the sources that have Gaia
	// IDs:
	if (sources[i].data.GAIA != '') {
	    const g = sources[i].data.GAIA;
	    deltaT_vals[g] = sources[i].data.DeltaT;
	    Tmag_vals[g] = sources[i].data.Tmag;
	    TIC_vals[g] = sources[i].data.TIC;
	}
    }
    TIC_is_done = true;
    // Update the label with number of sources: 
    document.getElementById('tic-N-sources').innerHTML = sources.length;
    // Update the central star coordinates and popup:
    if (centralStar.sources.length > 0) {
	centralStar.sources[0].ra = ra_center;
	centralStar.sources[0].dec = dec_center;
	if (centralStarIndex != -1) {
	    //  Add TIC info to popup:
	    const t = sources[centralStarIndex].data;
	    var m = '<br/><br/><i>TIC catalog entry:</i>'
		m += '<br/><div class="aladin-marker-measurement">';
	    m += '<table>';
	    for (var key in t) {
		m += '<tr><td>' + key + '</td><td>' + t[key] + '</td></tr>';
	    }
	    m += '</table>';
	    m += '</div>';
	    centralStar.sources[0].popupDesc += m;
	}
	centralStar.reportChange();
    }
}


function vizierURL(vizCatId, center, radiusDegrees, search_options) {
    var url = vizierServer + '/viz-bin/votable?-source=' + vizCatId + '&-c=' + 
	encodeURIComponent(center) + '&-out.max=100000&-c.rd=' + radiusDegrees;
    if (! search_options == '') {
	url = url + search_options;
    }
    return url;
};


function setupTIC() {
    var extra_options = "&-sort=_r&-out.all";
    var radius_deg = 5/60.;

    TIC = A.catalogFromURL(vizierURL('IV/38/tic', field_center, radius_deg, extra_options), 
			   {onClick: TICpopup,
			    name: 'TIC',
			    color: colors.tic,
			    shape: 'cross'},
			   shiftCatalogTIC, 
			   false);
    aladin.addCatalog(TIC);
    // Default to not showing initially, unless boolean passed as an argument: 
    TIC.isShowing = showTIC;
    let checkbox = document.getElementById('tic');
    checkbox.checked = showTIC;
    toggleElements(checkbox);
}

function TICpopup(s) {
    /* Function for showing a customized popup for TIC sources; much
       is copied out of the Aladin code for showPopup, but this allows
       us to construct our own content for the popup.
    */

    var view = s.catalog.view;
    var d = s.data;
    view.popup.setTitle('<b>TIC ' + d.TIC + '</b><br/><br/>');
    var m = '<div class="equation">';
    m += '<div>T = ' + d.Tmag + '</div>';
    m += '<div>&Delta;T = ' + d.DeltaT + '</div>';
    m += '<div>r = ' + d._r + '</div>';
    m += '</div>'
    m += '<br/><div class="aladin-marker-measurement">';
    m += '<table>';
    for (var key in s.data) {
	m += '<tr><td>' + key + '</td><td>' + s.data[key] + '</td></tr>';
    }
    m += '</table>';
    m += '</div>';
    view.popup.setText(m);
    view.popup.setSource(s);
    view.popup.show();
}

// Mark - done with section for querying the TIC, though at this 
// point in the code execution the query may not have completed yet. 

/* Now query the Gaia catalog.  We handle this is in much the same
   way, but it's a little simpler since we know the epoch of all
   sources is the same.  As we're shifting stars, we also keep track
   of a subset that have the right distance and delta magnitude to
   possibly contaminate the TESS detection.x */


/* Since new Gaia data releases will keep coming out, make sure
   to define some relevant variables together here, so we'll 
   notice to change epoch if the catalog changes. 
*/ 

// EDR3 is: I/350/gaiaedr3  ; DR2 is: I/345/gaia2
gaiaVizierCatalog = 'I/350/gaiaedr3';
gaiaEpoch = 2016.0  // DR2 is 2015.5

//  ---------- Gaia section: -------------
function setupGaia() {

    let extra_options = "&-sort=_r&-out.all";
    let radius_deg = 5/60.;

    // Start with defining basic properties for this catalog, but no actual sources 
    // until we do the main Gaia query and add a subset from there. 
    gaiaBlends = A.catalog({name: 'Possible Gaia blends', 
			    sourceSize: 12,
			    shape: 'square',
			    color: colors.gaiaBlends,
			    onClick: gaiaPopup});

    gaiaAll = A.catalogFromURL(vizierURL(gaiaVizierCatalog, field_center, 
					 radius_deg, extra_options), 
			       {onClick: gaiaPopup,
				name: 'All Gaia stars',
				sourceSize: 14,
				color: colors.gaiaAll,
				shape: 'circle'},
			       shiftCatalogGaia,
			       false);

    aladin.addCatalog(gaiaAll);
    gaiaAll.isShowing = false;
    // Add this last so it's on top: 
    aladin.addCatalog(gaiaBlends);
    gaiaBlends.isShowing = false;

    // Define this boundary so it's global, but don't add content until 
    // we have time to redefine the field center: 
    Gaia_boundary = A.graphicOverlay(gaia_options);
    aladin.addOverlay(Gaia_boundary);
    Gaia_boundary.isShowing = false;

    // Overlaid layers are by default not shown initially, 
    // unless the boolean is set in the URL params: 
    var checkbox = document.getElementById('gaiaAll');
    checkbox.checked = showGaia;
    toggleElements(checkbox);
    if (depth) {
	var checkbox = document.getElementById('gaia');
	checkbox.checked = showGaiaBlends;
	toggleElements(checkbox);
    }
}

async function shiftCatalogGaia(sources) {
    /* Callback function to process the Gaia catalog returned by a
       Vizier query.  Take a catalog of sources as input, and shift
       positions to the current epoch based on proper motions. This 
       has a decent amount of code overlap with the shiftCatalogTIC, 
       but it's a little simpler because the Gaia catalog is more 
       homogeneous. 
    */

    // Since the TIC callback resets the field center, ideally we 
    // want it to be done before starting here.  But don't keep
    // waiting indefinitely - after 10 seconds give up and move on. 
    var waited = 0;
    while ((! TIC_is_done) && (waited < 10000)) {
	await sleep(100);
	waited += 100;  // milliseconds
    }

    const current_epoch = currentEpoch();
    var neighbors = [];
    var neighborDistances = [];
    let lastDistance = -1;
    var centralStarData = null;
    for (i=0; i < sources.length; i++) {
	sources[i].data.i = i;
	// Use epoch of coords to get time span:
	span = current_epoch - gaiaEpoch;
	pmRA = parseFloat(sources[i].data.pmRA);
	pmDE = parseFloat(sources[i].data.pmDE);
	RAorig = parseFloat(sources[i].data.RA_ICRS);
	DEorig = parseFloat(sources[i].data.DE_ICRS);
	if (isNaN(pmRA) || isNaN(RAorig)) {
	    sources[i].data.rashift = 0.;
	} else {
	    // pmRA has cos(dec) factored in, so account for
	    // that when shifting RA coordinate:
	    sources[i].ra = RAorig + pmRA*span*mas2deg/Math.cos(sources[i].dec * deg2rad);
	    sources[i].data.RaNow = sources[i].ra;
	    sources[i].data.rashift = (pmRA*span).toPrecision(3) + ' mas';
	};
	if (isNaN(pmDE) || isNaN(DEorig)) {
	    sources[i].data.decshift = 0.;
	} else {
	    sources[i].dec = DEorig + pmDE*span*mas2deg;
	    sources[i].data.DecNow = sources[i].dec;
	    sources[i].data.decshift = (pmDE*span).toPrecision(3) + ' mas';
	};
	// Update the distance from the center, using new coordinates: 
	dist = center_coo.distance(new Coo(sources[i].ra,
					   sources[i].dec));
	
	// Convert distance from center to arcsec:
	sources[i].data._r = (dist * 3600).toPrecision(3) + '"';
	// And save the raw value for possible later use: 
	sources[i].data.r_deg = dist.toPrecision(6);

	// Check to see if this source is a potential blend that could
	// be responsible for the transit, and add to another catalog
	// if so.

	var gmag = parseFloat(sources[i].data.Gmag);
	var rmag = parseFloat(sources[i].data.RPmag);
	var color = parseFloat(sources[i].data['BP-RP']);
	// If we don't have Gaia mags, or don't have a central 
	// Tmag to compare to, we can't check this. 
	if (Tmag == '' || (isNaN(gmag) && isNaN(rmag))) {
	    sources[i].data.shiftedMag = null;
	    continue;
	}

	var mag = null; // which mag we will actually use
	var magOffset = null;
	if (isNaN(gmag)) {
	    // Fall back on R mag, different offset:
	    mag = rmag;
	    magOffset = 1.0;
	} else {
	    if (isNaN(color)) {
		T_gaia = gmag - 0.43;
	    } else {
		// Calculate the approximate Gaia source T mag from the Gaia 
		// photometry, following Eq. 1 of the TIC paper (Stassun et al. 
		// 2019).
		T_gaia = gmag - 0.00522555*color**3 + 0.0891337*color**2 - 
		    0.633923*color + 0.0324473;
	    }
	    mag = T_gaia;
	    magOffset = 0.5;
	}
	// Save this mag for possible neighbor recalculation later: 
	sources[i].data.shiftedMag = (mag - magOffset).toFixed(3);
	// Also store which mag we actually used for comparison:
	sources[i].data.magUsed = mag.toFixed(3);
	if (sources[i].data.Source == centralStar.gaia) {
	    // Save this separately:
	    centralStarData = sources[i];
	} else if ((mag <= (Tmag + depthDeltaMag + magOffset)) && 
		   (dist <= gaiaRadius)) {
	    // We have a neighbor star - add it to the list, but 
	    // keep the list in order by angular distance from the 
	    // center.  Most of the time this just means pushing it
	    // onto the end of the list, but occasionally we'll need
	    // to search from the end of the list backward to find
	    // the right location to add it in. 
	    j = neighbors.length - 1; // last index of array
	    if (dist >= lastDistance) {
		// Farthest source yet, just add to the end. Since 
		// the initial value of lastDistance is negative, 
		// this will always run for the first source. 
		neighbors.push(sources[i]);
		lastDistance = dist;
		neighborDistances.push(dist);
	    } else {
		// Find the right place to insert; here we do not
		// update lastDistance, so that it stays as distance
		// at end of array. 
		while ((j >= 0) && (neighborDistances[j] > dist)) {
		    j--;
		}
		neighbors.splice(j + 1, 0, sources[i]);
		neighborDistances.splice(j + 1, 0, dist);
	    }
	} 
    }

    gaiaBlends.addSources(neighbors);
    // Now add the circle with the field for the Gaia blends:
    Gaia_boundary.add(A.circle(ra_center, dec_center, 
			       gaiaRadius, gaia_options));
    console.log("Done with Gaia catalog.");
    // Update the label with number of sources: 
    document.getElementById('gaia-N-sources').innerHTML = sources.length;
    if (depth) {
	document.getElementById('gaia-blends-N-sources').innerHTML = neighbors.length;
	document.getElementById('depth-input').value = parseFloat(depth);
    }
    // Create the link to make an AIJ apertures file of the blending stars:
    neighbors_plus = neighbors;
    if (centralStarData) {
	neighbors_plus.unshift(centralStarData);
    } else {
	console.log("Did not match central star via Gaia in making AIJ apertures, will try to match by T mag.");
    }
    blob = createAIJApertures(neighbors);
    blobURL = URL.createObjectURL(blob);
    let aijLink = document.getElementById('aij-link');
    aijLink.href = blobURL;
    aijLink.innerHTML = "AIJ apertures";
    aijLink.download = blob.name;
}

function changeGaiaNeighbors(depth) {
    /* Recalculate membership for the gaiaBlends catalog, based on the
       input depth in ppt.  Similar to the code in the previous
       function for determining Gaia neighbors, but much shorter since
       much of the work has already been done above, saving key
       fields.
    */

    const magThreshold = Tmag - 2.5*Math.log10(depth/1000);
    var neighbors = [];
    let s = gaiaAll.sources;
    for (i = 0; i < s.length; i++) {
	if ((s[i].data.shiftedMag) && 
	    (s[i].data.Source != centralStar.gaia) &&
	    (s[i].data.shiftedMag <= magThreshold) && 
	    (s[i].data.r_deg <= gaiaRadius)) {
	    neighbors.push(s[i]);
	} 
    }
    gaiaBlends.removeAll();
    gaiaBlends.addSources(neighbors);
    document.getElementById('gaia-blends-N-sources').innerHTML = neighbors.length;
}    

function toSexagesimal(num, prec, plus) {
    /* Convert degrees to sexagesimal.  Adapted from Aladin 
       code; use ":" instead of space, and keep leading zero
       for all fields. 'prec' (precision) is number of decimal 
       places to include on seconds. 
    */ 

    var sign = num < 0 ? '-' : (plus ? '+' : '');
    var n = Math.abs(num);
    var n1 = Math.floor(n);	// d
    if (n1<10) n1 = '0' + n1;
    var n2 = (n-n1)*60;		// M.d
    var n3 = Math.floor(n2);// M
    if (n3<10) n3 = '0' + n3;
    var n4 = (n2-n3)*60;    // S.ddd
    var n5 = Numbers.format(n4, prec);
    if (n5<10) n5 = '0' + n5;
    return sign+n1+':'+n3+':'+n5;
}


function createAIJApertures(sources) {
    /* Take an input array of Gaia sources and create an in-memory
       text file (using Blob) that is in the format used by 
       AstroImageJ to mark apertures.  Returns the URL of the 
       Blob object.
    */

    // Initialize array: 
    var entries = [];
    // Start with some comment strings.  Make it an array 
    // so we can concat lines along with aperture lines. 
    comments = ['# Aperture file for use in AstroImageJ\n'];
    comments.push('# Target = TIC ' + tic_number + '\n');
    today = new Date().toISOString().split('T')[0] + '\n';
    comments.push('# RA and Dec are ICRS Gaia coordinates, proper motion applied to ' + today);
    comments.push('# Ref Star: 0=target star, 1=ref star\n');
    comments.push('# Centroid: 0=do not centroid, 1=centroid\n');
    comments.push('# Magnitude is estimated T mag from Gaia G, based on formula in TIC paper.\n');
    comments.push('# RA,      Dec, Ref Star, Centroid, Mag\n');
    var mags = [];
    var foundCentralStar = false;
    for (i=0; i < sources.length; i++) {
	const s = sources[i];
	var coo = toSexagesimal(s.ra/15, 3, false) +
	    ",  " + toSexagesimal(s.dec, 3, false);
	var target;
	// Is this the target star?  Check the Gaia ID, but also 
	// double-check the magnitude in case the Gaia DR2 ID from
	// the TIC has been re-assigned in eDR3 to a different star: 
	if ((s.data.Source == centralStar.gaia) && 
	    (Math.abs(parseFloat(s.data.magUsed) - centralStar.Tmag) < 0.2)) {
	    target = 1;
	    foundCentralStar = true;
	} else {
	    target = 0;
	}
	const line = coo + ", 0, " + target + ", " + s.data.magUsed + "\n";
	entries.push(line);
	mags.push(parseFloat(s.data.magUsed));
    }
    if (!foundCentralStar) {
	// Look at the first handful of stars and see if one of them has a similar
	// magnitude to the target star: 
	for (i=0; i < Math.min(5, entries.length); i++) {
	    if (Math.abs(mags[i] - centralStar.Tmag) < 0.1) {
		// Mags match pretty closely, mark this as the 
		// central star:
		entries[i] = entries[i].replace(" 0, 0, ", " 0, 1, ");
		console.log("Matched source " + i + " as central star for apertures, " +
			    "T = " + centralStar.Tmag + ", T(gaia) = " + mags[i]);
		foundCentralStar = true;
		break;
	    }
	}
    }
    if (!foundCentralStar) {
	console.log("Did not find a match for central star, " +
		    "none marked in AIJ apertures file."); 
    }
    let blob = new Blob(comments.concat(entries), {type: 'text/plain;charset=UTF-8'});
    blob.lastModifiedDate = new Date();
    blob.name = 'gaia_stars_TIC' + tic_number + '.radec';
    return blob;
}


function gaiaPopup(s) {
    /* Function for showing a customized popup for Gaia sources; much
       is copied out of the Aladin code for showPopup, but this allows
       us to construct our own content for the popup.  A number of the
       values displayed here are actually from the TIC, using the
       hashes we built while cycling through those sources.
    */

    var view = s.catalog.view;
    var d = s.data;
    g = d.Source; // Gaia ID, used to index some hashes
    view.popup.setTitle('<b>TIC ' + TIC_vals[g] + '</b><br/><br/>');
    var m = '<div class="equation">';
    // m += '<div><span>T</span> = <span>' + Tmag_vals[g] + '</span></div>';
    // m += '<div><span>&Delta;T</span> = <span>' + deltaT_vals[g] + '</span></div>';
    // m += '<div><span>r</span> = <span>' + d._r + '</span></div>';
    m += '<div>T = ' + Tmag_vals[g] + '</div>';
    m += '<div>&Delta;T = ' + deltaT_vals[g] + '</div>';
    m += '<div>r = ' + d._r + '</div>';
    m += '</div>'
    m += '<br/><div class="aladin-marker-measurement">';
    m += '<table>';
    for (var key in s.data) {
	m += '<tr><td>' + key + '</td><td>' + s.data[key] + '</td></tr>';
    }
    m += '</table>';
    m += '</div>';
    view.popup.setText(m);
    view.popup.setSource(s);
    view.popup.show();
}


// -------  end of Gaia section --------------


function toggleElements(box) {
    var item, overlay, color, link;

    link = null; // Most items don't have links

    if (box.id === 'gaia') {
	item = gaiaBlends;
	overlay = Gaia_boundary;
	color = colors.gaia;
	// Apertures link is toggled along with blends symbol: 
	link = document.getElementById('aij-link-span');
    } else if (box.id == 'simbad') {
	item = hipsSimbad;
	overlay = '';
	color = colors.simbad;
    } else if (box.id == 'gaiaAll') {
	item = gaiaAll;
	overlay = '';
	color = colors.gaiaAll;
    } else if (box.id == 'tic') {
	item = TIC;
	overlay = '';
	color = colors.tic;
    } else {
	console.log('Got unknown id in toggleElements: ' + box.id);
	console.log(box);
	return false; // unknown id
    }

    const legend = document.getElementById(box.id + "-legend");

    if (box.checked) {
	item.show();
	if (overlay) {overlay.show()};
	legend.style.stroke = color;
	if (link) {link.style.display="inline"};
    } else {
	item.hide();
	if (overlay) {overlay.hide()};
	legend.style.stroke = "none";
	if (link) {link.style.display="none"};
    }
}


function setupSimbad() {
    // Also add a Simbad layer option:
    hipsSimbad = A.catalogHiPS('https://axel.u-strasbg.fr/HiPSCatService/Simbad', 
			       {onClick: simbadPopup, 
				name: 'Simbad',
				color: colors.simbad,
				sourceSize: 14,
				shape: 'triangle',
			       });
    aladin.addCatalog(hipsSimbad);
    hipsSimbad.isShowing = false;

    let checkbox = document.getElementById('simbad');
    checkbox.checked = showSimbad;
    toggleElements(checkbox);
}

function simbadPopup(s) {
    /* Function for showing a customized popup for Simbad sources; much
       is copied out of the Aladin code for showPopup, but this allows
       us to construct our own content for the popup, including a link
       to the Simbad page for that source. 
    */

    var view = s.catalog.view;
    var d = s.data;
    simbad_url = 'https://simbad.harvard.edu/simbad/sim-id?Ident=' + 
	encodeURIComponent(d.main_id)
    view.popup.setTitle('<b>' + 
			d.main_id + '</b><br/>');
    var m = '<a href="' + simbad_url + '" target="_blank">Simbad</a>' +
	'<br/><div class="aladin-marker-measurement">';
    m += '<table>';
    for (var key in s.data) {
	m += '<tr><td>' + key + '</td><td>' + s.data[key] + '</td></tr>';
    }
    m += '</table>';
    m += '</div>';
    view.popup.setText(m);
    view.popup.setSource(s);
    view.popup.show();
}


function setupFFI() {
    // Add a TESS FFI image layer
    aladin.setOverlayImageLayer(aladin.createImageSurvey('TESS', 'TESS', 
							 'https://astro.swarthmore.edu/HiPS/TESS/', 
							 'J2000', 5, {imgFormat: 'png'}));
    aladin.getOverlayImageLayer().setAlpha(0);

    /* Set up a slider to set the opacity of the TESS 
       FFI image data - intially transparent.
    */ 
    var ffiAlpha = 0;
    var slider = document.getElementById('ffi_slider');
    slider.oninput = function() {
	ffiAlpha = this.value;
	$('#ffiAlpha').html(ffiAlpha);
	aladin.getOverlayImageLayer().setAlpha(ffiAlpha);
    }
}


function setAladinHeight() {
    //   Set height of the Aladin Lite div based on the height of the 
    //   header div, so all fits on the page.  Call this at page setup
    //   and on window resize.
    var aladinDiv = document.getElementById('aladin-lite-div');
    var checkboxDivHeight = document.getElementById('checkboxes').offsetHeight;
    var simbadHeight = document.getElementById('simbad-group').offsetHeight;
    //  If the height of the overall checkbox div is quite a bit more than the 
    // height of an individual div, it's likely that the display has wrapped onto 
    // multiple lines, so shrink the height of the Aladin div accordingly: 
    var heightRatio = checkboxDivHeight / simbadHeight;
    newHeight = Math.min(94, Math.pow(0.95, heightRatio - 1) * 100);
    aladinDiv.style.height = Number.parseFloat(newHeight).toPrecision(3) + "%";
    aladin.view.fixLayoutDimensions();
}


function mouseToRaDec(event, copyToClipboard) { 
    /* Get mouse coordinates from the input event, and return the RA,
       Dec as a sexigesimal string. If copyToClipboard is true, also
       copy the coordinate string to the system clipboard if the event
       is an alt-click (or option-click on the Mac).
    */

    let xymouse = aladin.view.imageCanvas.relMouseCoords(event);
    let radec = aladin.view.aladin.pix2world(xymouse.x, xymouse.y);
    let cooString = radec[0].toPrecision(8) + ' ' + radec[1].toPrecision(8);
    // Optionally copy coordinates to the clipboard:
    if ((copyToClipboard) && (event.altKey)) {
	navigator.clipboard.writeText(cooString);
    }
    return cooString;
}

function sexagesimalToDecimal(c) {
    /* Convert colon- or space-separated sexagesimal coordinates
       to decimal.  Does not do any hours -> degrees conversion.
    */

    var split_pattern;
    if (c.includes(':')) {
	split_pattern = /\s*:\s*/;
    } else {
	split_pattern = /\s+/;
    }

    var parts = c.split(split_pattern);
    if (parts.length != 3) {
	console.log('Could not parse coordinate ', c);
	return null;
    }

    let d = Math.abs(parseFloat(parts[0]));
    let m = parseFloat(parts[1]);
    let s = parseFloat(parts[2]);

    if (isNaN(d) || isNaN(m)|| isNaN(s)) {
	console.log('Could not parse coordinate ', c);
	return null;
    }

    var sign = 1;
    if (parts[0].includes('-')) {
	sign = -1;
    }
    return sign*(d + m/60 + s/3600);
}
