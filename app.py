import shutil
import os
from cursor import Cursor
from flask_httpauth import HTTPBasicAuth
from flask import Flask, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from settings import DATA_PATH, TEXT_MAX_LEN, RESULTS_PATH, PORT, USE_CASE
from deep_utils import remove_create, log_print, get_logger, split_extension

os.makedirs(RESULTS_PATH, exist_ok=True)

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = -1
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
min_length = 1
max_length = 15

app = Flask(__name__)
auth = HTTPBasicAuth()

with open('.secrets', 'r') as f:
    ph = f.read().strip()

# yes move this to .secrets
users = {
   "labeler": ph,
}

@auth.verify_password
def verify_password(username, password):
    if username in users and \
            check_password_hash(users.get(username), password):
        return username


@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r


# fetch cursor file
cursor = Cursor(data_dir=DATA_PATH, labeled_dir=RESULTS_PATH)
logger = get_logger("app", split_extension(cursor.cursor_path, extension=".log"))


# app routes
@app.route('/index')
@app.route('/')
@auth.login_required
def index():
    cursor.reload_file()
    image_name = cursor.get_next_image()
    if image_name is None:
        # Handle case when no more images are available
        return render_template('no_more_images.html')
    
    text = os.path.splitext(image_name)[0]
    index = cursor['file_index_to_read']
    images_count = len(cursor['images'])
    use_case = cursor['use_case']

    if use_case.lower() == "plate":
        text = text.split("_")[-1]
        text_01 = text[:2]
        text_02 = text[2]
        text_03 = text[3:]
    elif use_case.lower() == "ocr":
        text_01 = text.split("_")[-1]
        text_02 = ""
        text_03 = ""
    else:
        raise ValueError("USE_CASE type is not valid")
    remove_create("static/ocr_images")
    photo = os.path.join(DATA_PATH, image_name)
    dst = os.path.join("static/ocr_images", image_name)
    shutil.copy(photo, dst)
    return render_template('index.html', text_01=text_01, text_02=text_02, text_03=text_03, text=text, photo=image_name,
    min_length=min_length, max_length=max_length, index=index, images_count=images_count, use_case=use_case.lower())



@app.route('/action', methods=['POST', 'GET'])
def action():
    use_case = cursor['use_case']
    if request.method == 'POST':
        if request.form['action'] == "Save":
            if use_case.lower() == "plate":
                text = request.form.get('text_01') + request.form.get("text_02") + request.form.get("text_03")
            elif use_case.lower() == "ocr":
                text = request.form.get('text_01')
            else:
                raise ValueError()
            if len(text) <= TEXT_MAX_LEN:
                index = cursor['file_index_to_read']
                img_path = os.path.join(DATA_PATH, cursor['images'][str(index)])
                # get file extension e.g. jpg, png
                img_extension = os.path.splitext(img_path)[1]
                # copy file with a new name!
                shutil.copy(img_path, f"{RESULTS_PATH}/{index}_{text}{img_extension}")
                log_print(logger, f"Wrote image to {RESULTS_PATH}/{index}_{text}{img_extension}")
                # update index to read in cursor
                cursor.increase_index()
        # go to next image if skip is entered
        elif request.form['action'] == "Skip":
            cursor.increase_index()
        # jump to a specific index, choose from indexes under 'images' key in cursor.json
        elif request.form['action'] == "Jump":
            try:
                jump_index = int(request.form['jump_index'])
                if jump_index == 0:
                    raise ValueError("Index starts from 1.")
                cursor.set_index(jump_index)
            except ValueError:
                return redirect(url_for('index'))
        elif request.form['action'] == "Set":
            try:
                cursor.save_lengths(request.form['text_min_len'], request.form['text_max_len'])
                cursor.set_use_case_plate(request.form['plate-usual'] == 'on')
            except KeyError as e:
                if e.args[0] == 'text_min_len':
                    cursor.save_lengths("3", "3")
                    cursor.set_use_case_plate(True)
                if e.args[0] == 'plate-usual':
                    cursor.set_use_case_plate(False)

    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=PORT, debug=False)
