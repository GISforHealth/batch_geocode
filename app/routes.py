import json
import urllib
from flask import flash, render_template, request, Response, redirect
from app import app
from app.forms import GeocodeForm, VetLoadForm, VetSaveForm, VetFinalForm
from geocode import batch_geocode, vet_geocode, utilities
import time

@app.route('/')
@app.route('/index', methods=['GET','POST'])
def index():
    form = GeocodeForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            # Define the string of tools to use
            usetools = list()
            if form.use_gm.data: usetools.append('GM')
            if form.use_osm.data: usetools.append('OSM')
            if form.use_gn.data: usetools.append('GN')

            error = batch_geocode.geocode_from_flask(
                        infile=form.infile.data,
                        outfile=form.outfile.data, 
                        encoding=form.encoding.data, 
                        address=form.address.data,
                        iso=form.iso.data,
                        keygm=form.key.data, 
                        geonames=form.geonames.data,
                        usetools=usetools, 
                        resultspersource=form.resultsper.data, 
                        geo_buffer=form.geo_buffer.data
            )
            if(error is not None):
                flash(error, "error")
            else:
                flash(f"""Your output file for input file, {form.infile.data}, using 
                          tools {usetools}, with {form.resultsper.data} 
                          results per source, and a buffer of {form.geo_buffer.data} is 
                          now ready to view at {form.outfile.data}.""")
            return render_template('index.html', title='Home', form=form)
        else:
            flash('Need to enter all required fields')
    return render_template('index.html', title='Home', form=form)
    

@app.route('/vet', methods=['GET','POST'])
def vet():
    # Instantiate form to get input filepath
    load_form = VetLoadForm()
    save_form = VetSaveForm()
    final_form = VetFinalForm()
    # Instantiate an object that will be passed to the page definining 
    #  source types and source suffixes
    struct = utilities.get_geocoding_suffixes()

    # To do when the first (input data) form is submitted
    if load_form.validate_on_submit():
        # Load input data as JSON object and pass to application
        vetting_data = vet_geocode.VettingData(
            fp = load_form.infile.data, 
            encoding = load_form.encoding.data or 'detect', 
            address_col = load_form.address.data, 
            iso_col = load_form.iso.data or None
        )
        df_json = vetting_data.get_vetting_data_as_json()
        # Reload page, including new JSON data in the page
        return render_template('vet.html', title='Vetting', form=save_form, 
                               vet_json=df_json, show_map=1, result_struct=struct)

    # To do when the second (save vetted data) form is submitted
    if save_form.validate_on_submit():
        # TODO: Get the transformed JSON data from the page
        returned_json = urllib.parse.unquote(save_form.json_data.data)
        returned_data = utilities.json_to_dataframe(returned_json)

        save_filepath = save_form.outfile.data
        save_message = utilities.safe_save_vet_output(returned_data, save_filepath)
        # TODO: Save the transformed JSON data using the submitted filepath
        flash(save_message)
        if save_message == "Data saved successfully!":
            return render_template('vet.html', title='Vetting', form=final_form, 
                               vet_json=[], show_map=0, result_struct=[])
        else:
            return render_template('vet.html', title='Vetting', form=save_form, 
                               vet_json=[], show_map=0, result_struct=[])

    if final_form.validate_on_submit():
        return redirect('/index')
    # Start application for the first time
    return render_template('vet.html', title='Vetting', form=load_form, 
                           vet_json=[], show_map=0, result_struct=struct)
