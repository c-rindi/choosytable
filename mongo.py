from flask import Flask, redirect, url_for, session, render_template, request, jsonify, g
from flask_pymongo import PyMongo, ObjectId
from bson import json_util
from datetime import datetime
import os
from flask_dance.contrib.google import make_google_blueprint, google
from flask_paginate import Pagination, get_page_parameter
from flask_navigation import Navigation
import statistics 

app = Flask(__name__)
app.config['MONGO_DBNAME'] = 'restdb'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/restdb'
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get("GOOGLE_CLIENT_ID")
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get(
    "GOOGLE_CLIENT_SECRET")
blueprint = make_google_blueprint(scope=["profile", "email"])
app.register_blueprint(blueprint, url_prefix="/login")

mongo = PyMongo(app)
star = mongo.db.stars
db = mongo.db
nav = Navigation(app)

nav.Bar('top', [
    nav.Item('Home', 'person'),
    nav.Item('Companies', 'company'),
    nav.Item('People', 'person'),
    nav.Item('Logout', 'logout'),
])

colors = [
    "#F7464A", "#46BFBD", "#FDB45C", "#FEDCBA",
    "#ABCDEF", "#DDDDDD", "#ABCABC", "#4169E1",
    "#C71585", "#FF4500", "#FEDCBA", "#46BFBD"]

labels = ['1 Star','2 Stars','3 Stars','4 Stars','5 Stars']


@app.before_request
def before_request():
    if not google.authorized and "google" not in request.path:
        return render_template("index.html")
    else:
        session['resp'] = google.get("/oauth2/v1/userinfo").json()


@app.route("/")
@app.route("/home")
@app.route("/index")
@app.route("/welcome")
def home():
    e = ['Black', 'Afro-Latino', 'Bahamian', 'Jamaican', 'African']
    x = star.find_one({'email': session['resp']['email']})
    r = star.find(
      {
        "$and": [
          {'creator': x['name']}, 
          {'reviews': {"$exists": True}}
        ]
      })
    if r is not None:
        search = False
        q = request.args.get('q')
        if q:
            search = True
        page = request.args.get(get_page_parameter(), type=int, default=1)
        pagination = Pagination(
            page=page, total=r.count(), search=search, record_name='Your latest reviews')
        return render_template(
            'person.html',
            x=x,
            r=r,
            e=e,
            pagination=pagination)
    else:
        return render_template(
            'person.html',
            email=session['resp']['email'],
            name=session['resp']['name'],
            e=e)


@app.route('/company', methods=['GET', 'POST', 'PUT'])
def company():
    if request.method == 'GET':
        search = False
        q = request.args.get('q')
        if q:
            search = True
        page = request.args.get(get_page_parameter(), type=int, default=1)
        companies = star.find({'reviews': {"$exists": True}})
        pagination = Pagination(
            page=page, total=companies.count(), search=search, record_name='companies')
        return render_template('company.html', companies=companies, pagination=pagination)
    elif request.method in ('POST', 'PUT'):
        try:
            star.insert(
                {
                    'created': datetime.now(),
                    'company': request.form['company'],
                    'creator': session['resp']['name'],
                    'reviews': [
                        {
                            'review': request.form['reviews'],
                            'rating':request.form['rating']
                        }
                    ]
                }
            )
            return redirect(request.url)
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route('/company/<company_id>', methods=['GET', 'POST', 'PUT'])
def single_company(company_id):
    if request.method == 'GET':
        search = False
        q = request.args.get('q')
        if q:
            search = True
        page = request.args.get(get_page_parameter(), type=int, default=1)
        singlecompany = star.find_one({'_id': ObjectId(company_id)})
        data=[]
        for i in range(len(singlecompany['reviews'])):
            data.append(singlecompany['reviews'][i]['rating'])
        data.sort()
        l=[0,0,0,0,0]
        for j in range(len(data)):
            if data[j]=="1":
                l[0]+=1
            elif data[j]=="2":
                l[1]+=1
            elif data[j]=="3":
                l[2]+=1
            elif data[j]=="4":
                l[3]+=1
            elif data[j]=="5":
                l[4]+=1
        values=[]
        for k in range(len(l)):
            values.append(format(l[k]/len(data), '.3f'))
        pagination = Pagination(page=page, total=len(list(
            singlecompany['reviews'])), search=search, record_name=singlecompany['company'])
        return render_template('singlecompany.html', singlecompany=singlecompany, pagination=pagination, set=zip(values,labels,colors))
    elif request.method in ('POST', 'PUT'):
        try:
            star.update_one(
                {'_id': ObjectId(company_id)},
                {
                    '$push':
                    {'reviews':
                        {
                            'review': request.form['reviews'],
                            'rating': request.form['rating']
                        }
                     },
                    '$set': {'last_modified': datetime.now()}
                },
                upsert=True
            )
            return redirect(request.url)
        except Exception as e:
            return jsonify({'error': str(e)})
    else:
        return jsonify({'error': 'company not found'})


@app.route('/person/<person_id>', methods=['GET', 'PUT', 'POST'])
def single_person(person_id):
    if request.method == 'GET':
        try:
            return json_util.dumps(star.find_one({'_id': ObjectId(person_id)}))
        except:
            return jsonify({'error': 'person not found'})
    elif request.method in ('POST', 'PUT'):
        try:
            star.update(
                {'_id': ObjectId(person_id)},
                {
                    '$set': {
                        'name': request.form['name'],
                        'ethnicity': request.form['ethnicity'],
                        "last_modified": datetime.now()}
                }
            )
            return redirect(request.url)
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route('/person', methods=['GET', 'POST', 'PUT'])
def person():
    if request.method == 'GET':
        if request.args:
            return json_util.dumps(star.find({"$and": [{'name': request.args.get("name", "")}, {'email': {"$exists": True}}]}))
        else:
            return json_util.dumps(star.find({'email': {"$exists": True}}))
    elif request.method in ('POST', 'PUT'):
        try:
            star.insert({'created': datetime.now(), 'name': session['resp']['name'], 'email': session['resp']['email'], 'ethnicity': request.form['ethnicity']})
            return redirect(request.url)
        except Exception as e:
            return jsonify({'error': str(e)})


@app.route("/logout")
def logout():
    session.clear()
    return render_template('bye.html')


if __name__ == '__main__':
    app.run(debug=True)
