from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_session import Session  # You may need to install this with pip
import firebase_admin
from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import credentials, firestore, auth
from dotenv import load_dotenv
import uuid
import json
import os

load_dotenv()

app = Flask(__name__)

app.secret_key = 'your_secret_key'  # Change this to a random secret key
app.config['SESSION_TYPE'] = 'filesystem'

Session(app)

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        try:
            user_record = auth.create_user(
                email=data['email'],
                password=data['password']
            )
            # Save additional user details to Firestore
            additional_user_info = {
                'name': data['name'],
                'registration_date': firestore.SERVER_TIMESTAMP
            }
            db.collection('users').document(user_record.uid).set(additional_user_info)
            log_activity(user_record.uid, 'User registration')
            # Redirect to home or another appropriate page after registration
            return redirect(url_for('home'))
        except firebase_exceptions.FirebaseError as e:
            # Handle the Firebase error appropriately
            return str(e), 400
    # Render the registration page if method is GET
    return render_template('register.html')

def log_activity(user_id, activity):
    log_data = {
        'user_id': user_id,
        'activity': activity,
        'date': firestore.SERVER_TIMESTAMP
    }
    db.collection('activity_logs').add(log_data)

@app.route('/register_manufacturer', methods=['POST'])
def register_manufacturer():
    data = request.form
    db.collection('manufacturers').add(data)
    log_activity(data['user_id'], 'Manufacturer registration')
    return 'Manufacturer registered'

@app.route('/add_product_form')
def add_product_form():
    # You might want to add a check here to make sure only authorized users can access this page
    return render_template('add_product_form.html')

import uuid

@app.route('/add_product', methods=['POST'])
def add_product():
    # Ensure this route is protected and only accessible by authorized users

    product_id = str(uuid.uuid4())  # Generate a unique product ID
    product_name = request.form['name']
    product_price = request.form['price']
    image_url = request.form['image_url']

    # Create a new product document
    new_product_data = {
        'id': product_id,
        'name': product_name,
        'price': float(product_price),
        'image_url': image_url
        # Add any other product details here
    }

    # Add the new product to the Firestore database
    db.collection('products').add(new_product_data)

    # Redirect to the products page, or wherever appropriate
    return redirect(url_for('shop'))


@app.route('/register_customer', methods=['GET', 'POST'])
def register_customer():
    if request.method == 'POST':
        data = request.form
        try:
            customer_info = {
                'name': data['name'],
                'email': data['email'],
                'address': data['address'],
                'registration_date': firestore.SERVER_TIMESTAMP,
                'cart': {}  # Initialize an empty cart
            }
            # Add the customer to the "customers" collection in Firestore
            db.collection('customers').add(customer_info)
            # Redirect to the shop page or customer dashboard after registration
            return redirect(url_for('shop'))
        except firebase_exceptions.FirebaseError as e:
            return str(e), 400
    return render_template('register_customer.html')

@app.route('/place_order', methods=['POST'])
def place_order():
    user_id = request.form.get('user_id')  # The ID of the user placing the order
    cart_items = json.loads(request.form.get('cart_items'))

    # Collect payment data, assuming you have form fields for payment details
    payment_data = {
        'amount': request.form.get('amount'),  # Total amount to be charged
        'payment_token': request.form.get('payment_token')  # Payment token from frontend
    }
    
    # Call process_payment with the payment data
    payment_successful = process_payment(payment_data)

    if payment_successful:
        try:
            # Create a new order in the 'orders' collection
            order_ref = db.collection('orders').add({
                'user_id': user_id,
                'status': 'paid',
                'order_date': firestore.SERVER_TIMESTAMP
            })

            # For each item in the cart, create a document in the 'order_details' collection
            for item in cart_items:
                db.collection('order_details').add({
                    'order_id': order_ref.id,
                    'product_id': item['product_id'],
                    'quantity': item['quantity'],
                    'price_each': item['price'],
                    # Add any other necessary item details
                })

            # Log the successful order placement activity
            log_activity(user_id, 'Order placed')
            
            # Redirect to a confirmation page or similar
            return redirect(url_for('order_confirmation', order_id=order_ref.id))
        except firebase_exceptions.FirebaseError as e:
            # Handle the Firebase error appropriately
            return str(e), 400
    else:
        # Handle failed payment attempt
        # Redirect to an error page or display a message
        return 'Payment failed', 400

@app.route('/order_confirmation/<order_id>')
def order_confirmation(order_id):
    # Fetch order details from Firestore to display to the user
    order = db.collection('orders').document(order_id).get()
    order_details = db.collection('order_details').where('order_id', '==', order_id).stream()

    # Render an order confirmation page with the order and order details
    return render_template('order_confirmation.html', order=order.to_dict(), order_details=[detail.to_dict() for detail in order_details])


# Updated process_payment function that takes payment_data as an argument
def process_payment(payment_data):
    # Here, you would handle the payment processing logic
    # For example, using payment_data['amount'] and payment_data['payment_token']
    # Since this is a placeholder, we'll simulate a successful payment
    return True  # Simulate a successful payment

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    product_id = request.form.get('product_id')
    quantity = int(request.form.get('quantity', 1))
    user_id = request.form.get('user_id')  # Assuming you have the user's ID

    # Fetch the customer's document and update their cart
    customer_ref = db.collection('customers').document(user_id)
    customer = customer_ref.get()
    if customer.exists:
        cart = customer.to_dict().get('cart', {})
        if product_id in cart:
            cart[product_id]['quantity'] += quantity
        else:
            cart[product_id] = {'quantity': quantity}
        customer_ref.update({'cart': cart})

    return redirect(url_for('show_cart'))

@app.route('/cart')
def show_cart():
    cart_items = session.get('cart', {})
    products = []

    for product_id, item in cart_items.items():
        if not product_id or product_id.strip() == '':
            continue  # Skip if product_id is empty or None

        print("Fetching product:", product_id)  # Debugging line

        product_ref = db.collection('products').document(product_id).get()
        if product_ref.exists:
            product = product_ref.to_dict()
            product['quantity'] = item['quantity']
            products.append(product)

    return render_template('cart.html', cart_items=products)


# Placeholder for blockchain interaction function
def create_smart_contract(order_details):
    # The logic to create and interact with the smart contract
    # ...
    # Log activity
    log_activity(order_details['user_id'], 'Smart contract created')
    # This is a placeholder, actual implementation will vary
    return True

if __name__ == '__main__':
    app.run(debug=True)
