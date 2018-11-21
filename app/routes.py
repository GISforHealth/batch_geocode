from flask import render_template, request, flash
from app import app
from app.forms import SubmitForm
from geocode import batch_geocode

@app.route('/')
@app.route('/index', methods=['GET','POST'])
def index():
	form = SubmitForm()
	if request.method == 'POST':
		if form.validate_on_submit():
			infile = request.form['infile']
			outfile = request.form['outfile']
			address = request.form['address']
			iso = request.form['iso']
			key = request.form['key']
			geonames = request.form['geonames']
			usetools = request.form['usetools']
			encoding = request.form['encoding']
			resultsper = request.form['resultsper']
			buffer = request.form['buffer']
			batch_geocode.geocode_from_flask(infile=infile, iso=iso, outfile=outfile, keygm=key, geonames=geonames,
											 address=address, usetools=usetools, encoding=encoding,
											 resultspersource=resultsper, buffer=buffer)
			flash('Your output file for input file, {}, usingtools {}, with {} results per source, and a buffer of {} '
				  'is now ready to view at {}'.format(form.infile.data, form.usetools.data, form.resultsper.data,
														form.buffer.data, form.outfile.data))
			return render_template('index.html', title='Home', form=form)
		else:
			flash('Need to enter all required fields')
	return render_template('index.html', title='Home', form=form)

