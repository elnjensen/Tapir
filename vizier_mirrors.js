// Routines for finding the user's location via IP 
// address, and then using that to find the URL 
// of the nearest Vizier mirror. 
//  Ideally should be called from an async function
// to allow it to complete before using the results. 
// For example: 
//
// async function showVizier() {
//     mylatlong = await getCoords('');
//     // Handle errors here if coords are blank.
//     console.log('My lat and long: ', mylatlong[0], mylatlong[1]);
//     viz = nearestVizier(mylatlong[0], mylatlong[1]);
//     console.log('Nearest vizier server is ', viz.url, viz.location, viz.distance, ' km.');
// }

// $(document).ready( function() {
// 	showVizier();
//     });

// Requires that jquery has been loaded before calling these functions. 
// Copyright 2020, Eric Jensen, ejensen1@swarthmore.edu

function distance(lat1, long1, lat2, long2) {
    /* Return the great-circle distance along the 
       Earth's surface between the two specified
       latitude/longitude points.  Input lat/long
       should be in degrees, returned distance in km. 
    */ 

    const deg2rad = Math.PI / 180;
    const R_Earth = 6378; // km

    // Haversine formula for distance from 
    // http://www.movable-type.co.uk/scripts/latlong.html
    const phi1 = lat1 * deg2rad;
    const phi2 = lat2 * deg2rad;
    const delPhi = (lat2-lat1) * deg2rad;
    const delLam = (long2-long1) * deg2rad;
    
    const a = Math.sin(delPhi/2) * Math.sin(delPhi/2) +
	Math.cos(phi1) * Math.cos(phi2) *
	Math.sin(delLam/2) * Math.sin(delLam/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R_Earth * c;
}

function nearestVizier(lat,lon) {
    /* Given input latitude and longitude in degrees, return
       an object from above mirrors list for the nearest 
       Vizier mirror.  Caller will need to pull out URL 
       or name or other desired properties.
       Lat, lon assumed to be in degrees. 
    */ 

    const mirrors = [ 
	       {url: 'https://vizier.u-strasbg.fr/', 
		location: 'Strasbourg, France', 
		latitude: '48.5790727',
		longitude: '7.7642605'},
	       {url: 'https://vizier.iucaa.in/',
		location: 'Kolkata, India', 
		latitude: '13.0878',
		longitude: '80.2785'},
	       {url: 'https://vizier.cfa.harvard.edu/',
		location: 'Harvard, USA', 
		latitude: '42.3751',
		longitude: '-71.1056'},
	       {url:  'https://vizier.inasan.ru/',
		location: 'Moscow, Russia', 
		latitude: '55.7522',
		longitude: '37.6156'},
	       // No https access for these at present: 
	       // 'http://vizier.hia.nrc.ca/', 
	       // 'http://vizier.nao.ac.jp/',
	       // 'http://vizier.idia.ac.za/',
	       // 'http://vizier.china-vo.org/',
		      ];


    var min_dist = 1e10;  // Very large
    var index_min = -1;
    for (i=0; i < mirrors.length; i++) {
	d = distance(lat, lon, mirrors[i].latitude, mirrors[i].longitude); 
	mirrors[i].distance = d.toPrecision(4);
	console.log(mirrors[i].location + ': ' + d.toPrecision(4) + ' km.');
	if (d < min_dist) {
	    index_min = i;
	    min_dist = d;
	}
    }
    return mirrors[index_min];
}

async function getCoords(ip) {
    // Get the user's location from IP address. 
    // Return two-element array of latitude and longitude. 

    var ipinfoURL;
    if (ip == '') {
	ipinfoURL = 'https://ipinfo.io/json';
    } else {
	ipinfoURL = 'https://ipinfo.io/' + ip + '/json';
    }
    let response;
    try {
	response = await $.ajax({
		url: ipinfoURL,
		method: 'GET',
		dataType: 'json',
	});
	return response.loc.split(",");
    } catch (error) {
	console.log('Error in getCoords:');
	console.error(error);
	return ['', ''];
    }
};

async function nearestVizierURL(ip='') {
    /* 
       All-in-one function to get the coordinates and return only the
       URL.  Defaults to using the IP from the user's browser (blank
       IP string) but can be called for a different IP if needed.  
    */
    mylatlong = await getCoords(ip);
    // Handle errors here if coords are blank.
    if (mylatlong[0] == '') {
	return '';
    }
    viz = nearestVizier(mylatlong[0], mylatlong[1]);
    return viz.url;
}
