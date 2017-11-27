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
import urllib
import sys
from os import remove
from platform import system
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from time import sleep
from urllib import parse, request


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
        if type(iso) is str and len(iso)==2:
            # Add the uppercased ISO code to the request dictionary
            iso = iso.upper()
            component_filter = 'country:{}'.format(iso)
            request_dict['components'] = component_filter
        elif iso is None or iso=='':
            pass
        else:
            raise ValueError("""The 'iso' argument must be the two-digit 
                                country ISO code.""")
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
            raw_output = response.read()
    except urllib.error.HTTPError:
        raw_output = '{"status":"Failed to open page"}'

    # Google Maps API will not process >50 queries per second
    sleep(.03)
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
            raw_output = response.read()
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
    '''Returns the output query in JSON.
       Input
       query_text (str): the url-encoded query text'''
    url_base = 'http://api.geonames.org/searchJSON?'
    full_url = '{}{}'.format(url_base,query_text)
    with request.urlopen(full_url) as response:
        raw_output = response.read()
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
    



##############################################################################
# If all sources agree on the same point, select it and the buffer as "best"
##############################################################################

def choose_best_points(df):
    """This function takes the geocoded df and determines if all sources agree on
    a single point. If so, the program chooses that point as "best" and determines
    the overall buffer for the points.
    Input:
    df (a geocoded Pandas dataframe)
    """

    # Check to see which sources were used to geocode
    gm_used = ('gm_status' in df.columns)
    osm_used = ('osm_num_results' in df.columns)
    gn_used = ('gn_num_results' in df.columns)

    # If none were used, return the unmodified DF
    if (not(gm_used) and not(osm_used) and not(gn_used)):
        print("None of the engines were used for geocoding!")
        return df

    # Depending on which sources were used, add all the columns to create points and buffers for
    # Do some stuff
    
    return df



##############################################################################
# Produce summary maps for each row in the dataframe
##############################################################################


def which_zoom_level(point_meta,
                     map_width_px=512,map_height_px=512):
    """This function takes in the northeast and southwest point, then returns
    what zoom level should be used to contain all of the needed points.
    Inputs
    Metadata for all the points (in dict form, where entry 'point' is a SingleLocation class)
    map_width_px, map_height_px (int): The map dimensions in pixels"""
    # First, get the latitude and longitude range needed to show all pixels
    # Get the far North, South, East, and West points
    far_north = max([i['point'].lat for i in point_meta])
    far_south = min([i['point'].lat for i in point_meta])
    far_east = max([i['point'].long for i in point_meta])
    far_west = min([i['point'].long for i in point_meta])    

    # Get the East-West and North-South ranges, multiplied a bit to see all 
    #  points well within the bounds
    range_multiplier = 1.1
    range_ew_dd = (far_east - far_west) * range_multiplier
    range_ns_dd = (far_north - far_south) * range_multiplier
    # If there is only one point, there will be a range of 0 (with rounding errors)
    # Set a minimum range over which to show data
    min_range_dd = .005
    range_ew_dd = max([range_ew_dd,min_range_dd])
    range_ns_dd = max([range_ns_dd,min_range_dd])

    # For info on how Google Maps and OSM display features by zoom level, see
    #   http://bit.ly/2ntiUmk
    # Calculate the E-W and N-S range, in decimal degrees
    lat_range_shown = float(map_width_px)/256.0 * 180
    long_range_shown = float(map_width_px)/256.0 * 360

    current_zoom = 0
    max_zoom = 12
    while current_zoom < max_zoom:
        next_zoom = current_zoom + 1
        lat_range_shown = lat_range_shown / 2
        long_range_shown = long_range_shown / 2
        viewbox_too_small = (lat_range_shown < (range_ns_dd * 1.1) or \
                             long_range_shown < (range_ew_dd * 1.1))
        if viewbox_too_small:
            return current_zoom
        else:
            current_zoom = next_zoom
    # If the while loop breaks, then we've reached the max zoom:
    return max_zoom


def get_gmaps_img_query(point_meta,zoom,api_key,
                        map_height_px=512,map_width_px=512):
    # Create an argument for the map dimensions (height and width in pixels)
    dimensions_arg = '{}x{}'.format(map_width_px,map_height_px)
    # Get the coordinates of the centroid for all pts (center of the map)
    centroid_lat = np.mean([max([i['point'].lat for i in point_meta]),
                            min([i['point'].lat for i in point_meta])])
    centroid_long = np.mean([max([i['point'].long for i in point_meta]),
                             min([i['point'].long for i in point_meta])])
    centroid_arg = '{},{}'.format(np.round(centroid_lat,decimals=5),
                                  np.round(centroid_long,decimals=5))
    
    # Generate marker arguments
    # Each marker comes with a separate argument "&markers=[styles]|[lat],[long]"
    # Get a list of separate arguments based on the point metadata
    marker_args_list = []
    for point_dict in point_meta:
        this_marker_specs = []
        this_marker_specs.append('color:{}'.format(point_dict['gmaps_color']))
        this_marker_specs.append('label:{}'.format(point_dict['gmaps_label']))
        this_marker_specs.append('{},{}'.format(point_dict['point'].lat,
                                                point_dict['point'].long))
        # Join all args for this marker using the %7C (|) joining char
        this_marker_args = '%7C'.join(this_marker_specs)
        this_marker_args = 'markers={}'.format(this_marker_args)
        marker_args_list.append(this_marker_args)
    # Finally, join the args for each marker togehter using '&'
    marker_args = '&'.join(marker_args_list)

    # Store all other args as a dict, then encode to URL format
    gmaps_args_dict = {'center':centroid_arg,
                       'zoom':zoom,
                       'size':dimensions_arg,
                       'scale':2,
                       'key':api_key}
    non_marker_args = parse.urlencode(gmaps_args_dict)
    base_url = "https://maps.googleapis.com/maps/api/staticmap"
    full_url = '{}?{}&{}'.format(base_url,non_marker_args,marker_args)
    return full_url


def get_osm_img_query(point_meta,zoom,
                      map_height_px=512,map_width_px=512):
    # Create an argument for the map dimensions (height and width in pixels)
    dimensions_arg = '{}x{}'.format(map_width_px,map_height_px)    

    # Get the coordinates of the centroid for all pts (center of the map)
    centroid_lat = np.mean([max([i['point'].lat for i in point_meta]),
                            min([i['point'].lat for i in point_meta])])
    centroid_long = np.mean([max([i['point'].long for i in point_meta]),
                             min([i['point'].long for i in point_meta])])
    centroid_arg = '{},{}'.format(np.round(centroid_lat,decimals=5),
                                  np.round(centroid_long,decimals=5))
    # Create a list of markers and combine them with the | operator
    marker_list = []
    for point_dict in point_meta:
        marker_list.append('{},{},{}'.format(point_dict['point'].lat,
                                             point_dict['point'].long,
                                             point_dict['osm_meta']))
    markers_arg = '|'.join(marker_list)

    # Format as dict and then translate to PHP query format
    osm_args_dict = {'show':1,
                     'center':centroid_arg,
                     'zoom':zoom,
                     'size':dimensions_arg,
                     'maptype':'mapnik',
                     'markers':markers_arg}
    osm_args_url = parse.urlencode(osm_args_dict)
    
    full_url = 'http://staticmap.openstreetmap.de/staticmap.php?{}'.format(osm_args_url)
    return full_url


def summary_maps(df,address_col,out_file_path,gmaps_key,project_name="Summary Maps"):
    """This function takes the output of geocoding and returns summary text
    and maps for each geocoding result.
    
    Inputs
    df: The dataframe output from geocoding
    address_col (str): The name of the column containing addresses for geocoding
    out_file_path: Where the PDF will be saved, including the .PDF extension
    project_name: Will be printed in the title and at the top of each page
    """


    # Next, check that at least one of the tests was run and that there are some results we can use
    which_engines = []
    for engine in ['gm','osm','gn']:
        can_use_engine = False
        # We can only use an engine if there are more than 0 results...
        if '{}_num_results'.format(engine) in df.columns:
            total_results = df['{}_num_results'.format(engine)].sum()
            if total_results > 0:
                can_use_engine = True
        # ... and if there are the appropriate lat and long columns
        needed_cols = ['_r1_lat','_r1_long','_r2_lat','_r2_long']
        for col in needed_cols:
            if '{}{}'.format(engine,col) not in df.columns:
                can_use_engine = False
        which_engines.append(can_use_engine)

    if which_engines == [False,False,False]:
        print("""Sorry, there wasn't enough information available in the 
        dataframe returned. Either the correct columns were not included
        or there were no results geocoded.""")
        pass
    
    # At least one of the results is usable
    
    # Set up the PDF output
    sheet_dimensions = (792,612)
    if out_file_path[-4:].lower() != '.pdf':
        out_file_path = '{}{}'.format(out_file_path,'.pdf')
    c = canvas.Canvas(out_file_path,pagesize=sheet_dimensions)
    
    # Set up info for maps on each page
    # Pixel dimensions of the eventual maps
    map_height_px = 512
    map_width_px = 512    
    # Set up some information
    # Random seed for tempfiles
    rand_seed = np.random.randint(0,1000000000)
    tempfiles_to_delete = []
    
    for page_num,page_info in df.iterrows():
        #Set up the page header        
        pg_txt = c.beginText()            
        pg_txt.setTextOrigin(.5*inch,7.9*inch)
        pg_txt.setFont("Helvetica-Oblique",14)
        pg_txt.textLine(project_name)
        # Title
        pg_txt.setTextOrigin(.5*inch,7.6*inch)
        pg_txt.setFont("Helvetica-Bold",20)
        pg_txt.textLine("{}: {}".format(page_num+1,page_info[address_col]))

        # Set the page up for printing individual match results
        pg_txt.setTextOrigin(inch,7.2*inch)
        pg_txt.setFont("Helvetica",12)
        pg_txt.setLeading(18)
        
        # Each of the six tuples in the following list represents a possible pt
        # Tuple items: Representation name, lat, long, match name, 
        #   Google Maps marker color, Google Maps marker label, OSM point specs
        to_check = [("(1) Google Maps top result","gm_r1_lat","gm_r1_long",
                     "gm_r1_address","blue","1","lightblue1"),
                    ("(2) Google Maps 2nd result","gm_r2_lat","gm_r2_long",
                     "gm_r2_address","blue","2","lightblue2"),
                    ("(3) OpenStreetMap top result","osm_r1_lat","osm_r1_long",
                     "osm_r1_address","blue","3","lightblue3"),
                    ("(4) OpenStreetMap 2nd result","osm_r2_lat","osm_r2_long",
                     "osm_r2_address","blue","4","lightblue4"),
                    ("(5) GeoNames top result","gn_r1_lat","gn_r1_long",
                     "gn_r1_name","blue","5","lightblue5"),
                    ("(6/Pin) GeoNames 2nd result","gn_r2_lat","gn_r2_long",
                     "gn_r2_name","blue","6","ltblu-pushpin")]
        all_points_on_page = []
        # Write individual results
        for item in to_check:
            # Check if there is a match            
            if ((item[1] in page_info) and (item[2] in page_info) and 
                (item[3] in page_info) and ~np.isnan(page_info[item[1]]) and 
                ~np.isnan(page_info[item[2]])):
                # In this case, a match exists
                match_text = ("{}: '{}'".format(item[0],page_info[item[3]]))
                pg_txt.textLine(match_text)
                # This dict contains information for the map plotters
                match_desc = {'point':SingleLocation({'lat':page_info[item[1]],
                                                      'lng':page_info[item[2]]}),
                              'gmaps_color':item[4],
                              'gmaps_label':item[5],
                              'osm_meta':item[6]}
                all_points_on_page.append(match_desc)
            else:
                # There is no match for this particular result
                match_text = ("{}: No match".format(item[0]))
                pg_txt.textLine(match_text)
        # If there was at least one match, plot it on the map
        if len(all_points_on_page) > 0:
            # Print out map headings
            pg_txt.setFont("Helvetica-Bold",14)
            pg_txt.setTextOrigin(.5*inch,5.55*inch)
            pg_txt.textLine("Google Maps Overlay:")
            pg_txt.setTextOrigin(5.55*inch,5.55*inch)
            pg_txt.textLine("OpenStreetMap Overlay:")

            zoom = which_zoom_level(all_points_on_page,
                                    map_height_px=map_height_px,
                                    map_width_px=map_width_px)
            
            gmaps_img_query = get_gmaps_img_query(point_meta=all_points_on_page,
                                                  zoom=zoom,
                                                  api_key=gmaps_key)
            osm_img_query = get_osm_img_query(all_points_on_page,zoom=zoom)

            # Temp filepath for local files
            # These will be deleted after the PDF has been written
            rand_seed = rand_seed + 1
            gmaps_temp_path = "{}temp/nathenry/tempfile_space/gmaps_{}.png".format(j_header(),
                                                                                   rand_seed)
            osm_temp_path = "{}temp/nathenry/tempfile_space/osm_{}.png".format(j_header(),
                                                                                 rand_seed)
            tempfiles_to_delete.append(gmaps_temp_path)
            tempfiles_to_delete.append(osm_temp_path)

            with open(gmaps_temp_path,'wb') as f:
                with request.urlopen(gmaps_img_query) as response:
                    f.write(response.read())
            
            with open(osm_temp_path,'wb') as f:
                with request.urlopen(osm_img_query) as response:
                    f.write(response.read())
            
            #Draw the Google Maps overlay and the OSM overlay
            c.drawImage(gmaps_temp_path,.5*inch,.5*inch,width=4.95*inch,height=4.95*inch)
            c.drawImage(osm_temp_path,5.55*inch,.5*inch,width=4.95*inch,height=4.95*inch)            
        else:
            # There were no maps to draw
            pg_txt.setFont("Helvetica-Bold",14)
            pg_txt.setTextOrigin(.5*inch,3*inch)
            pg_txt.textLine("(NO MAPS AVAILABLE)")
        
        c.drawText(pg_txt)            
        # Finish writing to the page
        c.showPage()
        # Finally, add another dot to stdout to show progress
        sys.stdout.write(".")
        sys.stdout.flush()
    # Finished iterating through pages. We're good!
    c.save()
    # Clean up: remove temp file paths
    for delete_me in tempfiles_to_delete:
        remove(delete_me)
                

