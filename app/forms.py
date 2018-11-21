from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, IntegerField, FloatField
from wtforms.validators import DataRequired, Optional

class SubmitForm(FlaskForm):
	infile = StringField('Infile', validators=[DataRequired()])
	outfile = StringField('Outfile', validators=[DataRequired()])
	address = StringField('Address Field', validators=[DataRequired()])
	key = StringField('Google Maps Key', validators=[DataRequired()])
	geonames = StringField('Geonames Username', validators=[DataRequired()])
	iso = StringField('ISO2 Field', validators=[DataRequired()])
	usetools = StringField('Geocoders to Query')
	encoding = StringField('Encoding')
	resultsper = IntegerField('Results Per Source', validators=[Optional()])
	buffer = FloatField('Buffer Size', validators=[Optional()])
	submit = SubmitField('Geocode')
