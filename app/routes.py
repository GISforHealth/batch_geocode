from flask import render_template, request, flash, Response
from app import app
from app.forms import SubmitForm
from geocode import batch_geocode
import time

@app.route('/')
@app.route('/index', methods=['GET','POST'])
def index():
    form = SubmitForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            # Define the string of tools to use
            usetools = list()
            if form.use_gm.data: usetools.append('GM')
            if form.use_osm.data: usetools.append('OSM')
            if form.use_gn.data: usetools.append('GN')
            if form.use_fg.data: usetools.append('FG')

            batch_geocode.geocode_from_flask(
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
            flash(f"""Your output file for input file, {form.infile.data}, using 
                      tools {usetools}, with {form.resultsper.data} 
                      results per source, and a buffer of {form.geo_buffer.data} is 
                      now ready to view at {form.outfile.data}.""")
            return render_template('index.html', title='Home', form=form)
        else:
            flash('Need to enter all required fields')
    return render_template('index.html', title='Home', form=form)
    