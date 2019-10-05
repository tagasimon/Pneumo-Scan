# -*- coding: utf-8 -*-
from __future__ import division, print_function
from scripts import tabledef
from scripts import forms
from scripts import helpers
from flask import Flask, redirect, url_for, render_template, request, session
import json
import sys
import os

## More Imports
import numpy as np ## Numpy
import cv2 ## Open CV

import os ##Operating System 
import glob ## Global
from flask_dropzone import Dropzone  ## Flask Dropzone

# Keras
from keras.applications.imagenet_utils import preprocess_input, decode_predictions
from keras.models import load_model
from keras.preprocessing import image

# Model saved with Keras model.save()
MODEL_PATH = 'models/new_model.h5'

# Load your trained model
model = load_model(MODEL_PATH)
model._make_predict_function()  # Necessary
print('Model loaded. Start serving...')

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.secret_key = os.urandom(12)  # Generic key for dev purposes only
app.config.update(
    UPLOADED_PATH=os.path.join(basedir, 'static/uploads'),
    # Flask-Dropzone config:
    DROPZONE_ALLOWED_FILE_TYPE='image',
    DROPZONE_MAX_FILE_SIZE=3,
    DROPZONE_MAX_FILES=10,
    DROPZONE_IN_FORM=True,
    DROPZONE_UPLOAD_ON_CLICK=True,
    DROPZONE_UPLOAD_ACTION='handle_upload',  # URL or endpoint
    DROPZONE_UPLOAD_BTN_ID='submit',
)

dropzone = Dropzone(app)


# Heroku
#from flask_heroku import Heroku
#heroku = Heroku(app)

# ======== Routing =========================================================== #
# -------- Login ------------------------------------------------------------- #
@app.route('/', methods=['GET', 'POST'])
def login():
    if not session.get('logged_in'):
        form = forms.LoginForm(request.form)
        if request.method == 'POST':
            username = request.form['username'].lower()
            password = request.form['password']
            if form.validate():
                if helpers.credentials_valid(username, password):
                    session['logged_in'] = True
                    session['username'] = username
                    return json.dumps({'status': 'Login successful'})
                return json.dumps({'status': 'Invalid user/pass'})
            return json.dumps({'status': 'Both fields required'})
        return render_template('login.html', form=form)
    user = helpers.get_user()
    return render_template('home.html', user=user)


@app.route("/logout")
def logout():
    session['logged_in'] = False
    return redirect(url_for('login'))


# -------- Signup ---------------------------------------------------------- #
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if not session.get('logged_in'):
        form = forms.LoginForm(request.form)
        if request.method == 'POST':
            username = request.form['username'].lower()
            password = helpers.hash_password(request.form['password'])
            email = request.form['email']
            if form.validate():
                if not helpers.username_taken(username):
                    helpers.add_user(username, password, email)
                    session['logged_in'] = True
                    session['username'] = username
                    return json.dumps({'status': 'Signup successful'})
                return json.dumps({'status': 'Username taken'})
            return json.dumps({'status': 'User/Pass required'})
        return render_template('login.html', form=form)
    return redirect(url_for('login'))


# -------- Settings ---------------------------------------------------------- #
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get('logged_in'):
        if request.method == 'POST':
            password = request.form['password']
            if password != "":
                password = helpers.hash_password(password)
            email = request.form['email']
            helpers.change_user(password=password, email=email)
            return json.dumps({'status': 'Saved'})
        user = helpers.get_user()
        return render_template('settings.html', user=user)
    return redirect(url_for('login'))


@app.route('/upload', methods=['POST'])
def handle_upload():
    ### NEW UPLOADS
    for key, f in request.files.items():
        if key.startswith('file'):
            f.save(os.path.join(app.config['UPLOADED_PATH'], f.filename))
    return '', 204

@app.route('/form', methods=['POST'])
def handle_form():
    # title = request.form.get('title')
    # description = request.form.get('description')

    filenames = [img for img in glob.glob("static/uploads/*.jpeg")]

    final_results = {}
    for img in filenames:
        # Make prediction
        preds = predict(img, model)
        # Process your result for human
        pred_class = np.argmax(preds)  # Simple argmax
        if pred_class == 1:
            result = " PNEUMONIA + "
        else:
            result = " NORMAL "
        final_results[img] = result

    ##############################################################
    #####    HANDLE PAYMENTS HERE BEFORE SHOWING RESULTS    ######
    ##############################################################

    return render_template("results.html", results=final_results)

### This is the predict method
def predict(img, model):
    img = cv2.imread(img)
    img = cv2.resize(img, (224, 224))
    x = np.reshape(img, [224, 224, 3])
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    preds = model.predict(x)
    return preds[0]



# ======== Main ============================================================== #
if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
