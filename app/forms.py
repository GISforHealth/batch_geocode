from flask_wtf import FlaskForm
from wtforms import BooleanField, FloatField, IntegerField, StringField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed

class GeocodeForm(FlaskForm):
    infile = FileField("Infile", validators = [FileRequired(),
        FileAllowed(['csv'], 
        "csv's only please!")])
    address = StringField(
        'Address Field (Required)', 
        validators=[DataRequired()], 
        default='address'
    )
    iso = StringField('ISO2 Field', default='iso2')
    key = StringField('Google Maps Key (<i>required if using GM</i>)')
    geonames = StringField('Geonames Username (<i>required if using GN</i>)')
    encoding = StringField('Encoding (Tries utf-8 and latin1 if "detect")', default='detect')
    resultsper = IntegerField('Results Per Source', default=2)
    geo_buffer = FloatField('Buffer Size', default=15)
    use_gm = BooleanField('Query Google Maps?')
    use_osm = BooleanField('Query OpenStreetMap?')
    use_gn = BooleanField('Query Geonames?')
    submit = SubmitField('Geocode')

class VetLoadForm(FlaskForm):
    infile = FileField('Geocoded file for vetting (<i>required</i>)', 
        validators = [FileRequired(),
        FileAllowed(['csv'], 
        "csv's only please!")])
    address = StringField(
        'Address Field (<i>required</i>)', 
        validators=[DataRequired()], 
        default='address'
    )
    iso = StringField('ISO2 Field', default='iso2')
    encoding = StringField('Encoding (Tries utf-8 and latin1 if "detect")', default='detect')
    submit = SubmitField('Load geocoded data')

class VetSaveForm(FlaskForm):
    json_data = HiddenField()
    submit = SubmitField('Download Results!')

class IndexFinalForm(FlaskForm):
    submit = SubmitField('Download Results!')

class InstructionForm(FlaskForm):
    filler = HiddenField()
