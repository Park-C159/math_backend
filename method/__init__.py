from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from method.socket import *


db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    # 加载配置
    app.config.from_object('method.config.Config')

    # 初始化数据库
    db.init_app(app)
    with app.app_context():
        db.create_all()
    # 注册路由
    from .routes import main
    app.register_blueprint(main)

    # socketio.init_app(app)
    # socketio.on_namespace(ChatNamespace('/chat_ai'))

    return app
