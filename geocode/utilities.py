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
from io import StringIO


def read_to_pandas(fp, encoding='detect'):
    """Read an input Excel or CSV file as a pandas DataFrame, testing a variety
    of encodings."""
    try:
        readfun = pd.read_csv
        if encoding != 'detect':
            # Try to read using the passed encoding
            try:
                df = readfun(fp, encoding=encoding)
                print(df)
                return (df, encoding, None)
            except Exception as e:
                print(f"The file {fp} could not be opened with encoding {encoding}.")
                print("Testing out all valid character encodings now...")
        # If the 
        test_encodings = ['utf-8','latin1'] + list(aliases.keys())
        valid_encoding = None
        for test_encoding in test_encodings:
            try:
                df = readfun(fp, encoding=test_encoding)
                valid_encoding = test_encoding
            except UnicodeDecodeError:
                pass
        if valid_encoding is None:
            return(None, None, UnicodeDecodeError(encoding='All standard encodings', reason='', 
                object=f'file {fp}', start=0, end=0))
        return (df, valid_encoding, None)
    except Exception as e:
        return(None, None, e)


def write_pandas(df, fp, encoding):
    """Write a pandas DataFrame to a CSV or Excel file using a known file
    encoding."""
    try:
        if fp.lower().endswith('.csv'):
            df.to_csv(fp, encoding=encoding, index=False)
        else:
            df.to_excel(fp, encoding=encoding, index=False)
        return None
    except Exception as e:
        return e


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
    """save vetting output as csv or xlsx, with some custom error messages"""
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


def validate_iso2(iso2_list):
    """check that the iso2 values passed in for geocoding are valid"""
    valid_iso2_set = ["AF", "AX", "AL", "DZ", "AS", "AD", "AO", "AI", "AQ", "AG", 
        "AR", "AM", "AW", "AU", "AT", "AZ", "BH", "BS", "BD", "BB", "BY", "BE", "BZ",
        "BJ", "BM", "BT", "BO", "BQ", "BA", "BW", "BV", "BR", "IO", "BN", "BG", "BF",
        "BI", "KH", "CM", "CA", "CV", "KY", "CF", "TD", "CL", "CN", "CX", "CC", "CO", 
        "KM", "CG", "CD", "CK", "CR", "CI", "HR", "CU", "CW", "CY", "CZ", "DK", "DJ", 
        "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "ET", "FK", "FO", "FJ", "FI", 
        "FR", "GF", "PF", "TF", "GA", "GM", "GE", "DE", "GH", "GI", "GR", "GL", "GD", 
        "GP", "GU", "GT", "GG", "GN", "GW", "GY", "HT", "HM", "VA", "HN", "HK", "HU", 
        "IS", "IN", "ID", "IR", "IQ", "IE", "IM", "IL", "IT", "JM", "JP", "JE", "JO", 
        "KZ", "KE", "KI", "KP", "KR", "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", 
        "LI", "LT", "LU", "MO", "MK", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MQ", 
        "MR", "MU", "YT", "MX", "FM", "MD", "MC", "MN", "ME", "MS", "MA", "MZ", "MM", 
        "NA", "NR", "NP", "NL", "NC", "NZ", "NI", "NE", "NG", "NU", "NF", "MP", "NO", 
        "OM", "PK", "PW", "PS", "PA", "PG", "PY", "PE", "PH", "PN", "PL", "PT", "PR", 
        "QA", "RE", "RO", "RU", "RW", "BL", "SH", "KN", "LC", "MF", "PM", "VC", "WS", 
        "SM", "ST", "SA", "SN", "RS", "SC", "SL", "SG", "SX", "SK", "SI", "SB", "SO", 
        "ZA", "GS", "SS", "ES", "LK", "SD", "SR", "SJ", "SZ", "SE", "CH", "SY", "TW", 
        "TJ", "TZ", "TH", "TL", "TG", "TK", "TO", "TT", "TN", "TR", "TM", "TC", "TV", 
        "UG", "UA", "AE", "GB", "US", "UM", "UY", "UZ", "VU", "VE", "VN", "VG", "VI", 
        "WF", "EH", "YE", "ZM", "ZW"]
    iso2_set = [element.upper() for element in list(iso2_list.unique())]
    valid_iso2 = all(x in valid_iso2_set for x in iso2_set)

    if valid_iso2:
        return None
    else:
        bad_iso2s = [item for item in iso2_set if item not in valid_iso2_set]
        if(len(bad_iso2s) > 1):
            bad_iso2s = ", ".join(bad_iso2s)
        else:
            bad_iso2s = bad_iso2s[0]
        return bad_iso2s


def check_keys_for_tools(keygm, geonames, usetools):
    """Check to ensure that a key has been entered for Google maps, and a username has been entered for geonames """
    if("GM" in usetools):
        if(keygm == ""):
            return "Google Maps has been specified as a service, a Google Maps key must be provided."
    if("GN" in usetools):
        if(geonames == ""):
            return "Geonames has been specified as a service, a Geonames username must be provided."


def read_and_prep_input(f, encoding) :
    if encoding == 'detect':
        encoding = 'latin-1'
    f.seek(0)
    csv_file = f.read().decode(encoding)
    csv_file = StringIO(csv_file)

    df, encoding, read_error = read_to_pandas(csv_file, encoding)
    return df, encoding, read_error


def prep_stringio_output(df):
    try:
        string_buffer = StringIO()
        df.to_csv(string_buffer, index=False)
        return string_buffer, None
    except Exception as e:
        return None, e