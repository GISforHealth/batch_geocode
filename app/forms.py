from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional

class GeocodeForm(FlaskForm):
    infile = StringField('Infile (<i>required</i>)', validators=[DataRequired()])
    outfile = StringField('Outfile (<i>required</i>)', validators=[DataRequired()])
    address = StringField(
        'Address Field (Required)', 
        validators=[DataRequired()], 
        default='address'
    )
    iso = StringField('ISO2 Field', default='iso2')
    key = StringField('Google Maps Key (<i>required if using GM</i>)')
    geonames = StringField('Geonames Username (<i>required if using GN</i>)')
    encoding = StringField('Encoding', default='detect')
    resultsper = IntegerField('Results Per Source', default=2)
    geo_buffer = FloatField('Buffer Size', default=15)
    use_gm = BooleanField('Query Google Maps?')
    use_osm = BooleanField('Query OpenStreetMap?')
    use_gn = BooleanField('Query Geonames?')
    submit = SubmitField('Geocode')

class VetLoadForm(FlaskForm):
    infile = StringField(
        'Geocoded file for vetting (<i>required</i>)', 
        validators=[DataRequired()]
    )
    address = StringField(
        'Address Field (<i>required</i>)', 
        validators=[DataRequired()], 
        default='address'
    )
    iso = StringField('ISO2 Field', default='iso2')
    encoding = StringField('Encoding', default='detect')
    submit = SubmitField('Load geocoded data')

class VetSaveForm(FlaskForm):
    outfile = StringField(
        'Save file to path (<i>required</i>)', 
        validators=[DataRequired()]
    )
    json_data = HiddenField()
    submit = SubmitField('Save vetted data')

class VetFinalForm(FlaskForm):
    submit = SubmitField('Return to Start')

