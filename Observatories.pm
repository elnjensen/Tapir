package Observatories;

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



use warnings; 
use strict;

# This package creates several hashes of observatory names and
# coordinates, which can be re-used by various routines that need to
# provide this information.  Adding observatories here avoids them
# having to be re-defined in multiple places. 

use Exporter;
our @ISA = qw(Exporter);

# Allow all of these to be exported:
our @EXPORT = qw(%observatories_asia
		 %observatories_western_north_america
		 %observatories_australia
		 %observatories_europe
		 %observatories_africa
		 %observatories_south_america
		 %observatories_eastern_us
		 );


# Define the lists of observatories.  Latitude is in degrees, with
# north being positive.  Longitude is also in degrees, with east being
# positive.  timezone_integer is number of hours from UTC; timezone is
# a string that will be recognized as a valid timezone name by
# DateTime::TimeZone.   If you want to add something here and need to
# find the proper timezone name, you can run
#
#  perl -e 'use DateTime; \
#     $country = "US";  # or other two-letter country code. \
#     print join("\n", DateTime::TimeZone->names_in_country($country)); ' 
#
# to see a list of timezone names for the given country.  Or call
# DateTime::TimeZone->all_names in the same way to get every name.

our %observatories_asia = (

	   "Beijing XingLong Observatory, China" => {
	       latitude => 40.393333,
	       longitude => -242.425000,
	       timezone_integer => -8,
	       timezone => 'Asia/Shanghai',
	   },

	   "Vainu Bappu Observatory, India" => {
	       latitude => 12.576660,
	       longitude => -281.173400,
	       timezone_integer => -5,
	       timezone => 'Asia/Kolkata',
	   },

	   "Indian Astronomical Observatory, Hanle" => {
	       latitude => 32.779400,
	       longitude => -281.035830,
	       timezone_integer => -5,
	       timezone => 'Asia/Kolkata',
	   },

	    "Aryabhatta Research Institute, India" => {
	       latitude => 29.360000,
	       longitude => -280.543610,
	       timezone_integer => -5,
	       timezone => 'Asia/Kolkata',
	   },


			  );

our %observatories_western_north_america = (

	   "Kitt Peak National Observatory" => {
	       latitude => 31.963333,
	       longitude => -111.600000,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },

	   "Mount Lemmon" => {
	       latitude => 32.416667,
	       longitude => -110.731667,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },

	   "MMT Observatory" => {
	       latitude => 31.688333,
	       longitude => -110.885000,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },

	   "Lowell Observatory" => {
	       latitude => 35.096667,
	       longitude => -111.535000,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },


	   "Whipple Observatory" => {
	       latitude => 31.680944,
	       longitude => -110.877500,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },


	   "Mount Graham Observatory" => {
	       latitude => 32.701667,
	       longitude => -109.891667,
	       timezone_integer => 7,
	       timezone => 'America/Phoenix',
	   },


	   "Apache Point Observatory" => {
	       latitude => 32.780000,
	       longitude => -105.820000,
	       timezone_integer => 7,
	       timezone => 'MST7MDT',
	   },


	   "Mauna Kea (Keck, Gemini, CFHT, Subaru, IRTF, etc.)" => {
	       latitude => 19.828333,
	       longitude => -155.478333,
	       timezone_integer => 10,
	       timezone => 'Pacific/Honolulu',
	   },


	   "Dominion Astrophysical Observatory" => {
	       latitude => 48.521667,
	       longitude => -123.416667,
	       timezone_integer => 8,
	       timezone => 'America/Vancouver',
	   },


	   "Lick Observatory" => {
	       latitude => 37.343333,
	       longitude => -121.636667,
	       timezone_integer => 8,
	       timezone => 'PST8PDT',
	   },


	   "McDonald Observatory" => {
	       latitude => 30.671667,
	       longitude => -104.021667,
	       timezone_integer => 6,
	       timezone => 'CST6CDT',
	   },

	   "Observatorio Astronomico Nacional, San Pedro Martir" => {
	       latitude => 31.029167,
	       longitude => -115.486944,
	       timezone_integer => 7,
	       timezone => 'America/Tijuana',
	   },

	   "Observatorio Astronomico Nacional, Tonantzintla" => {
	       latitude => 19.032778,
	       longitude => -98.313889,
	       timezone_integer => 8,
	       timezone => 'America/Mexico_City',
	   },

	   "Palomar Observatory" => {
	       latitude => 33.356000,
	       longitude => -116.863000,
	       timezone_integer => 8,
	       timezone => 'PST8PDT',
	   },


	   "Red Buttes Observatory, Wyoming" => {
	       latitude => 41.17642,
	       longitude => -105.57403,
	       timezone => 'MST7MDT',
	   },

	   "Wyoming Infrared Observatory (WIRO)" => {
	       latitude => 41.09706,
	       longitude => -105.97653,
	       timezone => 'MST7MDT',
	   },

	   "Boyce-Astro Research Observatory (San Diego)" => {
	       latitude => 32.6133,
	       longitude => -116.3319,
	       timezone => 'America/Los_Angeles',
	   }, 

	   "Rothney Astrophysical Observatory (Calgary)" => {
	       latitude => 50.868039,
	       longitude => -114.291142,
	       timezone => 'America/Edmonton',
	   }, 

          "New Mexico Skies, Mayhill, NM" => {
              latitude => 32.90388889,
              longitude => -105.52888889,
              timezone_integer => 7,
              timezone => 'MST7MDT',
          },

          "Sierra Remote Observatories, CA" => {
              latitude => 37.07055,
              longitude => -119.4128,
	      timezone => 'America/Los_Angeles',
          },

          "Table Mountain Observatory, CA" => {
              latitude => 34.38139,
              longitude => -117.68194,
	      timezone => 'America/Los_Angeles',
          },

          "Sommers-Bausch Observatory, Univ. of Colorado" => {
              latitude => 40.00371,
              longitude => -105.2630,
	      timezone => 'America/Denver',
          },
					   );



our %observatories_australia = (

	   "Mt. Stromlo Observatory" => {
	       latitude => -35.320650,
	       longitude => 149.0081,
	       timezone_integer => -10,
	       timezone => 'Australia/Sydney',
	   },

	   "Mt. Kent Observatory" => {
	       latitude => -27.797861,
	       longitude => 151.855417,
	       timezone => 'Australia/Brisbane',
	   },

	   "Anglo-Australian Observatory / Siding Spring" => {
	       latitude => -31.274,
	       longitude => 149.069,
	       timezone_integer => -10,
	       timezone => 'Australia/Sydney',
	   },

	   "Mount John University Observatory, New Zealand" => {
	       latitude => -43.986667,
	       longitude => 170.465,
	       timezone_integer => -12,
	       timezone => 'Pacific/Auckland',
	   },

			       );




our %observatories_europe = (

	   "Roque de los Muchachos, La Palma" => {
	       latitude => 28.758333,
	       longitude => -17.880000,
	       timezone_integer => 0,
	       timezone => "Atlantic/Canary",
	   },

	   "Observatorio Terrassa, Spain" => {
	       latitude => 41.571578,
	       longitude => 2.0349,
	       timezone_integer => -1,
	       timezone => 'Europe/Madrid',
	   },

	   "Observatorio de Sierra Nevada, Spain" => {
	       latitude => 37.064167,
	       longitude => -3.384722,
	       timezone_integer => -1,
	       timezone => 'Europe/Madrid',
	   },

	   "SLN - Catania Astrophysical Observatory, Italy" => {
	       latitude => 37.691667,
	       longitude => -345.026667,
	       timezone_integer => -1,
	       timezone => 'Europe/Rome',
	   },

	   "Mt. Ekar Observatory, Asiago, Italy" => {
	       latitude => 45.848589,
	       longitude => -348.418867,
	       timezone_integer => -1,
	       timezone => 'Europe/Rome',
	   },

	   "Ege University Observatory, Izmir, Turkey" => {
	       latitude => 38.398333,
	       longitude => 27.275000,
	       timezone_integer => 2,
	       timezone => 'Europe/Istanbul',
	   },

	   "Tubitak National Observatory, Turkey" => {
	       latitude => 36.825000,
	       longitude => 30.333333,
	       timezone_integer => -2,
	       timezone => 'Europe/Istanbul',
	   },

	   "National Astronomical Observatory Rozhen - Bulgaria" => {
	       latitude => 41.693056,
	       longitude => -335.256111,
	       timezone_integer => -2,
	       timezone => 'Europe/Sofia',
	   },

	   "Calar Alto Observatory, Spain" => {
	       latitude => 37.223611,
	       longitude => -2.546250,
	       timezone_integer => -1,
	       timezone => 'Europe/Madrid',
	   },

	   "Observatorium Hoher List (Universität Bonn) - Germany" => {
	       latitude => 50.162760,
	       longitude => 6.850000,
	       timezone_integer => -1,
	       timezone => 'Europe/Berlin',
	   },

			    );

our %observatories_africa = (

	   "Boyden Observatory, Bloemfontein, South Africa" => {
	       latitude => -29.038889,
	       longitude => -332.594444,
	       timezone_integer => -2,
	       timezone => 'Africa/Johannesburg',
	   },

	   "South African Astronomical Observatory" => {
	       latitude => -32.379444,
	       longitude => -339.189306,
	       timezone_integer => -2,
	       timezone => 'Africa/Johannesburg',
	   },

			    );

our %observatories_south_america = (


	   "Cerro Tololo Interamerican Observatory" => {
	       latitude => -30.165278,
	       longitude => -70.815000,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },

	   "Gemini South Observatory" => {
	       latitude => -30.240750,
	       longitude => -70.736693,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },

	   "European Southern Observatory: La Silla" => {
	       latitude => -29.256667,
	       longitude => -70.730000,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },


	   "European Southern Observatory: Paranal" => {
	       latitude => -24.625000,
	       longitude => -70.403333,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },

	   "ALMA" => {
	       latitude => -23.029,
	       longitude => -67.755,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },


	   "Las Campanas Observatory" => {
	       latitude => -29.003333,
	       longitude => -70.701667,
	       timezone_integer => 4,
	       timezone => 'America/Santiago',
	   },


	   "Observatorio Astronomico de La Plata, Buenos Aires" => {
	       latitude => -34.906751,
	       longitude => -57.932299,
	       timezone_integer => 3,
	       timezone => 'America/Argentina/Buenos_Aires',
	   },

	   "Estacion Astrofisica Bosque Alegre, Cordoba, Argentina" => {
	       latitude => -31.598333,
	       longitude => -64.545833,
	       timezone_integer => 3,
	       timezone => 'America/Argentina/Cordoba',
	   },

	   "National Observatory of Venezuela" => {
	       latitude => 8.790000,
	       longitude => -70.866667,
	       timezone_integer => 4,
	       timezone => 'America/Caracas',
	   },

	   "Laboratorio Nacional de Astrofisica, Brazil" => {
	       latitude => -22.534444,
	       longitude => -45.582500,
	       timezone_integer => 3,
	       timezone => 'America/Sao_Paulo',
	   },


	   "Complejo Astronomico El Leoncito, San Juan, Argentina" => {
	       latitude => -31.799167,
	       longitude => -69.295000,
	       timezone_integer => 3,
	       timezone => 'America/Argentina/San_Juan',
	   },

    );



our %observatories_eastern_us = (

	   "Bowling Green State Univ. Observatory, Ohio" => {
	       latitude => 41.378333,
	       longitude => -83.659167,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Collins Observatory, Colby College, Maine" => {
	       latitude => 44.56667,
	       longitude =>  -69.656378,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Smith College Observatory, Northampton, MA" => {
	       latitude => 42.317036,
	       longitude =>  -72.639514,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Moore Observatory, Univ. of Louisville, Kentucky" => {
	       latitude => 38.344792,
	       longitude => -85.528475,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Harvard Clay Telescope, Cambridge, MA" => {
	       latitude => 42.3766,
	       longitude => -71.1169,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },


	   "Oak Ridge Observatory, Harvard, MA" => {
	       latitude => 42.505261,
	       longitude => -71.558144,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Leander McCormick Observatory, Univ. of Virginia" => {
	       latitude => 38.033333,
	       longitude => -78.523333,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Black Moshannon Observatory, State College PA" => {
	       latitude => 40.921667,
	       longitude => -78.005000,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },


	   "Michael L. Britton Observatory, Dickinson College, PA" => {
	       latitude => 40.20398,
	       longitude => -77.19786,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },


	   "Fan Mountain Observatory, VA" => {
	       latitude => 37.878333,
	       longitude => -78.693333,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Whitin Observatory, Wellesley College, MA" => {
	       latitude => 42.295000,
	       longitude => -71.305833,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Olin Observatory, Connecticut College, CT" => {
	       latitude => 41.378889,
	       longitude => -72.105278,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Sperry Observatory, Union County College, NJ" => {
	       latitude => 40.66632,
	       longitude => -74.32327,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Peter van de Kamp Observatory, Swarthmore College, PA" => {
	       latitude => 39.907100,
	       longitude => -75.355550,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

           "Union College Observatory, NY" => {
	       latitude => 42.8176,
	       longitude => -73.9283,
	       timezone => 'EST5EDT',
           },

	   "Van Vleck Observatory, Wesleyan University, CT" => {
	       latitude => 41.555000,
	       longitude => -72.659167,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Vassar College Observatory, Poughkeepsie, NY" => {
	       latitude => 41.683011,
	       longitude => -73.890604,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Williams College Observatory, MA" => {
	       latitude => 42.7115,
	       longitude => -73.2052,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Mittelman Observatory, Middlebury College, VT" => {
	       latitude => 44.0134,
	       longitude => -73.1813,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "George R. Wallace, Jr. Astrophysical Observatory, MA" => {
	       latitude => 42.295,
	       longitude => -71.485,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Foggy Bottom Observatory, Colgate Univ., NY" => {
	       latitude => 42.81651,
	       longitude => -75.532568,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Breyo Observatory, Siena College, NY" => {
	       latitude => 42.719546,
	       longitude => -73.751433,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "C.E.K. Mees Observatory, Univ. Rochester, NY" => {
	       latitude => 42.7002778,
	       longitude => -77.4087667,
	       timezone_integer => 5,
	       timezone => 'EST5EDT',
	   },

	   "Observatoire du Mont-Mégantic, Québec" => {
	       latitude => 45.455683,
	       longitude => -71.1521,
	       timezone_integer => 5,
	       timezone => 'America/Toronto',
	   },
				);



