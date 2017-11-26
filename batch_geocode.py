#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 17 10:37:07 2017
@author: nathenry

This module includes a series of functions that allow for automated geocoding
using the Google Maps, OpenStreetMaps, and GeoNames APIs.

You can edit the paths within this program, or else call it from the command line.

Written in Python 3.6
"""

import argparse
import json
import numpy as np
import pandas as pd
import sys
import query_funcs as qf
from os.path import join
from numpy.random import choice as randoneof
from time import sleep


def check_cmd(cmd_arg,default_arg,value_name):
    """This function determines whether to use the coomand-line value or the 
    default value for a given program parameter."""
    if cmd_arg:
        print("The command-line argument, '{}', will be used for the {}.".format(cmd_arg,
                                                                               value_name))
        sleep(1)
        return cmd_arg
    else:
        print("The program's default value, '{}', will be used for the {}.".format(default_arg,
                                                                                   value_name))
        sleep(1)
        return default_arg




if __name__ == "__main__":
    """
    This section of the program will run from the command line or an 
    interactive prompt.
    """
    # System setup for users at IHME
    if 'win' in sys.platform:
        j_head = "J:/"
        h_head = "H:/"
    else:
        j_head = "/home/j/"
        # If you are adding paths inline, change this to your own username
        h_head = "homes/nathenry"

    ######################################################################
    # SET DEFAULT FILEPATHS AND VALUES
    ######################################################################

    # Set the default input and output files
    # These files will be used if no command line arguments are passed
    in_file = join(j_head,'temp/nathenry/testing_google_maps_query/test_query_sheet.xlsx')
    out_file = join(j_head,'temp/nathenry/testing_google_maps_query/test_query_output.xlsx')
    pdf_file = join(j_head,'temp/nathenry/testing_google_maps_query/test_query_maps.pdf')
    
    # Set the default name of the column to be geocoded
    geocode_col="for_geocoding"
    # Set the default name of the column containing ISO-2 codes
    # (None is an acceptable value)
    iso2_col=None

    # Data key for the Google Maps Geocoding API
    # Generate your own here:
    # https://developers.google.com/maps/documentation/geocoding/get-api-key
    gmaps_key = None
    # Data key for the Google Maps Static Maps API
    # As of September 2017, this is different from the Google Maps Geocoding API
    # Generate your own here: 
    # https://developers.google.com/maps/documentation/static-maps/
    static_maps_key = None
    # Geonames username
    # Create your own account and activate your username at http://geonames.org
    geonames_username = None
    # If no default key are set or passed through the command line, default API
    #   keys and usernames will be read from the following file.
    keys_file = join(j_head,'temp/nathenry/testing_google_maps_query/api_keys/keys.json')
    # Whether or not to make maps
    make_maps = True

    ######################################################################
    # SET UP AND READ COMMAND LINE ARGUMENTS, IF ANY
    ######################################################################
    print("\n*********************************")
    print("***     SET UP PARAMETERS     ***")
    print("*********************************")

    # If any command line arguments were passed, set up and read args
    if len(sys.argv) > 1:
        # This means some arguments were passed
        # Set up possible arguments
        parser = argparse.ArgumentParser()
        parser.add_argument("-i","--infile",type=str,help="The location of the input Excel file")
        parser.add_argument("-o","--outfile",type=str,help="The name of the output file")
        parser.add_argument("-p","--pdf",type=str,help="The location of the PDF maps")
        parser.add_argument("-a","--address",type=str,help="The name of the column to geocode")
        parser.add_argument("-s","--iso",type=str,help="The name of the file's ISO2 column (if any)")
        parser.add_argument("-k","--keygm",type=str,help="Your own activated Google Maps geocoding key (optional)")
        parser.add_argument("-m","--keystatic",type=str,help="Your own activated Google Maps Static Maps key (optional)")
        parser.add_argument("-g","--geonames",type=str,help="Your own activated Geonames username (optional)")
        parser.add_argument("-n","--nomaps", action="store_true", help="Add this argument to skip making vetting maps (optional)")
        c_args = parser.parse_args()

        # Check the command line values:
        in_file = check_cmd(c_args.infile,in_file,"input spreadsheet filepath")
        out_file = check_cmd(c_args.outfile,out_file,"output spreadsheet filepath")
        pdf_file = check_cmd(c_args.pdf,pdf_file,"output PDF maps filepath")
        geocode_col = check_cmd(c_args.address,geocode_col,"column name to geocode")
        iso2_col = check_cmd(c_args.iso,iso2_col,"ISO2 column (if any)")
        # Quietly add the Google Maps and Geonames keys
        gmaps_key = c_args.keygm or gmaps_key
        static_maps_key = c_args.keystatic or static_maps_key
        geonames_username = c_args.geonames or geonames_username
        # Determine whether or not maps will be made
        make_maps = not(c_args.nomaps)
        if not(make_maps):
            print("No vetting maps will be made for this geocoding run.")
    else:
        print("No command line arguments were passed - all default values will be used.")

    # Check if any program-specific Google Maps keys or Geonames usernames
    #  have been passed. If not, read some default values from a file.
    if np.any([i is None for i in [gmaps_key, static_maps_key, geonames_username]]):
        # Load the file containing API keys
        ## LOAD THE STATIC MAPS KEY
        with open(keys_file) as f:
            keys_dict = json.load(f)
        if gmaps_key is None:
            print("No Google Maps Geocoding API key has been provided;")
            print("A default API key will be read from file.")
            gmaps_key = str(randoneof(keys_dict['google_geocoding']))
        if static_maps_key is None:
            print("No Google Maps Static Maps API key has been provided;")
            print("A default API key will be read from file.")
            static_maps_key = str(randoneof(keys_dict['google_static_maps']))
        if geonames_username is None:
            print("No Geonames username has been provided;")
            print("A default API key will be read from file.")
            geonames_username = str(randoneof(keys_dict['geonames']))


    ######################################################################
    # CODE EXECUTES
    ######################################################################
    print("\n*********************************")
    print("***      BEGIN GEOCODING      ***")
    print("*********************************")
    print("Reading input file...")
    if in_file.lower().endswith('.csv'):
        df = pd.read_csv(in_file, encoding='latin1')
    else:
        df = pd.read_excel(in_file)
    print("Geocoding using Google Maps...")
    expanded = qf.gm_geocode_data_frame(df,
                                     api_key=gmaps_key,
                                     address_col=geocode_col,
                                     iso_2_col=iso2_col)
    print("Geocoding using OpenStreetMap...")
    expanded = qf.osm_geocode_data_frame(expanded,
                                      address_col=geocode_col)
    print("Geocoding using GeoNames...")
    expanded = qf.geonames_geocode_data_frame(expanded,
                                           address_col=geocode_col,
                                           iso_2_col=iso2_col,
                                           username=geonames_username)
    #print("Calculating likely points...")
    #expanded = qf.choose_best_points(df=expanded)

    print("Exporting output to Excel...")
    if out_file.lower().endswith('.csv'):
        expanded.to_csv(out_file, encoding='latin1', index=False)
    else:
        expanded.to_excel(out_file, index=False)
    print("Your output file is now ready to view at {} !".format(out_file))
    print("")

    # Make summary maps in 50-page chunks
    if make_maps:
        print("Making {} summary maps".format(expanded.shape[0]))
        def get_chunked_series(total_length, chunk_size=50):
            def get_chunk(row_num,chunk_size,total_length):
                low = (np.floor(1.0*row_num/chunk_size) * chunk_size) + 1
                high = np.min([(np.ceil(1.0*row_num/chunk_size) * chunk_size),
                               total_length])
                return "{}_to_{}".format(int(low),int(high))
            s = pd.Series(range(1,int(total_length) + 1))
            # Create chunks based on the row number
            chunked = s.apply(lambda x: get_chunk(x,chunk_size,total_length))
            return chunked
        expanded['mapping_chunk'] = get_chunked_series(total_length=expanded.shape[0])
        for chunk_name, chunked_df in expanded.groupby(by="mapping_chunk"):
            out_file_path_map = "{}_{}.pdf".format(pdf_file[:-4],chunk_name)
            qf.summary_maps(chunked_df,
                           address_col=geocode_col,
                           out_file_path=out_file_path_map,
                           gmaps_key=static_maps_key)
            print("  Maps {} completed.".format(chunk_name))
        print("\nYour summary maps are ready to view at {} !\n`".format(pdf_file[:-4]))

    print("GEOCODING COMPLETE")