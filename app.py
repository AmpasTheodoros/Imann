from flask import Flask, render_template
import firebase_admin
from firebase_admin import credentials, db

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

# Use the application default credentials
cred = credentials.Certificate(os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON'))
firebase_admin.initialize_app(cred)

db = firestore.client()


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/shop')
def shop():
    products_ref = db.collection('products')
    products = products_ref.stream()
    products_list = [product.to_dict() for product in products]
    return render_template('products.html', products=products_list)

if __name__ == '__main__':
    app.run(debug=True)
