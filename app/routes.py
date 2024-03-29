import json
import urllib
from flask import flash, render_template, request, Response, redirect, send_file, session
from app import app
from app.forms import GeocodeForm, VetLoadForm, VetSaveForm, IndexFinalForm, InstructionForm
from geocode import batch_geocode, vet_geocode, utilities
import time
import datetime
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from io import StringIO, BytesIO
import uuid
import collections

# Holds the output data going from index to index_end, by user_id key
# This is necessary to avoid global overwriting with concurrent usage
geocoding_user_variable_buffer = collections.deque(maxlen=20)

@app.route('/instructions')
def instructions():
    form = InstructionForm()
    return render_template('instructions.html', title='Instructions', form=form)

@app.route('/')
@app.route('/index', methods=['GET','POST'])
def index():
    form = GeocodeForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            
            # Define a user id to identify the download csv in the global deque
            user_id = uuid.uuid4()
            session['user_id_geocode'] = user_id

            # Define the string of tools to use
            usetools = list()
            if form.use_gm.data: usetools.append('GM')
            if form.use_osm.data: usetools.append('OSM')
            if form.use_gn.data: usetools.append('GN')

            # Main function which runs the entire geocoding process
            geocoded_data, error_type, error = batch_geocode.geocode_from_flask(
                                                    infile=form.infile.data, 
                                                    encoding=form.encoding.data, 
                                                    address=form.address.data,
                                                    iso=form.iso.data,
                                                    keygm=form.key.data, 
                                                    geonames=form.geonames.data,
                                                    usetools=usetools, 
                                                    resultspersource=form.resultsper.data, 
                                                    geo_buffer=form.geo_buffer.data
            )

            # Add geocoded data to global deque so it is accessible from end page
            geocoding_user_variable_buffer.append((user_id, geocoded_data))
            if(error is not None):
                flash(error_type + str(error), 'error')
            else:
                return render_template('index_end.html', title='Home', form=form)
        else:
            flash('Need to enter all required fields')
    return render_template('index.html', title='Home', form=form)
    
@app.route('/index_end', methods=['GET','POST'])
def index_end():
    form = IndexFinalForm()
    back_form = GeocodeForm()
    if form.validate_on_submit():
        # Pull data from the global deque for download
        user_id = session['user_id_geocode']
        file_to_download = None
        if user_id is None:
            flash('No data found for download, please try reuploading', 'error')
            return render_template('index.html', title='Home', form=back_form)
        for file in geocoding_user_variable_buffer:
            if file[0] == user_id:
                file_to_download = file[1]
        if file_to_download is None:
            flash('No data returned from geocoding, please try reuploading', 'error')
            return render_template('index.html', title='Home', form=back_form)
        download_IO = BytesIO(file_to_download.getvalue().encode('utf-8'))

        current_date = datetime.datetime.now()
        file_out_name = "geocode_results_" + str(current_date.strftime("%Y")) + "_" + str(current_date.strftime("%m")) + "_" + str(current_date.strftime("%d")) + ".csv"
        return send_file(download_IO, download_name=file_out_name, as_attachment=True)

@app.route('/vet', methods=['GET','POST'])
def vet():
    # Instantiate form to get input filepath
    load_form = VetLoadForm()
    save_form = VetSaveForm()
    # Instantiate an object that will be passed to the page definining source types and source suffixes
    struct = utilities.get_geocoding_suffixes()

    # To do when the first (input data) form is submitted
    if load_form.validate_on_submit():
        # Load input data as JSON object and pass to application
        try:    
            vetting_data = vet_geocode.VettingData(
                fp = load_form.infile.data, 
                encoding = load_form.encoding.data or 'detect', 
                address_col = load_form.address.data, 
                iso_col = load_form.iso.data
            )
        except Exception as loading_error:
            flash("Infile Loading Error: " + str(loading_error), 'error')
            return render_template('vet.html', title='Vetting', form=load_form, 
                                   vet_json=[], show_map=0, result_struct=struct)

        # loading happens inside the constructor call for vet_geocode, so issues with loading the data (which uses a function shared with index)
        # there is separate error checking that happens here
        if(vetting_data.get_error() is not None):
            flash("Infile Loading Error: " + str(vetting_data.get_error()), 'error')
            return render_template('vet.html', title='Vetting', form=load_form, 
                                   vet_json=[], show_map=0, result_struct=struct)

        df_json = vetting_data.get_vetting_data_as_json()

        # Reload page, including new JSON data in the page
        return render_template('vet.html', title='Vetting', form=save_form, 
                               vet_json=df_json, show_map=1, result_struct=struct)

    # To do when the second (save vetted data) form is submitted
    if save_form.validate_on_submit():
        # Get the transformed JSON data from the page
        returned_json = urllib.parse.unquote(save_form.json_data.data)
        returned_data = utilities.json_to_dataframe(returned_json)

        # Prepare data for download through browser 
        io_output, io_e = utilities.prep_stringio_output(returned_data)
        if (io_e is not None):
            flash(io_e)
            return render_template('vet.html', title='Vetting', form=save_form, 
                               vet_json=[], show_map=0, result_struct=[])

        download_IO = BytesIO(io_output.getvalue().encode('utf-8'))
        current_date = datetime.datetime.now()
        file_out_name = "vetting_results_" + str(current_date.strftime("%Y")) + "_" + str(current_date.strftime("%m")) + "_" + str(current_date.strftime("%d")) + ".csv"
        return send_file(download_IO, download_name=file_out_name, as_attachment=True)

    # Start application for the first time
    return render_template('vet.html', title='Vetting', form=load_form, 
                           vet_json=[], show_map=0, result_struct=struct)
