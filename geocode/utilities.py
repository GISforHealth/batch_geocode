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


def get_geocoding_suffixes():
    """Store a list of suffixes that should be included in geocoding fields"""
    suffixes_list = ['name','type','lat','long','buffer']
    return suffixes_list