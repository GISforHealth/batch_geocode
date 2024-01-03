#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 17 10:37:07 2017
@author: Nathaniel Henry, nathenry@uw.edu

This module includes a series of functions that allow for automated geocoding
using the Google Maps, OpenStreetMaps, GeoNames, and FuzzyG APIs.

Written in Python 3.6
"""

import json
import numpy as np
import pandas as pd
import requests
import xmltodict
from haversine import haversine
from collections import namedtuple, OrderedDict


################################################################################
## HELPER FUNCTIONS
################################################################################

def check_iso(iso):
    """The geocoding services all take an ISO-2 code. If the passed value does
    not match the formatting for an ISO-2 code, pass None as the ISO code 
    instead."""
    if type(iso) is str and len(iso)==2:
        return iso.lower()
    else:
        return None


def geocode_row(address, iso=None, gm_key=None, gn_key=None, execute_names=None,
                results_per_app=None, max_buffer=None, track_progress=True):
    """This function geocodes a single address/ISO row from the input dataset.
    It instantiates a WebGeocodingManager object and runs the entire geocoding
    process using the WebGeocodingManager API. It then fetches and returns the 
    geocoding results as a pandas Series.

    Arguments: All arguments except for `address` are optional and will revert
    to the defaults for the WebGeocodingManager class.
        address (str): Text to geocode
        iso (str, optional): ISO-2 code for the location
        gm_key (str, optional): Activated Google Maps Geocoding API key passed 
            to the Google Maps geocoding web tool.
        gn_key (str, optional): Activated GeoNames username passed to the 
            Geonames web tool.
        execute_names (list, optional): List of string inputs representing web 
            geocoding tools to use. Valid options include "GM" (Google Maps), 
            "OSM" (OpenStreetMap), "GN" (GeoNames), and "FG" (FuzzyG).
        results_per_app (int, optional): How many results should be returned 
            from each geocoding application?
        max_buffer (numeric, optional): The maximum acceptable "buffer size" 
            (bounding box diagonal distance) for an individual result to take.
        track_progress (boolean, default True): If true，the function writes a 
            dot (.) to output each time this function runs.
    """
    # Define a list of arguments to be passed to a WebGeocodingManager object
    args_dict = {
        'location_text' : address,
        'iso' : check_iso(iso)
    }
    # For all other arguments, use the class defaults if they are not passed to
    #  this function
    if gm_key is not None: args_dict['gm_key'] = gm_key
    if gn_key is not None: args_dict['gn_key'] = gn_key
    if execute_names is not None: args_dict['execute'] = execute_names
    if results_per_app is not None: args_dict['results_per_app'] = results_per_app
    if max_buffer is not None: args_dict['max_buffer'] = max_buffer

    # Run the geocoding manager for this location
    webgm = WebGeocodingManager(**args_dict)
    webgm.create_web_interfaces()
    webgm.geocode()
    webgm.vet()
    geocoding_results = webgm.get_results_as_series()
    if track_progress:
        # Track progress using dots
        print('.', end='', flush=True)
    return geocoding_results


################################################################################
## GEOCODING DATA STRUCTURES AND METHODS
################################################################################

class WebGeocodingManager(object):
    """This class manages the entire geocoding process for a single location.
    """
    def __init__(self, location_text, iso=None, execute=["GM","OSM","GN","FG"], 
                 gm_key=None, gn_key=None, results_per_app=2, max_buffer=15):
        """This class manages the web geocoding process for a single location.
        It takes location text, and ISO-2 code, a list of web geocoding tools to
        execute, and keys for the two services that require them. The web
        geocoding tools return up to two GeocodedLocation objects per tool, 
        which can then be vetted and returned in a format that is convenient and
        readable into a Pandas DataFrame row.

        Methods:
            create_web_interfaces():
                Initialize all web geocoding tools to be used based on the 
                `execute` argument. This function fills the `execute_apps`
                attribute.
            geocode():
                Geocode location text for all initialized geocoding tools. This
                function fills the `location_results` attribute.
            vet():
                For all location results, determine which results can be 
                immediately excluded from consideration due to buffer size or
                other disqualifying properties. This function trips items from
                the `location_results` list.
            get_results_as_series():
                Return geocoded locations in a convenient, readable format for
                Pandas.

        Attributes:
            location_text (str): Text to geocode.
            iso (optional, str): ISO-2 code for the location
            execute_names (list): List of two-character inputs representing
                web geocoding tools to use. Valid options include "GM" (Google 
                Maps), "OSM" (OpenStreetMap), "GN" (GeoNames), and "FG" (FuzzyG).
            execute_apps (dict): Initialized web applications. This attribute is
                filled in the `create_web_interfaces` method.
            gm_key (str): Google Maps Geocoding API key passed to the Google 
                Maps geocoding web tool.
            gn_key (str): GeoNames username passed to the Geonames web tool.
            results_per_app (int): How many results should be returned from each
                geocoding application?
            max_buffer (numeric): The maximum acceptable "buffer size" (bounding
                box diagonal distance) for an individual result to take.
            location_results (dict): Dictionary of all GeocodedLocation objects
                returned from geocoding. This list is populated in the `geocode`
                method and is then trimmed in the `vet` method.
        """
        self.location_text = location_text
        self.iso = iso
        self.execute_names = execute
        self.execute_apps = dict() # To be filled in `instantiate_interfaces`
        self.gm_key = gm_key
        self.gn_key = gn_key
        self.results_per_app = results_per_app
        self.max_buffer = max_buffer
        self.location_results = dict()

    def create_web_interfaces(self):
        """Given a list of apps to execute, instantiate various web interfaces.
        """
        if "GM" in self.execute_names:
            self.execute_apps['GM'] = GMInterface(
                location_text = self.location_text,
                iso           = self.iso,
                key           = self.gm_key,
                n_results     = self.results_per_app
            )
        if "OSM" in self.execute_names:
            self.execute_apps['OSM'] = OSMInterface(
                location_text = self.location_text,
                iso           = self.iso,
                n_results     = self.results_per_app
            )
        if "GN" in self.execute_names:
            self.execute_apps['GN'] = GNInterface(
                location_text = self.location_text,
                iso           = self.iso,
                key           = self.gn_key,
                n_results     = self.results_per_app
            )
        if "FG" in self.execute_names:
            self.execute_apps["FG"] = FuzzyGInterface(
                location_text = self.location_text,
                iso           = self.iso,
                n_results     = self.results_per_app
            )

    def geocode(self):
        """Execute all web queries and build location objects from them.
        """
        for app_class in self.execute_apps.keys():
            # Build the API query
            self.execute_apps[app_class].build_query()
            # Execute the API query
            self.execute_apps[app_class].execute_query()
            # Compile geocoding results as GeocodedLocation objects
            self.execute_apps[app_class].populate_locs()
            # Collect top 2 GeocodedLocations from each web interface
            loc_res = self.execute_apps[app_class].return_locs()
            for i in range(len(loc_res)):
                self.location_results[f'{app_class}{i+1}'] = loc_res[i]

    def vet(self):
        """Execute some vetting of location outputs."""
        # This object will store points from all valid results
        combined_pts = list()
        num_valid  = 0
        # Vetting for individual location results based on buffer size
        for k,loc_res in self.location_results.items():
            if loc_res is not None:
                if loc_res.get_diag_buffer() <= self.max_buffer:
                    # If the location is valid, add its points to the combined list
                    combined_pts = combined_pts + loc_res.get_points_list()
                    num_valid = num_valid + 1
                else:                    
                    # Remove the location result if the buffer is too large
                    self.location_results[k] = None

        # Check to see if a best result can be generated from the bounding box
        #  of all valid location results combined
        if len(combined_pts) > 0:
            combined_location = GeocodedLocation(
                points_list = combined_pts,
                address_name = 'Vetted',
                location_type = f'Composite of {num_valid} geocoded locations',
                source = 'Vetted'
            )
            if combined_location.get_diag_buffer() <= self.max_buffer:
                self.location_results['best'] = combined_location

    def get_results_as_series(self):
        """Systematically pass back the location result as a pandas Series."""
        # Initialize empty results
        results_to_return = [ pd.Series([], dtype='Float64') ]
        valid_keys = [k for k in self.location_results.keys() 
                        if self.location_results[k] is not None]
        # Get a series representation of each non-empty location result, 
        #  changing names to match the key prefix
        for k in valid_keys:
            loc_series = self.location_results[k].get_attributes_as_series()
            loc_series.index = [f'{k}_{c}' for c in list(loc_series.index)]
            results_to_return.append( loc_series )
        # Combine all results into a single series
        return( pd.concat(results_to_return, axis=0) )


class GeocodedLocation(object):

    def __init__(self, points_list, address_name='', location_type='', source=''):
        """Take a list of points and instantiate a new location."""
        self.points_list   = points_list 
        self.address_name  = address_name
        self.location_type = location_type
        self.source        = source
        self.bound_box     = self.get_bounding_box()

    @staticmethod
    def calc_haversine_distance(a_long, a_lat, b_long, b_lat):
        pt_a = (a_lat, a_long)
        pt_b = (b_lat, b_long)
        dist = haversine(pt_a, pt_b)
        return dist

    def get_centroid(self):
        avg_long = np.nanmean([pt[0] for pt in self.points_list])
        avg_lat = np.nanmean([pt[1] for pt in self.points_list])
        return(avg_long, avg_lat)

    def get_bounding_box(self):
        BoundingBox = namedtuple('BoundingBox', ['min_x', 'min_y', 'max_x', 'max_y'])
        min_long = min(pt[0] for pt in self.points_list)
        min_lat = min(pt[1] for pt in self.points_list)
        max_long = max(pt[0] for pt in self.points_list)
        max_lat = max(pt[1] for pt in self.points_list)
        bound_box = BoundingBox(min_long, min_lat, max_long, max_lat)
        return bound_box

    def get_points_list(self):
        """Return the full points list used to define the object"""
        return self.points_list

    def get_diag_buffer(self):
        """Get the approximate distance (in km) of the bounding box diagonal."""
        diag_dist = self.calc_haversine_distance(a_long = self.bound_box.min_x,
                                                 a_lat = self.bound_box.min_y,
                                                 b_long = self.bound_box.max_x,
                                                 b_lat = self.bound_box.max_y)
        return diag_dist

    def get_attributes_as_series(self):
        """Return all relevant attributes as a pandas Series object."""
        centroid = self.get_centroid()
        buffer_dist = self.get_diag_buffer()
        series_index = ['name','type','long','lat','bb_n','bb_s','bb_e','bb_w',
                        'buffer']
        series_vals = [
            self.address_name, self.location_type, centroid[0], centroid[1], 
            self.bound_box.max_y, self.bound_box.min_y, self.bound_box.max_x,
            self.bound_box.min_x, buffer_dist]
        return pd.Series(series_vals, index=series_index)


class WebInterface(object):
    def __init__(self, location_text, iso=None, key=None, n_results=2):
        """This class is a parent class for all individual web geocoding tools.
        Given location text and optional arguments (including an API key for 
        some geocoding tools), construct a web query for the tool, recover text 
        from the web API, and populate the top two location results as
        GeocodedLocation objects.

        Methods:
            build_query(): Given location text, populate the URL and the API
                "payload" needed for the request to execute. This method 
                populates the `request_url` and `request_params` attributes. 
                This method is unique for each individual tool type.
            execute_query(): Execute the API query. This method populates the 
                `output` attribute, and is the same across all tool types.
            populate_locs(): Given the text output from the web API query, 
                populate valid GeocodingResult objects from the top two results.
                This method is unique for each individual tool type.
            return_locs(): Return the `location_results` attribute.

        Attributes:
            location_text (str): Input text for geocoding.
            iso (str): Input ISO-2 code for geocoding. Only accepted by some
                tools.
            key (str): API key or username. Only required for some tools.
            n_results (int): How many geocoding results should be populated?
            request_url (str): URL where the API query will be executed. This
                attribute is filled by `build_query()`.
            request_params (dict): Dictionary containing all arguments in the 
                API request "payload". This attribute is filled by 
                `build_query()`.
            output: API output object from the `requests` library. This object
                is populated by the `execute_query()` method.
            location_results: A list of up to two `GeocodedLocation` objects.
                This attribute is populated by the `populate_locs()` method.
        """
        self.location_text = location_text
        self.iso = iso
        self.key = key
        self.n_results = n_results
        self.request_url = None # Initialized in `build_query()`
        self.request_params = None # Initialized in `build_query()`
        self.output = None # Initialized in `execute_query()`
        self.location_results = [] # Initialized in `populate_locs()`

    def build_query(self):
        """This method will be different for each inherited class."""
        raise NotImplementedError

    def execute_query(self):
        """This method should be the same for every interface. Run a pre-defined
        query with appropriate error handling."""
        # TODO add more sophisticated error handling
        self.output = requests.get(
            url = self.request_url,
            params = self.request_params
        )

    def populate_locs(self):
        """This method will be different for every inherited class. Take JSON or
        XML input and use it to populate up to two GeocodedLocation objects."""
        raise NotImplementedError

    def return_locs(self):
        """Return self.location_results."""
        return self.location_results


class GMInterface(WebInterface):
    """This is the specific web interface used for Google Maps."""
    def build_query(self):
        self.request_url = 'https://maps.googleapis.com/maps/api/geocode/json'
        self.request_params = {
            'address' : self.location_text,
            'key'     : self.key
        }
        if self.iso is not None and len(str(self.iso))==2:
            self.request_params['components'] = f"country:{self.iso}"

    def populate_locs(self):
        output_dict = json.loads(self.output.text)
        if 'results' in output_dict.keys():
            response_list = output_dict['results']
            num_locs = min([ len(response_list), self.n_results ])
            for i in range(0, num_locs):
                loc = response_list[i]
                try:
                    if 'bounds' in loc['geometry'].keys():
                        bounds = loc['geometry']['bounds']
                        points_list = [
                            [bounds['northeast']['lng'], bounds['northeast']['lat']],
                            [bounds['southwest']['lng'], bounds['southwest']['lat']]
                        ]
                    elif 'location' in loc['geometry'].keys():
                        ll = loc['geometry']['location']
                        points_list = [ [ll['lng'], ll['lat']] ]
                    self.location_results.append(
                        GeocodedLocation(
                            points_list   = points_list,
                            address_name  = loc['formatted_address'],
                            location_type = ';'.join(loc['types']),
                            source        = 'GM'
                        )
                    )
                except KeyError:
                    pass


class OSMInterface(WebInterface):
    """This is the specific web interface used for OpenStreetMap."""
    def build_query(self):
        self.request_url = "http://nominatim.openstreetmap.org/search"
        self.request_params = {
            'q' : self.location_text,
            'format' : 'json',
            'addressdetails': 1
        }

    def in_correct_country(self, loc_dict, keep_unsure=True):
        """Helper method to determine whether a loaded location result is in the
        correct country."""
        if self.iso is None:
            # There was no ISO code passed and so no filter should be applied
            return True
        try:
            loc_iso = loc_dict['address']['country_code']
            locations_same = (loc_iso.lower() == str(self.iso).lower())
            return locations_same
        except KeyError:
            return keep_unsure

    def populate_locs(self):
        response_list = json.loads(self.output.text)
        # Keep only locations with the correct ISO code
        response_list = [i for i in response_list if self.in_correct_country(i)]
        num_locs = min([ len(response_list), self.n_results ])
        for i in range(0, num_locs):
            loc_dict = response_list[i]
            bb = [float(b) for b in loc_dict['boundingbox']]
            self.location_results.append(
                GeocodedLocation(
                    points_list   = [ [bb[2],bb[0]], [bb[3],bb[1]] ], #SW & NE
                    address_name  = loc_dict['display_name'],
                    location_type = loc_dict['class'],
                    source        = 'OSM'
                )
            )


class GNInterface(WebInterface):    
    """This is the specific web interface used for GeoNames."""
    def build_query(self):
        self.request_url = "http://api.geonames.org/searchJSON"
        self.request_params = {
            'q' : self.location_text,
            'username' : self.key
        }
        if self.iso is not None and len(str(self.iso)) == 2:
            self.request_params['country'] = self.iso        
    def populate_locs(self):
        try:
            response_list = json.loads(self.output.text)['geonames']
            num_locs = min([ len(response_list), self.n_results ])
            for i in range(0, num_locs):
                loc_dict = response_list[i]
                self.location_results.append(
                    GeocodedLocation(
                        points_list   = [
                            [float(loc_dict['lng']), float(loc_dict['lat'])]
                        ],
                        address_name  = loc_dict['name'],
                        location_type = loc_dict['fclName'],
                        source        = 'GN'
                    )
                )
        except (ValueError, KeyError) as e:
            pass


class FuzzyGInterface(WebInterface):
    """This is the specific web interface used for the FuzzyG geocoding tool."""
    def build_query(self):
        self.request_url = 'http://dma.jrc.it/fuzzyg/xml/'
        self.request_params = {
            'fuzzy' : '0',
            'start' : '0',
            'end'   : '2',
            'q'     : self.location_text
        }
        if self.iso is not None and len(str(self.iso)) == 2:
            self.request_params['cc'] = self.iso.upper() # ISO2 must be uppercase

    def populate_locs(self):
        output_dict = xmltodict.parse(self.output.text)
        if output_dict['fuzzyg']['response']['results'] is not None:
            response_list = output_dict['fuzzyg']['response']['results']['result']
            if isinstance(response_list, OrderedDict):
                # There is only one result
                num_locs = 1
                response_list = [response_list]
            else:
                num_locs = min([ len(response_list), self.n_results ])
            for i in range(0, num_locs):
                loc_dict = response_list[i]
                self.location_results.append(
                    GeocodedLocation(
                        points_list = [
                            [float(loc_dict['ddlong']), float(loc_dict['ddlat'])]
                        ],
                        address_name = loc_dict['fullname'],
                        location_type = loc_dict['dsg']['#text'],
                        source = 'FuzzyG'
                    )
                )