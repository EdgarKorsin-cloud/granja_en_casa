from flask import Flask, render_template, redirect, url_for, request, flash, abort, current_app
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Text
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, URL, Email
from flask_ckeditor import CKEditor, CKEditorField
from flask_wtf.file import FileField, FileAllowed
from datetime import date
from flask_bootstrap import Bootstrap5
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from wtforms import PasswordField
from functools import wraps
import os
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)
login_manager = LoginManager()
login_manager.init_app(app)
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///posts.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return abort(403) # Forbidden
        return f(*args, **kwargs)
    return decorated_function
def author_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['admin', 'author']:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function

class User(UserMixin,db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(250), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")

with app.app_context():
    db.create_all()

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(),
                                             Email(check_deliverability=False, message="Invalid email address.")])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")

class RegisterForm(FlaskForm):
    name = StringField("Your Name", validators=[DataRequired()])
    email = StringField("Your Email", validators=[DataRequired(),
                                                  Email(check_deliverability=False, message="Invalid email address.")])
    password = PasswordField("Password", validators=[DataRequired()])
    token = StringField("Interview/Admin Token (Optional)")
    submit = SubmitField("Save User")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    author_id: Mapped[str] = mapped_column(Integer, db.ForeignKey('users.id'))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="parent_post")

with app.app_context():
    db.create_all()
class Comment(db.Model):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('users.id'))
    comment_author: Mapped[str] = relationship('User', back_populates='comments')
    post_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('blog_posts.id'))
    parent_post = relationship("BlogPost",back_populates="comments")

with app.app_context():
    db.create_all()
class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_file = FileField("Blog Image", validators=[
        DataRequired(),
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")

class CommentForm(FlaskForm):
    comment = TextAreaField("Leave a comment", validators=[DataRequired()])
    submit = SubmitField("Submit Comment")

@app.context_processor
def inject_year():
    return {'current_year': date.today().year}
@app.route('/')
def index():
    posts = db.session.execute(db.select(BlogPost)).scalars().all()
    return render_template('index.html', all_posts=posts)
@app.route('/edit-post/<int:post_id>', methods=['GET', 'POST'])
@author_only
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data

        post.body = edit_form.body.data

        db.session.commit()
        return redirect(url_for('show_post', post_id=post.id))
    return render_template('new_post.html', edit_form=edit_form, is_edit=True)
@app.route('/delete/<int:post_id>')
@admin_only
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('You need to be logged in to be able to comment', 'danger')
            return redirect(url_for('login'))
        new_comment = Comment(
            text=comment_form.comment.data,
            comment_author=current_user,
            parent_post =requested_post,
        )
        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=requested_post.id))
    return render_template('post.html', post=requested_post, form=comment_form)

@app.route("/new-post", methods=["GET", "POST"])
@author_only
def new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        f = form.img_file.data
        filename= secure_filename(f.filename)
        save_path = os.path.join(app.root_path, 'static/uploads', filename)
        f.save(save_path)
        db_image_path = f"uploads/{filename}"
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=db_image_path,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('new_post.html', form=form)

@app.route('/contact', methods=['POST'])
def contact():
    user_name = request.form.get('name')
    user_email = request.form.get('email')
    user_message = request.form.get('message')
    print(f'New message received!\nFrom: {user_name} {user_email}\n'
          f'Message: {user_message}')
    return render_template('index.html',
                           success_message='Thank you! Your message has been sent')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        assigned_role = "user"
        if form.token.data == "SecretAdmin123":
            assigned_role = "admin"
        elif form.token.data == "SecretInterview123":
            assigned_role = "author"
        elif form.token.data:
            flash("Invalid token. Leave blank for normal user.")
            return redirect(url_for('register'))

        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            flash("You've already signed up with that email!")
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hashed_password,
            role=assigned_role
        )
        db.session.add(new_user)
        db.session.commit()

        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html', form=form)

@app.route('/users')
def users_list():
    users = db.session.execute(db.select(User)).scalars().all()
    return render_template('users.html', all_users=users)

@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    user=db.get_or_404(User, user_id)
    edit_form = RegisterForm(
        name=user.name,
        email=user.email,
    )
    if edit_form.validate_on_submit():
        user.name=edit_form.name.data
        user.email=edit_form.email.data

        if edit_form.password.data:
            user.password = generate_password_hash(
                edit_form.password.data, method='pbkdf2:sha256', salt_length=8
            )
        db.session.commit()
        return redirect(url_for('users_list'))
    return render_template("register.html", form=edit_form, is_edit=True)

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    user_to_delete = db.get_or_404(User, user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    return redirect(url_for('users_list'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form =LoginForm()
    if form.validate_on_submit():
        password = form.password.data

        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()

        if not user:
            flash("That email does not exist, please try again.")
        elif not check_password_hash(user.password, password):
            flash("Incorrect Password!")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html', form=form)
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
