#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 17 10:37:07 2017
@author: nathenry

This module includes a series of functions that allow for automated geocoding
using the Google Maps, OpenStreetMaps, and GeoNames APIs.

Written in Python 3.6
"""

import json
import numpy as np
import pandas as pd
import requests
import sys
from os import remove
from platform import system
from time import sleep
import xmltodict
from haversine import haversine
from collections import namedtuple, OrderedDict

# Returns the right filepath to J:/ both locally and on the cluster
def j_header():
    if system() == "Linux":
        return "/home/j/"
    else:
        return "J:/"

# Returns the right filepath to H:/ both locally and on the cluster
def h_header():
    if system() == "Linux":
        return "/homes/nathenry/"
    else:
        return "H:/"
    

class SingleLocation:
    """This class stores the latitude and longitude from a single point
       returned by Google Maps. To initialize, it takes a dict with the items
       'lat' and 'lng'."""
    def __init__(self,location_dict):
        self.lat = float(location_dict['lat'])
        self.long = float(location_dict['lng'])


def get_centroid(northeast,southwest):
    center_lat = np.mean([northeast.lat,southwest.lat])
    center_long = np.mean([northeast.long,southwest.long])
    center_dict = {'lat':center_lat,
                   'lng':center_long}
    centroid = SingleLocation(center_dict)
    return centroid


def get_uncertainty(northeast,southwest):
    """Given the northeast and southwest corners of a bounding box, gives
       the north-south and east-west buffers for the geometry. The bounding
       box corners should be from the class SingleLocation."""
    # Check for impossible lats and longs\
    if ((np.absolute(northeast.lat)>90) or (np.absolute(southwest.lat)>90)):
        raise ValueError("Lats should be between -90 and 90 decimal degrees.")
    if ((np.absolute(northeast.long)>180) or (np.absolute(southwest.long)>180)):
        raise ValueError("Longs should be between -180 and 180 decimal degrees.")
    
    centroid = get_centroid(northeast,southwest)
    # Decimal degrees of latitude are always constant: traveling directly north
    #  1 dd will always be equivalent to 111.32 km
    km_per_dd_northsouth = 111.32
    # Decimal degrees of longitude VARY BASED ON THE LATITUDE: lines of latitude
    #  are furthest apart at the equator and move closer towards the poles.
    #  We must estimate the dd-to-km conversion depening on the latitude
    # EW DD length at a latitude ~ EW DD length at equator * cosine(latitude) 
    centroid_lat_radians = np.deg2rad(centroid.lat)
    km_per_dd_eastwest = 111.32 * np.cos(centroid_lat_radians)
    
    # Get the NS and EW difference in decimal degrees, then convert to kilometers
    delta_ns_dd = northeast.lat - southwest.lat
    delta_ns_km = delta_ns_dd * km_per_dd_northsouth
    delta_ew_dd = northeast.long - southwest.long
    delta_ew_km = delta_ew_dd * km_per_dd_eastwest
        
    # Returns a tuple: (North-South Buffer, East-West Buffer)
    return delta_ns_km, delta_ew_km


class SingleResult:
    """This class stores information about a single result from
       the Google Maps API"""
    def __init__(self,result_dict,source):
        # Source should be one of "OSM" and "Google Maps"
        if source not in ["OSM","Google Maps"]:
            raise ValueError("Source should be one of 'OSM' or 'Google Maps'")

        if source == "Google Maps":
            # Navigates the Google Maps dict and converts into class vars
            geom = result_dict['geometry']
            self.centroid = SingleLocation(geom['location'])
            if "bounds" in geom:
                self.northeast = SingleLocation(geom['bounds']['northeast'])
                self.southwest = SingleLocation(geom['bounds']['southwest'])
            else:
                self.northeast = self.centroid
                self.southwest = self.centroid
            self.address = result_dict['formatted_address']
            if "partial_match" in result_dict:
                self.partial_match = "Yes"
            else:
                self.partial_match = "No"
            # There is no such attribute as "type" in Google Maps'
            self.place_type = "Unknown"
        else:
            # Navigates the OSM dict and converts into class vars
            obj = result_dict
            # All floats have to be converted from 
            self.centroid = SingleLocation({'lat':obj['lat'],
                                            'lng':obj['lon']})
            if "boundingbox" in obj:
                self.northeast = SingleLocation({'lat':obj['boundingbox'][1],
                                                 'lng':obj['boundingbox'][3]})
                self.southwest = SingleLocation({'lat':obj['boundingbox'][0],
                                                 'lng':obj['boundingbox'][2]})
            else:
                self.northeast = self.centroid
                self.northwest = self.centroid
                
            if "display_name" in obj:
                self.address = obj['display_name']
            else:
                self.address = "Unknown"

            if "type" in obj:
                self.place_type = obj['type']
            self.partial_match = "Unknown"
        # The North/South and East/West buffers can now be determined for all pts
        self.buffer_ns_km, self.buffer_ew_km = get_uncertainty(self.northeast,
                                                               self.southwest)


def parse_osm_gm_result(full_json):
    """This function takes the full JSON object (already parsed into a dict or list)
       returned by Google Maps or OSM and returns the list of results as well 
       as some information about the bounding box containing ALL results."""

    # Set up some variables so you can use them even if <2 results are returned
    result_source = ''
    status = ''
    bounded_ns_km = np.nan
    bounded_ew_km = np.nan
    bounding_centroid_lat = np.nan
    bounding_centroid_long = np.nan
    r1_address = ''
    r1_type = ''
    r1_lat = np.nan
    r1_long = np.nan
    r1_buffer_ns = np.nan
    r1_buffer_ew = np.nan
    r1_partial_match = ''
    r2_address = ''
    r2_type = ''
    r2_lat = np.nan
    r2_long = np.nan
    r2_buffer_ns = np.nan
    r2_buffer_ew = np.nan
    r2_partial_match = ''

    if type(full_json) == dict:
        # The JSON comes from Google Maps
        result_source = "Google Maps"
        status = full_json['status']
    elif type(full_json) == list:
        # The JSON type is a list, and comes from OSM Nominatim
        result_source = "OSM"
        if len(full_json) > 0:
            status = "OK"
    else:
        raise ValueError("The full_json object should be in dict or list format")
        
    num_results = 0
    results_list = []
    
    # Only parse the results if there are correct results to parse
    if status=="OK":
        if result_source == "Google Maps":
            full_json = full_json['results']
        # The full_json object should now be a list of individual results dicts
        num_results = len(full_json)
        for result_json in full_json:
            # Creates an object of class SingleResult
            this_result = SingleResult(result_json,source=result_source)
            results_list.append(this_result)
            
        # Get the coordinates of the bounding box for all matched geographies
        far_north = max([i.northeast.lat for i in results_list])
        far_south = min([i.southwest.lat for i in results_list])
        far_east = max([i.northeast.long for i in results_list])
        far_west = min([i.southwest.long for i in results_list])
        bounded_all_northeast = SingleLocation({'lat':far_north,
                                                'lng':far_east})
        bounded_all_southwest = SingleLocation({'lat':far_south,
                                                'lng':far_west})
        bounded_ns_km, bounded_ew_km = get_uncertainty(bounded_all_northeast,
                                                       bounded_all_southwest)
        bounding_centroid_lat = np.mean([far_north,far_south])
        bounding_centroid_long = np.mean([far_east,far_west])
        if num_results >= 1:
            r1_address = results_list[0].address
            r1_type = results_list[0].place_type
            r1_lat = results_list[0].centroid.lat
            r1_long = results_list[0].centroid.long
            r1_buffer_ns = results_list[0].buffer_ns_km
            r1_buffer_ew = results_list[0].buffer_ew_km
            r1_partial_match = results_list[0].partial_match
        if num_results >= 2:
            r2_address = results_list[1].address
            r2_type = results_list[1].place_type
            r2_lat = results_list[1].centroid.lat
            r2_long = results_list[1].centroid.long
            r2_buffer_ns = results_list[1].buffer_ns_km
            r2_buffer_ew = results_list[1].buffer_ew_km
            r2_partial_match = results_list[1].partial_match
            
    # Return slightly different things depending on the source
    if result_source == "Google Maps":
        return (status, num_results,
                bounding_centroid_lat, bounding_centroid_long,
                bounded_ns_km, bounded_ew_km,
                r1_address, r1_lat, r1_long,
                r1_buffer_ns, r1_buffer_ew, r1_partial_match,
                r2_address, r2_lat, r2_long,
                r2_buffer_ns, r2_buffer_ew, r2_partial_match)
    else:
        # The source is OSM
        return (num_results,bounding_centroid_lat, bounding_centroid_long,
                bounded_ns_km, bounded_ew_km,
                r1_address, r1_type, r1_lat, r1_long,r1_buffer_ns, r1_buffer_ew,
                r2_address, r2_type, r2_lat, r2_long,r2_buffer_ns, r2_buffer_ew)


##############################################################################
# Helper functions for Google Maps
##############################################################################

def format_gmaps_args(address_text,key=None,iso=None):
    """This function formats the arguments for Google Maps. Arguments:
       address_text (str): The raw text of the address
       key (str): The key to be used for the Google Maps API
       iso (str), optional: Use this if you want to filter by country. Two-
          letter ISO code."""
    request_dict = {'address':address_text}
    if key is not None:
        request_dict['key'] = key
    
    if iso is not None:
        if len(str(iso))==2:
            # Add the uppercased ISO code to the request dictionary
            iso = iso.upper()
            component_filter = 'country:{}'.format(iso)
            request_dict['components'] = component_filter
    q = parse.urlencode(request_dict)
    return q

    
def gmaps_query(url_args,output_type='json'):
    """This function returns the Google Maps query in JSON format.
        url_args (str): Google Maps arguments in URL string form
        output_type (str): Determines output type. One of 'xml' or 'json'"""
    if output_type not in ['xml','json']:
        raise ValueError("output_type must be one of 'xml' or 'json'")
        
    base_url = "https://maps.googleapis.com/maps/api/geocode/"
    combined_url = "{}{}?{}".format(base_url,output_type,url_args)
    try:
        with request.urlopen(combined_url) as response:
            raw_output = response.read().decode('utf-8')
    except urllib.error.HTTPError:
        raw_output = '{"status":"Failed to open page"}'

    # Google Maps API will not process >50 queries per second
    sleep(.025)
    return raw_output


def gm_geocode_data_frame(df,
                          api_key,
                          address_col="address_query",
                          iso_2_col=None):
    """This function takes a data frame and geocodes every row based on the
       value given in an address column.

       Inputs
       df (Pandas dataframe): A dataframe containing all the locations
       api_key (str): The Google Maps API key
       address_col: Name of the column containing addresses for geocoding
       iso_2_col (optional): The ISO-2 code for the country being geocoded

       Outputs
       Expanded dataframe containing geocoding results with new columns, including
       the API output for the first two results, and the size of the bounding box
       containing ALL results.""" 


    # Create a new column for the formatted API query text
    if type(api_key) != str:
        raise ValueError("The Google Maps API key should be a string.")
    
    if iso_2_col is not None:
        df['gm_query'] = df.apply(lambda x: format_gmaps_args(address_text=x[address_col],
                                                              key=api_key,
                                                              iso=x[iso_2_col]),axis=1)
    else:
        # Exclude the iso argument
        df['gm_query'] = df.apply(lambda x: format_gmaps_args(address_text=x[address_col],
                                                              key=api_key),axis=1)
    df['gm_json_results'] = df['gm_query'].apply(lambda x: json.loads(gmaps_query(x)))
    
    df['gm_status'],df['gm_num_results'], df['gm_centroid_lat'], \
      df['gm_centroid_long'], df['gm_buffer_ns_km'], df['gm_buffer_ew_km'], \
      df['gm_r1_address'],df['gm_r1_lat'],df['gm_r1_long'], \
      df['gm_r1_buffer_ns'],df['gm_r1_buffer_ew'],df['gm_r1_part_match'], \
      df['gm_r2_address'],df['gm_r2_lat'],df['gm_r2_long'], \
      df['gm_r2_buffer_ns'],df['gm_r2_buffer_ew'], \
      df['gm_r2_part_match'] = zip(*df['gm_json_results'].map(parse_osm_gm_result))
    df = df.drop(labels=['gm_query','gm_json_results'],axis=1)
    return df


def gm_geocode_plain_text(in_text,
                       api_key,
                       iso_2=None):
    """This function takes in a single string and geocodes it using the Google
    Maps API.
    
    Inputs
    in_text (str): The text (in address format) that will be geocoded
    api_key (str): The Google Maps API key
    iso_2 (str, optional): The ISO-2 code for the country being geocoded.
    
    Outputs: A single-row dataframe containing results for the text."""

    # Create the output dataframe
    if iso_2 is not None:
        df = pd.DataFrame.from_dict({"input_text":[in_text],"iso_2":[iso_2]},
                                     orient='columns')        
        df_expanded = gm_geocode_data_frame(df,
                                            api_key=api_key,
                                            address_col='input_text',
                                            iso_2_col='iso_2')
    else:
        df = pd.DataFrame.from_dict({"input_text":[in_text]},
                                     orient='columns')        
        df_expanded = gm_geocode_data_frame(df,
                                            api_key=api_key,
                                            address_col='input_text')
    return df_expanded


##############################################################################
# Helper functions for Open Street Maps
##############################################################################

def format_osm_args(address_text):
    """This function formats the arguments for Google Maps. Arguments:
       address_text (str): The raw text of the address
    """
    request_dict = {'q':address_text}
    q = parse.urlencode(request_dict)
    return q


def osm_query(url_args, output_type="json"):
    """This function returns the output of an OSM Nominatim query as structured text.
        url_args (str): OSM arguments in URL string form
        output_type (str): Determines output type. One of 'html', 'xml', or 'json'
    """
    if output_type not in ['html','xml','json']:
        raise ValueError("output_type must be one of 'html', 'xml', or 'json'")

    #Create the formatted URL
    base_url = "http://nominatim.openstreetmap.org/search?"
    combined_url = "{}{}&format={}".format(base_url,url_args,output_type)
    # Get the JSON from Nominatim
    try:
        with request.urlopen(combined_url) as response:
            raw_output = response.read().decode('utf-8')
    except urllib.error.HTTPError:
        raw_output = '[]'
    # API will not process >50 queries per second
    sleep(.03)
    return raw_output    


def osm_geocode_data_frame(df,
                           address_col="address_query"):
    """This function takes a dataframe and geocodes every row in OSM using
    the value given in an address column.
    
    Inputs
    df (Pandas dataframe): A dataframe containing all the locations
    address_col (str): The name of the column containing addresses for geocoding"""
    
    # Format the query text correctly
    df['osm_query'] = df[address_col].apply(lambda x: format_osm_args(address_text=x))
    # Get the results of each query
    df['osm_json_results'] = df['osm_query'].apply(lambda x: json.loads(osm_query(x)))
    
    df['osm_num_results'], df['osm_centroid_lat'], \
      df['osm_centroid_long'], df['osm_buffer_ns_km'], df['osm_buffer_ew_km'], \
      df['osm_r1_address'],df['osm_r1_type'],df['osm_r1_lat'],df['osm_r1_long'], \
      df['osm_r1_buffer_ns'],df['osm_r1_buffer_ew'], \
      df['osm_r2_address'],df['osm_r2_type'],df['osm_r2_lat'], \
      df['osm_r2_long'], df['osm_r2_buffer_ns'], \
      df['osm_r2_buffer_ew'] = zip(*df['osm_json_results'].map(parse_osm_gm_result))
    
    df = df.drop(labels=['osm_query','osm_json_results'],axis=1)
    return df


def osm_geocode_plain_text(in_text):
    """This function takes in a single string and geocodes it using the OSM
    Nominatim API.
    Inputs
    in_text (str): The text (in address format) that will be geocoded"""
    df = pd.DataFrame.from_dict({'input_text':[in_text]},orient='columns')
    df_expanded = osm_geocode_data_frame(df,address_col='input_text')
    return df_expanded


##############################################################################
# Helper functions for GeoNames
##############################################################################

class SingleResult_geonames:
    """This class stores information about a single result from
       the GeoNames API"""
    def __init__(self,in_dict):
        self.name = in_dict['name'] if 'name' in in_dict else ''
        self.admin1 = in_dict['adminName1'] if 'adminName1' in in_dict else ''
        self.admin2 = in_dict['adminName2'] if 'adminName2' in in_dict else ''
        self.admin3 = in_dict['adminName3'] if 'adminName3' in in_dict else ''
        self.place_type = in_dict['fclName'] if 'fclName' in in_dict else ''
        if 'lat' in in_dict and 'lng' in in_dict:
            self.loc = SingleLocation(in_dict)
        else:
            self.loc = SingleLocation({'lat':np.nan,'lng':np.nan})


def geonames_parse_result(full_json):
    # Sets up variables to return
    r1_name = ''
    r1_admin1 = ''
    r1_admin2 = ''
    r1_admin3 = ''
    r1_type = ''
    r1_lat = np.nan
    r1_long = np.nan
    r2_name = ''
    r2_admin1 = ''
    r2_admin2 = ''
    r2_admin3 = ''
    r2_type = ''
    r2_lat = np.nan
    r2_long = np.nan
    
    num_results = 0
    buffer_all_ns = np.nan
    buffer_all_ew = np.nan
    all_results = []
    center_lat = np.nan
    center_long = np.nan    
    
    # If there are any results, there will be a "geonames" field within the dict
    if "geonames" in full_json:
        num_results = len(full_json['geonames'])
        for result_dict in full_json['geonames']:
            this_result = SingleResult_geonames(result_dict)
            all_results.append(this_result)
        # Check that at least one result is associated with a lat-long
        num_latlong = len([i for i in all_results if (~np.isnan(i.loc.lat) and ~np.isnan(i.loc.long))])
        if num_results > 0 and num_latlong > 0:
            max_lat = np.max([i.loc.lat for i in all_results if ~np.isnan(i.loc.lat)])
            min_lat = np.min([i.loc.lat for i in all_results if ~np.isnan(i.loc.lat)])
            max_long = np.max([i.loc.long for i in all_results if ~np.isnan(i.loc.long)])
            min_long = np.min([i.loc.long for i in all_results if ~np.isnan(i.loc.long)])
            center_lat = np.mean([max_lat,min_lat])
            center_long = np.mean([max_long,min_long])
            bbox_northeast = SingleLocation({'lat':max_lat,'lng':max_long})
            bbox_southwest = SingleLocation({'lat':min_lat,'lng':min_long})
            buffer_all_ns,buffer_all_ew = get_uncertainty(bbox_northeast,
                                                          bbox_southwest)
    if num_results >= 1:
        r1_name = all_results[0].name
        r1_admin1 = all_results[0].admin1
        r1_admin2 = all_results[0].admin2
        r1_admin3 = all_results[0].admin3
        r1_type = all_results[0].place_type
        r1_lat = all_results[0].loc.lat
        r1_long = all_results[0].loc.long
    if num_results >= 2:
        r2_name = all_results[1].name
        r2_admin1 = all_results[1].admin1
        r2_admin2 = all_results[1].admin2
        r2_admin3 = all_results[1].admin3
        r2_type = all_results[1].place_type
        r2_lat = all_results[1].loc.lat
        r2_long = all_results[1].loc.long
                             
    # Update the total number of results with the "totalResultsCount" if available
    if 'totalResultsCount' in full_json:
        num_results = full_json['totalResultsCount']

    return (num_results,center_lat,center_long,buffer_all_ns,buffer_all_ew,
            r1_name,r1_admin1,r1_admin2,r1_admin3,r1_type,r1_lat,r1_long,
            r2_name,r2_admin1,r2_admin2,r2_admin3,r2_type,r2_lat,r2_long)


def format_geonames_args(address,username,iso2=None):
    # Create a Python dict with all of the required parameters
    args_dict = {'q':address,'username':username}
    if iso2 is not None:
        args_dict['country'] = iso2
    # Create the url encoding of this dict
    q = parse.urlencode(args_dict)
    return q


def geonames_query(query_text):
    """Returns the output query in JSON.
       Input
       query_text (str): the url-encoded query text"""
    url_base = 'http://api.geonames.org/searchJSON?'
    full_url = '{}{}'.format(url_base,query_text)
    with request.urlopen(full_url) as response:
        raw_output = response.read().decode('utf-8')
    # Geonames API will not process >50 queries per second
    sleep(.03)
    return raw_output


def geonames_geocode_data_frame(df,address_col,username="demo",iso_2_col=None):
    """This function takes a dataframe and geocodes every row in OSM using
    the value given in an address column.
    Inputs
    df (Pandas dataframe): A dataframe containing all the locations
    address_col (str): The name of the column containing addresses for geocoding
    username (str, optional): The account username to associate with the
      query. Default 'demo'
    iso_2_col (str, optional): The column name containing ISO 2 codes for each address"""
    if iso_2_col is not None:                     
        df['geonames_query'] = df.apply(lambda x: format_geonames_args(x[address_col],
                                                                       username=username,
                                                                       iso2=x[iso_2_col]),axis=1)
    else:
        df['geonames_query'] = df.apply(lambda x: format_geonames_args(x[address_col],
                                                                       username=username),axis=1)
    
    df['gn_json_results'] = df['geonames_query'].apply(lambda x: json.loads(geonames_query(x)))
    
    df['gn_num_results'],df['gn_center_lat'],df['gn_center_long'], \
      df['gn_buffer_ns_km'],df['gn_buffer_ew_km'], \
      df['gn_r1_name'],df['gn_r1_admin1'],df['gn_r1_admin2'], \
      df['gn_r1_admin3'],df['gn_r1_type'],df['gn_r1_lat'],df['gn_r1_long'], \
      df['gn_r2_name'],df['gn_r2_admin1'],df['gn_r2_admin2'], \
      df['gn_r2_admin3'],df['gn_r2_type'],df['gn_r2_lat'], \
      df['gn_r2_long'] = zip(*df['gn_json_results'].map(geonames_parse_result))
      
    df = df.drop(labels=['geonames_query','gn_json_results'],axis=1)
    return df        


def geonames_geocode_plain_text(in_text,username='demo',iso_2=None):
    """This function takes in a single string and geocodes it using the
    Geonames API.
    Inputs
    in_text (str): The text (in address format) that will be geocoded
    username (str, optional): The account username to associate with the
      query. Default 'demo'
    iso_2_col (str, optional): The iso-2 code of the country containing this address"""
    # Create a dictionary that will store the input text and eventually the output
    single_row_dict = {'input_text':[in_text]}
    if iso_2 is not None:
        single_row_dict['iso2'] = [iso_2]
    # Turn the dict into a dataframe
    df = pd.DataFrame.from_dict(single_row_dict,orient='columns')
    if iso_2 is not None:
        expanded = geonames_geocode_data_frame(df,
                                               address_col='input_text',
                                               username=username,
                                               iso_2_col='iso2')
    else: 
        expanded = geonames_geocode_data_frame(df,
                                               address_col='input_text',
                                               username=username)
    return expanded
    


## REBUILDING FROM SCRATCH HERE
## REMEMBER TO ADD DOCUMENTATION TO EACH CLASS AND METHOD

class WebGeocodingManager(object):
    """This class manages the entire geocoding process for a single location.
    """
    def __init__(self, location_text, iso=None, execute=["GM","OSM","GN","FG"], 
                 gm_key=None, gn_key=None, results_per_app=2, max_buffer=20):
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
            get_results():
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
        results_to_return = [ pd.Series([]) ]
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
                    points_list   = [ [bb[0],bb[2]], [bb[1],bb[3]] ], #SW & NE
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
        except ValueError:
            pass


class FuzzyGInterface(WebInterface):
    """This is the specific web interface used for the FuzzyG geocoding tool."""
    def build_query(self):
        self.request_url = 'http://dma.jrc.it/fuzzygall/xml/'
        self.request_params = {
            'fuzzy' : '0',
            'start' : '0',
            'end'   : '2',
            'q'     : self.location_text
        }
        if self.iso is not None and len(str(self.iso)) == 2:
            self.request_params['cc'] = self.iso

    def populate_locs(self):
        output_dict = xmltodict.parse(self.output.text)
        if output_dict['fuzzyg']['response']['results'] is not None:
            response_list = output_dict['fuzzyg']['response']['results']['result']
            num_locs = min([ len(response_list), self.n_results ])
            for i in range(0, num_locs):
                loc_dict = response_list[i]
                self.location_results.append(
                    GeocodedLocation(
                        points_list = [
                            [loc_dict['ddlong'], loc_dict['ddlat']]
                        ],
                        address_name = loc_dict['fullname'],
                        location_type = loc_dict['dsg']['#text'],
                        source = 'FuzzyG'
                    )
                )