#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 17 10:37:07 2017
@author: Nathaniel Henry, nathenry@uw.edu

This file defines the command line interface for the automated geocoding 
application, which allows the user to geocode many locations in succession using
the the Google Maps, OpenStreetMaps, and/or GeoNames. For more
information about how to use this tool, please see the repository README.

Written in Python 3.6
"""

import argparse
import numpy as np
import pandas as pd
from io import StringIO
from geocode import query_funcs
from geocode.utilities import read_to_pandas, write_pandas, get_geocoding_suffixes, validate_iso2, check_keys_for_tools, read_and_prep_input, prep_stringio_output, validate_columns
from tqdm import tqdm

def rearrange_fields(gc_df):
    """Rearrange the column order of a geocoded dataframe and drop unnecessary 
    fields."""
    cols = list(gc_df.columns)
    # Get all column prefixes (representing source types) and sort
    #  case-insensitive alphabetically.
    prefixes = sorted(
        list(set( [c[0:c.index('_')] for c in cols] )),
        key=lambda s: s.lower()
    )
    if 'best' not in prefixes:
        prefixes = ['best'] + prefixes
    # Keep only the following fields from the results of each geocoding tool
    suffixes = get_geocoding_suffixes()
    all_cols = [f'{p}_{s}' for p in prefixes for s in suffixes]
    return gc_df.reindex(labels=all_cols, axis='columns')


def geocode_from_flask(infile, keygm, geonames, iso, encoding, address,
                       usetools, resultspersource, geo_buffer):
        """Create a function that can be called from flask routes.py that wraps the
        whole batch_geocode process."""

        # Set all optional arguments to None if they are currently empty
        # This will cause `geocode_row()` to run using defaults
        usetools = usetools or None
        encoding = encoding or None
        resultspersource = resultspersource or None
        geo_buffer = geo_buffer or None

        key_error = check_keys_for_tools(keygm, geonames, usetools)
        if (key_error is not None):
            return(None, "Key Error: ", key_error)

        # Reading input file
        df, encoding, read_error = read_and_prep_input(infile, encoding)

        if (read_error is not None):
            return(None, "Infile Error: ", read_error)

        # Check that columns from web page are in dataset
        invalid_columns = validate_columns(df, iso, address)
        if(invalid_columns is not None):
            return(None, "Invalid column: ", f"{invalid_columns}. If you are sure the columns names are correct, the encoding may be wrong.")

        # Check for invalid iso2s in dataset
        valid_iso2 = validate_iso2(df[iso])
        if(valid_iso2 is not None):
            return(None, "The following iso2s provided were invalid: ", valid_iso2)

        # Initialize progress bar for pandas
        tqdm.pandas()

        try:
            # Geocode Rows of Data
            geocoded_cols = df.progress_apply(
                lambda row: query_funcs.geocode_row(
                    address=row[address], iso=row[iso],
                    gm_key=keygm, gn_key=geonames,
                    execute_names=usetools, results_per_app=resultspersource,
                    max_buffer=geo_buffer
                ),
                axis=1
            )
            geocoded_cols = rearrange_fields(geocoded_cols)
            df_with_geocoding = pd.concat([df, geocoded_cols], axis=1)            
        except Exception as e:
            return(None, "Geocoding Error: ", e)

        # Export Outfile
        io_output, io_e = prep_stringio_output(df_with_geocoding)
        if (io_e is not None):
            return(None, "Error prepping file download: ", io_e)

        return io_output, None, None


if __name__ == "__main__":
    """
    This section of the program will run from the command line or an 
    interactive prompt.
    """
    ######################################################################
    # SET UP AND READ COMMAND LINE ARGUMENTS, IF ANY
    ######################################################################

    print("\n*********************************")
    print("***      READ PARAMETERS      ***")
    print("*********************************")

    # Set up command-line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--infile", type=str,
                        help="The full filepath of the input Excel or CSV file")
    parser.add_argument("-o", "--outfile", type=str, 
                        help="The full filepath of the output Excel or CSV file")
    parser.add_argument("-a", "--address", type=str, default="for_geocoding",
                        help="The name of the address field to geocode")
    parser.add_argument("-s", "--iso", type=str, default=None,
                        help="The name of the file's ISO2 field (if any)")
    parser.add_argument("-e", "--encoding", type=str, default='detect',
                        help="Character encoding for the input file")
    parser.add_argument("-k", "--keygm", type=str, 
                        help="Activated Google Maps geocoding key")
    parser.add_argument("-g", "--geonames", type=str, 
                        help="Activated Geonames username")
    parser.add_argument(
        "-u", "--usetools", type=str, default='GM,OSM,GN', 
        help="""Comma-separated string listing geocoding web tools to query. 
             Valid items in this list include GM (Google Maps), OSM 
             (OpenStreetMap), and GN (GeoNames). Leaving this 
             argument blank will query all available tools as a default 
             UNLESS the Google Maps key and/or GeoNames username are blank. 
             Example valid arguments: '-u GN'; '-u GN,GM'; '-u OSM,GM'
             """
    )
    parser.add_argument(
        "-r", "--resultspersource", type=int, default=2,
        help="How many results should be returned from each web geocoding tool?"
    )
    parser.add_argument(
        "-b", "--buffer", type=float, default=15,
        help="""The maximum acceptable 'buffer size' (bounding box diagonal 
             distance) that a valid geocoded location can have, in kilometers. 
             The default is 15 km.
             """
    )

    # Parse command-line arguments
    c_args = parser.parse_args()
    # Get the web geocoding tools as a list rather than a comma-separated string
    execute_apps = [i.upper() for i in c_args.usetools.split(',')]

    ######################################################################
    # CODE EXECUTES
    ######################################################################
    print("\n*********************************")
    print("***      BEGIN GEOCODING      ***")
    print("*********************************")
    print("Reading input file...")
    df, encoding, errors = read_to_pandas(c_args.infile, c_args.encoding)

    if errors is not None:
        print("File loading failed: ")
        raise Exception(errors)

    print(f"Geocoding {df.shape[0]} rows of data...")
    # Initialize progress bar for pandas
    tqdm.pandas()
    # Geocode Rows of Data
    geocoded_cols = df.progress_apply(
        lambda row: query_funcs.geocode_row(
            address=row[c_args.address],
            iso=None if c_args.iso is None else row[c_args.iso],
            gm_key=c_args.keygm, gn_key=c_args.geonames,
            execute_names=execute_apps, results_per_app=c_args.resultspersource,
            max_buffer=c_args.buffer
        ),
        axis=1
    )
    geocoded_cols = rearrange_fields(geocoded_cols)
    df_with_geocoding = pd.concat([df, geocoded_cols], axis=1)

    print("\nExporting output to file...")
    write_pandas(df=df_with_geocoding, fp=c_args.outfile, encoding=encoding)

    print(f"Your output file is now ready to view at {c_args.outfile} !")
    print("\nGEOCODING COMPLETE")
