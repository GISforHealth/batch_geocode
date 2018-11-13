#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Fri Mar 17 10:37:07 2017
@author: Nathaniel Henry, nathenry@uw.edu

This file defines the command line interface for the automated geocoding 
application, which allows the user to geocode many locations in succession using
the the Google Maps, OpenStreetMaps, GeoNames, and/or FuzzyG APIs. For more
information about how to use this tool, please see the repository README.

Written in Python 3.6
"""

import argparse
import numpy as np
import pandas as pd
from encodings.aliases import aliases
from geocode import query_funcs


def read_to_pandas(fp):
    """Read an input Excel or CSV file as a pandas DataFrame, testing a variety
    of encodings."""
    readfun = pd.read_csv if fp.lower().endswith('.csv') else pd.read_excel
    test_encodings = ['utf-8','latin1'] + list(aliases.keys())
    valid_encoding = None
    for encoding in test_encodings:
        try:
            df = readfun(fp, encoding=encoding)
            valid_encoding = encoding
            break
        except UnicodeDecodeError:
            pass
    if valid_encoding is None:
        raise UnicodeDecodeError(encoding='All standard encodings', reason='', 
                                 object=f'file {fp}', start=0, end=0)
    return (df, encoding)


def write_pandas(df, fp, encoding):
    """Write a pandas DataFrame to a CSV or Excel file using a known file
    encoding."""
    if fp.lower().endswith('.csv'):
        df.to_csv(fp, encoding=encoding, index=False)
    else:
        df.to_excel(fp, encoding=encoding, index=False)
    return None



def rearrange_fields(gc_df):
    """Rearrange the column order of a geocoded dataframe and drop unnecessary 
    fields."""
    cols = list(gc_df.columns)
    prefixes = sorted(
        list(set( [c[0:c.index('_')] for c in cols] )),
        key=lambda s: s.lower()
    )
    if 'best' not in prefixes:
        prefixes = ['best'] + prefixes
    # Keep only the following fields from the results of each geocoding tool
    suffixes = ['name','type','long','lat','buffer']
    all_cols = [f'{p}_{s}' for p in prefixes for s in suffixes]
    return gc_df.reindex(labels=all_cols, axis='columns')



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
    parser.add_argument("-s", "--iso", type=str,
                        help="The name of the file's ISO2 field (if any)")
    parser.add_argument("-k", "--keygm", type=str, 
                        help="Activated Google Maps geocoding key")
    parser.add_argument("-g", "--geonames", type=str, 
                        help="Activated Geonames username")
    parser.add_argument(
        "-u", "--usetools", type=str, default='GM,OSM,GN,FG', 
        help="""Comma-separated string listing geocoding web tools to query. 
             Valid items in this list include GM (Google Maps), OSM 
             (OpenStreetMap), GN (GeoNames), and FG (FuzzyG). Leaving this 
             argument blank will query all available tools as a default 
             UNLESS the Google Maps key and/or GeoNames username are blank. 
             Example valid arguments: '-u GN'; '-u GN,GM,FG'; '-u OSM,GM,FG'
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
    df, encoding = read_to_pandas(c_args.infile)

    print(f"Geocoding {df.shape[0]} rows of data...")
    geocoded_cols = df.apply(
        lambda row: query_funcs.geocode_row(
            address=row[c_args.address], iso=row[c_args.iso],
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
