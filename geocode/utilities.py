#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on Mon 12 Dec 2018
@author: Nathaniel Henry, nathenry@uw.edu

This file defines common utilies for file I/O in Pandas

Written in Python 3.6
"""
import numpy as np
import pandas as pd
from encodings.aliases import aliases
import json
import re
import csv
import os


def read_to_pandas(fp, encoding='detect'):
    """Read an input Excel or CSV file as a pandas DataFrame, testing a variety
    of encodings."""
    readfun = pd.read_csv if fp.lower().endswith('.csv') else pd.read_excel
    if encoding != 'detect':
        # Try to read using the passed encoding
        try:
            df = readfun(fp, encoding=encoding)
            return (df, encoding)
        except UnicodeDecodeError:
            print(f"The file {fp} could not be opened with encoding {encoding}.")
            print("Testing out all valid character encodings now...")
    # If the 
    test_encodings = ['utf-8','latin1'] + list(aliases.keys())
    valid_encoding = None
    for test_encoding in test_encodings:
        try:
            df = readfun(fp, encoding=test_encoding)
            valid_encoding = test_encoding
            break
        except UnicodeDecodeError:
            pass
    if valid_encoding is None:
        raise UnicodeDecodeError(encoding='All standard encodings', reason='', 
                                 object=f'file {fp}', start=0, end=0)
    return (df, valid_encoding)


def write_pandas(df, fp, encoding):
    """Write a pandas DataFrame to a CSV or Excel file using a known file
    encoding."""
    if fp.lower().endswith('.csv'):
        df.to_csv(fp, encoding=encoding, index=False)
    else:
        df.to_excel(fp, encoding=encoding, index=False)
    return None


def get_geocoding_sources():
    '''Store a list of geocoding source types and related prefixes'''
    sources = {
        'Google Maps':'GM','OpenStreetMaps':'OSM','GeoNames':'GN','FuzzyG':'FG'
    }
    return sources


def get_geocoding_suffixes():
    """Store a list of suffixes that should be included in geocoding fields"""
    suffixes_list = ['name','type','lat','long','buffer']
    return suffixes_list


def json_to_dataframe(json_data):
    """Get the json passed from vet save form and process into excel-saveable format"""
    null = None
    json_data = eval(json_data)
    keys = json_data.keys()
    column_names = list(json_data[list(keys)[0]].keys())
    column_names.insert(0, "address")
    del column_names[-1]

    csv_list = list()
    for key in keys:
        row_list = list(json_data[key].values())
        row_list.insert(0, key)
        del row_list[-1]
        row_list[0] = re.sub('\d: ','', row_list[0])
        csv_list.append(row_list)

    df = pd.DataFrame(csv_list, columns=column_names)
    return(df)

def safe_save_vet_output(df, filepath):
    if(os.path.exists(os.path.dirname(filepath))):
        try:
            if filepath.lower().endswith('.csv'):
                df.to_csv(filepath, index=False)
            elif filepath.lower().endswith('.xlsx'):
                df.to_excel(filepath, index=False)
            else:
                return("Filepath must end in .csv or .xlsx")
            return("Data saved successfully!")
        except:
            return("File failed to save - RIP everything")
    else:
         return("specified directory does not exist")