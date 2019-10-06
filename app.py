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
import paypalrestsdk as paypal
from paypalrestsdk import *
paypal.configure({
    "mode": "sandbox",  # sandbox or live
    "client_id": "AaVMBALfH-QL4gp-dVs7He0cM6dnZX2uRqsm7fJR337f1j630XZ2_mtJOA8MSxpVQU0tGuNQ4JoieUYw",
    "client_secret": "EAYonfnZoVAMhtaw59b2-y1Ljv7z1BbmFSgzATurQtkmj-bBerU0ljBt5lg63iWOqg_deYoXQu4CtgKd"})

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
final_results = {}
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
    return render_template("results.html", results=final_results, success=False)

### This is the predict method
def predict(img, model):
    img = cv2.imread(img)
    img = cv2.resize(img, (224, 224))
    x = np.reshape(img, [224, 224, 3])
    x = np.expand_dims(x, axis=0)
    x = preprocess_input(x)
    preds = model.predict(x)
    return preds[0]

@app.route('/paypal_Return', methods=['GET'])
def paypal_Return():
    # ID of the payment. This ID is provided when creating payment.
    paymentId = request.args['paymentId']
    payer_id = request.args['PayerID']
    payment = paypal.Payment.find(paymentId)

    # PayerID is required to approve the payment.
    if payment.execute({"payer_id": payer_id}):  # return True or False
        print("Payment[%s] execute successfully" % (payment.id))
        #return 'Payment execute successfully!' + payment.id
        return render_template("results.html", results=final_results, success=True)
    else:
        print(payment.error)
        return 'Payment execute ERROR!'


@app.route('/paypal_payment', methods=['GET'])
def paypal_payment():
    # Payment
    # A Payment Resource; create one using
    # the above types and intent as 'sale'
    payment = paypal.Payment({
        "intent": "sale",

        # Payer
        # A resource representing a Payer that funds a payment
        # Payment Method as 'paypal'
        "payer": {
            "payment_method": "paypal"},

        # Redirect URLs
        "redirect_urls": {
            "return_url": "http://127.0.0.1:5000/paypal_Return?success=true",
            "cancel_url": "http://127.0.0.1:5000/paypal_Return?cancel=true"},

        # Transaction
        # A transaction defines the contract of a
        # payment - what is the payment for and who
        # is fulfilling it.
        "transactions": [{

            # ItemList
            "item_list": {
                "items": [{
                    "name": "Pneumonia Prediction",
                    "sku": "item",
                    "price": "5.00",
                    "currency": "USD",
                    "quantity": 1}]},

            # Amount
            # Let's you specify a payment amount.
            "amount": {
                "total": "5.0",
                "currency": "USD"},
            "description": "This amount is charged for every Predictions on the Site"}]})

    # Create Payment and return status
    if payment.create():
        print("Payment[%s] created successfully" % (payment.id))
        # Redirect the user to given approval url
        for link in payment.links:
            if link.method == "REDIRECT":
                # Convert to str to avoid google appengine unicode issue
                # https://github.com/paypal/rest-api-sdk-python/pull/58
                redirect_url = str(link.href)
                print("Redirect for approval: %s" % (redirect_url))
                return redirect(redirect_url)
    else:
        print("Error while creating payment:")
        print(payment.error)
        return "Error while creating payment"


# ======== Main ============================================================== #
if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)
