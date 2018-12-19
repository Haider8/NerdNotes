# app.py


from flask import Flask, render_template, flash, redirect, url_for, session, logging, request
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps

app = Flask(__name__)
app.secret_key = 'secretkey'

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'mypassword'
app.config['MYSQL_DB'] = 'myflaskapp'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# init MYSQL
mysql = MySQL(app)


def user_present(username):
    # create cursor
    cur = mysql.connection.cursor()

    # fetch rows of that username
    present_users = cur.execute("SELECT * FROM users WHERE username = %s", [username])

    if present_users > 0:  # if any row is found with that username
        return True
    else:
        return False

    # close connection
    cur.close()


# Index
@app.route('/')
def index():
    return render_template('home.html')

# About
@app.route('/about')
def about():
    return render_template('about.html')

# Articles
@app.route('/articles')
def articles():
    # create cursor
    cur = mysql.connection.cursor()

    # get articles
    result = cur.execute("SELECT * FROM articles")

    articles = cur.fetchall()  # will fetch in dictionary form

    if result > 0:  # if any row exists in db
        return render_template('articles.html', articles=articles)
    else:
        msg = "No articles to show."
        return render_template('articles.html', msg=msg)

    # close connection
    cur.close()

# Single Article
@app.route('/article/<string:id>/', methods=['GET', 'POST'])
def article(id):
    # create cursor
    cur = mysql.connection.cursor()

    # get articles
    result = cur.execute("SELECT * FROM articles WHERE id=%s", [id])

    article = cur.fetchone()  # will fetch in dictionary form

    comment_result = cur.execute("SELECT * FROM comments WHERE article_id=%s", [id])

    comments = cur.fetchall()

    if article['url']:
        return render_template('article-images.html', article=article, comments=comments)
    else:
        return render_template('article.html', article=article, comments=comments)


# Register Form Class
class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password',[
        validators.DataRequired(),
        validators.EqualTo('confirm', message="Passwords do not match")
    ])
    confirm = PasswordField('Confirm Password')

# User Register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)

    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # first check that username does not exist already
        if user_present(username):
            flash("This username already exists.", "danger")
        else:
            # Create cursor
            cur = mysql.connection.cursor()

            # now we can use this cur to execute mysql queries
            cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)",
                        (name, email, username, password))

            # commit to DB
            mysql.connection.commit()

            # close connection
            cur.close()

            # show or flash msg when registered
            flash('You are now registered and can login.', 'success')  # success is the category of flash msg

            # redirect
            return redirect(url_for('login'))


    return render_template('register.html', form=form)

#user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #get form fields
        username = request.form['username']
        password_candidate = request.form['password'] #actual correct password from db(unhashed one)

        # create cursor
        cur = mysql.connection.cursor()

        # get user by username
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username]) #from line 85

        if result > 0: # if any row is found
            # get stored hash
            data = cur.fetchone()             # fetch only the first one in, even if
                                              # there are more users with that username
            password = data['password']       # get the password from data(hashed), works because of line 18
                                              # treating them as dictionary
            # compare passwords
            if sha256_crypt.verify(password_candidate, password):
                # Passed
                # If user succesfully logins, create some session variables
                session['logged_in'] = True
                session['username'] = username

                flash("You are now logged in.", "success")
                return redirect(url_for('dashboard'))

            else:
                error = "Username not found."
                return render_template('login.html', error=error)

            # close connection
            cur.close()

        else:
            app.logger.info('NO USER')

    return render_template('login.html')

# check if user is logged in
def is_logged_in(f):  # we can use this on any route
    # used in dashboard, logout, add_article
    @wraps(f)  # import wraps. line 8
    def wrap(*args, **kwargs):
        # now write logic here
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Please login first. Takes less then a minute!', 'danger')
            return redirect(url_for('login'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out.', 'success')
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard')
@is_logged_in
def dashboard():
    current_user = session['username']

    # create cursor
    cur = mysql.connection.cursor()

    #get articles
    result = cur.execute("SELECT * FROM articles WHERE author=%s", [current_user])  # look at square brackets

    articles = cur.fetchall()  # will fetch in dictionary form

    if result > 0:  # if any row exists in db
        return render_template('dashboard.html', articles=articles)
    else:
        msg = "No articles submitted. Submit and let them see what you got :)"
        return render_template('dashboard.html', msg=msg)

    # close connection
    cur.close()

# Submit article comment
@app.route('/submit_comment/<string:id>', methods=['POST'])
@is_logged_in
def submit_comment(id):
    if request.method == 'POST':
        comment = request.form['body']

        # create cursor
        cur = mysql.connection.cursor()

        # now use this cur to execute mysql queries
        cur.execute("INSERT INTO comments(article_id, cmt_by, body) VALUES(%s, %s, %s)",
                    [id, session['username'], comment])

        # commit to DB
        mysql.connection.commit()

        result = cur.execute("SELECT * FROM articles WHERE id=%s", [id])
        article = cur.fetchone()

        comment_result = cur.execute("SELECT * FROM comments WHERE article_id=%s", [id])
        comments = cur.fetchall()

        if article['url']:
            flash("Comment successfully added.", "success")
            return render_template('article-images.html', article=article, comments=comments)

        else:
            flash("Comment successfully added.", "success")
            return render_template('article.html', article=article, comments=comments)

        # close connection
        cur.close()


# Article Form Class
class ArticleForm(Form):
    title = StringField('title', [validators.Length(min=1, max=200)])
    body = TextAreaField('body', [validators.Length(min=30)])


# Article Form if there are images
class ArticleForm_images(Form):
    title = StringField('title', [validators.Length(min=1, max=200)])


# Add Article
@app.route('/add_article', methods=['GET', 'POST'])
@is_logged_in
def add_article():
    form = ArticleForm(request.form)
    if request.method == 'POST' and form.validate():
        title = form.title.data
        body = form.body.data

        # create cursor
        cur = mysql.connection.cursor()

        # execute
        cur.execute("INSERT INTO articles(title, body, author) VALUES(%s, %s, %s)", (title, body, session['username']))

        # commit to database
        mysql.connection.commit()

        # close connection
        cur.close()

        flash("Article Submitted.", "success")
        return redirect(url_for('dashboard'))

    return render_template('add_article.html', form=form)

# Edit Article
@app.route('/edit_article/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def edit_article(id):
    # create cursor
    cur = mysql.connection.cursor()

    # first check that user is editing his own article
    result_auth = cur.execute("SELECT title, body FROM articles WHERE author=%s and id=%s", (session['username'], id))
    if result_auth > 0:
        article = cur.fetchone()
        if article['body']:
            # close connection
            cur.close()

            # get form
            form = ArticleForm(request.form)

            # populate article form fields
            form.title.data = article['title']
            form.body.data = article['body']

            if request.method == 'POST' and form.validate():
                title = request.form['title']
                body = request.form['body']

                # create cursor
                cur = mysql.connection.cursor()

                # execute
                cur.execute("UPDATE articles SET title=%s, body=%s WHERE id=%s", (title, body, id))

                # commit to database
                mysql.connection.commit()

                # close connection
                cur.close()

                flash("Article Updated.", "success")
                return redirect(url_for('dashboard'))
        else:
            # close connection
            cur.close()

            # get form
            form = ArticleForm_images(request.form)

            # populate article form fields
            form.title.data = article['title']

            if request.method == 'POST' and form.validate():
                title = request.form['title']

                # create cursor
                cur = mysql.connection.cursor()

                # execute
                cur.execute("UPDATE articles SET title=%s WHERE id=%s", (title, id))

                # commit to database
                mysql.connection.commit()

                # close connection
                cur.close()

                flash("Article Updated.", "success")
                return redirect(url_for('dashboard'))
    else:
        cur.close()
        flash("Permission denied!", "danger")
        return redirect(url_for('dashboard'))


    return render_template('edit_article.html', form=form, article=article)

# Delete Article
@app.route('/delete_article/<string:id>', methods=['GET', 'POST'])
@is_logged_in
def delete_article(id):
    # create cursor
    cur = mysql.connection.cursor()

    # first check that user is deleting his own article
    result = cur.execute("SELECT id FROM articles WHERE author=%s and id=%s", (session['username'], id))
    if result > 0:
        # get article by id
        cur.execute("DELETE FROM articles WHERE id=%s", [id])

        # commit to database
        mysql.connection.commit()

        # close connection
        cur.close()

        flash("Article Deleted.", "success")
        return redirect(url_for('dashboard'))
    flash("Permission denied.", "danger")
    return redirect(url_for('dashboard'))

@app.route('/upload')
@is_logged_in
def upload():
    return render_template('upload.html')

@app.route('/store', methods=['GET', 'POST'])
@is_logged_in
def store():
    if request.method == 'POST':
        url = request.form['avatar']
        title = request.form['title']
        imgs = int(url[-2])  # number of images uploaded

        # create cursor
        cur = mysql.connection.cursor()

        # now we can use this cur to execute mysql queries
        cur.execute("INSERT INTO articles(author, url, num_imgs, title) VALUES(%s, %s, %s, %s)",
                    [session['username'], url, imgs, title])

        # commit to database
        mysql.connection.commit()

        # close connection
        cur.close()

    flash("Uploaded Successfully.", "success")
    return redirect(url_for('dashboard'))



if __name__== '__main__':
    app.run(debug=True)

