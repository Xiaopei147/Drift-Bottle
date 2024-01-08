# app.py

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import pymysql
import os
import base64
from datetime import datetime
from io import BytesIO
from PIL import Image
import random
import re
import configparser

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 连接到MySQL数据库
db = pymysql.connect(
    host=config['database']['host'],
    user=config['database']['user'],
    password=config['database']['password'],
    database=config['database']['database'],
    port=int(config['database']['port']),  # 添加端口配置
    connect_timeout=3600
)
cursor = db.cursor()


#展示所以功能
@app.route('/all')
def show_all_features():
    return render_template('all.html')

# 注册功能
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        cursor.execute("INSERT INTO users (username, password, email) VALUES (%s, %s, %s)", (username, password, email))
        db.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

# 添加一个新的路由，用于展示登录页面
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user_id' in session:
        # 如果用户已登录，直接重定向到submit_bottle
        return redirect(url_for('submit_bottle'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT id FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]  # 将用户ID存储在会话中
            return redirect(url_for('submit_bottle'))
        else:
            flash('用户名或密码错误', 'error')

    return render_template('login.html')


# 登录功能
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor.execute("SELECT id FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('submit_bottle'))
    return render_template('login.html')

#注销功能
@app.route('/logout')
def logout():
    # 注销逻辑
    session.pop('user_id', None)  # 从 session 中移除用户名
    return redirect(url_for('login'))

# 提交漂流瓶功能
@app.route('/submit_bottle', methods=['GET', 'POST'])
def submit_bottle():
    if request.method == 'POST':
        message = request.form['message']
        sender_id = session.get('user_id')
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO bottles (message, sender_id, created_at) VALUES (%s, %s, %s)", (message, sender_id, created_at))
        db.commit()
        return redirect(url_for('view_bottle'))
    return render_template('submit_bottle.html')

import logging

# 设置日志记录
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 拾取漂流瓶功能
@app.route('/pick_up_bottle')
def pick_up_bottle():
    user_id = session.get('user_id')
    try:
        cursor.execute("SELECT id, message, sender_id, created_at FROM bottles WHERE sender_id != %s AND (id NOT IN (SELECT bottle_id FROM bottle_picks WHERE user_id = %s) OR id IN (SELECT bottle_id FROM bottle_picks WHERE user_id = %s))", (user_id, user_id, user_id))
        available_bottles = cursor.fetchall()
        if available_bottles:
            # 获取当前用户已经拾取过的漂流瓶的ID列表
            cursor.execute("SELECT bottle_id FROM bottle_picks WHERE user_id = %s", (user_id,))
            picked_bottle_ids = [row[0] for row in cursor.fetchall()]

            # 从可选漂流瓶中排除已经拾取过的漂流瓶
            available_bottles = [bottle for bottle in available_bottles if bottle[0] not in picked_bottle_ids]

            if available_bottles:
                bottle = random.choice(available_bottles)  # 随机选择一个漂流瓶
                bottle_id, message, sender_id, created_at = bottle

                # 将漂流瓶添加到 bottle_picks 表中
                cursor.execute("INSERT INTO bottle_picks (user_id, bottle_id) VALUES (%s, %s)", (user_id, bottle_id))
                db.commit()
                logger.debug(f"Bottle with id {bottle_id} picked up by user {user_id}")

                # 获取发送者的昵称
                cursor.execute("SELECT nickname FROM users WHERE id = %s", (sender_id,))
                sender_nickname = cursor.fetchone()[0]

                return render_template('picked_up_bottle.html', message=message, sender_nickname=sender_nickname, created_at=created_at)

                # 在这里，不再需要显示按钮，因为用户看到漂流瓶信息就表示用户已经捡起了这个漂流瓶

            else:
                return "当前没有可供拾取的漂流瓶，请稍后再试。"
        else:
            return "当前没有可供拾取的漂流瓶，请稍后再试。"
    except Exception as e:
        db.rollback()
        logger.error(f"An error occurred: {e}")
        return "出现错误，请稍后再试。"


# 查看自己提交的漂流瓶功能
@app.route('/view_bottle')
def view_bottle():
    user_id = session.get('user_id')  # 获取当前用户的ID
    print("Current user ID:", user_id)  # 打印当前用户的ID
    cursor.execute("SELECT message, created_at FROM bottles WHERE sender_id = %s", (user_id,))
    my_bottles = cursor.fetchall()
    print("My bottles:", my_bottles)  # 打印从数据库中获取的漂流瓶数据
    return render_template('view_bottle.html', bottles=my_bottles)

# 查看拾取的漂流瓶
@app.route('/view_found_bottle')
def view_found_bottle():
    finder_id = session.get('user_id')
    cursor.execute("SELECT b.message, b.created_at FROM bottle_picks bp JOIN bottles b ON bp.bottle_id = b.id WHERE bp.user_id = %s", (finder_id,))
    found_bottles = cursor.fetchall()

    # 在这里为漂流瓶列表添加序号
    processed_found_bottles = [(index + 1, bottle) for index, bottle in enumerate(found_bottles)]

    return render_template('view_found_bottle.html', bottles=processed_found_bottles)

#清空拾取的漂流瓶列表
@app.route('/clear_found_bottles')
def clear_found_bottles():
    user_id = session.get('user_id')
    cursor.execute("DELETE FROM bottle_picks WHERE user_id = %s", (user_id,))
    db.commit()
    return redirect(url_for('view_found_bottle'))

# 保存头像到本地目录
def save_avatar(avatar, user_id):
    if avatar:
        avatar.save(os.path.join('avatar', f'{user_id}.png'))  # 保存头像到本地目录，假设文件名为用户ID.png

# 上传头像功能
@app.route('/upload_avatar', methods=['GET', 'POST'])
def upload_avatar():
    if request.method == 'POST':
        if 'avatar' in request.files:
            avatar = request.files['avatar']
            user_id = session.get('user_id')
            save_avatar(avatar, user_id)
            return redirect(url_for('user_profile'))
    return render_template('upload_avatar.html')

# 静态文件路由，用于访问保存在本地目录中的头像文件
@app.route('/avatar/<path:filename>')
def serve_avatar(filename):
    return send_from_directory('avatar', filename)

# 从数据库中获取用户信息
def get_user_info(user_id):
    cursor.execute("SELECT username, email, avatar, nickname FROM users WHERE id = %s", (user_id,))
    user_info = cursor.fetchone()
    if user_info:
        user_info_dict = {
            'username': user_info[0],
            'email': user_info[1],
            'avatar': user_info[2],  # 注意这里不再是 avatar_url，而是直接取得头像数据
            'nickname': user_info[3]
        }
        return user_info_dict
    else:
        # 如果未找到用户信息，可以返回一个默认的用户信息或者抛出异常
        return None  # 或者返回一个默认的用户信息

# 解码 BASE64 编码的图像数据
def decode_base64_image(base64_string):
    if base64_string is not None:
        image_data = base64.b64decode(base64_string)
        return Image.open(BytesIO(image_data))
    else:
        return None  # 或者返回一个默认的头像图片

@app.route('/user_profile')
def user_profile():
    user_id = session.get('user_id')
    user_info = get_user_info(user_id)

    if user_info:  # 确保 user_info 不为 None
        # 解码头像数据并保存为图像文件
        avatar_image = decode_base64_image(user_info['avatar'])
        avatar_image_path = f'avatar/{user_id}.png'  # 保存解码后的图像文件
        if avatar_image:
            avatar_image.save(avatar_image_path)

        # 在模板中使用 avatar_image_path 来显示头像
        user_info['avatar_url'] = f'/avatar/{user_id}.png'  # 直接指定头像的 URL

        return render_template('user_profile.html', user=user_info)
    else:
        # 如果 user_info 为 None，可以根据实际情况返回错误页面或者其他处理方式
        return "用户信息不存在或者出现错误"

# 修改密码功能
@app.route('/change_password', methods=['POST'])
def change_password():
    user_id = session.get('user_id')
    old_password = request.form['old_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']

    # 从数据库中获取用户的旧密码
    cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
    stored_password = cursor.fetchone()[0]

    if new_password != confirm_password:
        flash('新密码和确认密码不一致', 'error')
        return redirect(url_for('user_profile'))

    if old_password != stored_password:
        flash('旧密码不正确', 'error')
        return redirect(url_for('user_profile'))

    # 更新用户密码
    cursor.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, user_id))
    db.commit()
    flash('密码修改成功', 'success')
    return redirect(url_for('user_profile'))


@app.route('/update_profile', methods=['POST'])
def update_profile():
    new_email = request.form['email']
    new_nickname = request.form['nickname']
    user_id = session.get('user_id')
    cursor.execute("UPDATE users SET email = %s, nickname = %s WHERE id = %s", (new_email, new_nickname, user_id))
    db.commit()
    return redirect(url_for('user_profile'))

if __name__ == '__main__':
    app.run(debug=True, port=int(config['app']['port']))
