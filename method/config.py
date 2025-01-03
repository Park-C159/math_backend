import os


class Config:
    SECRET_KEY = 'your_secret_key'
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'mysql://root:123456@localhost/math'
    # SQLALCHEMY_TRACK_MODIFICATIONS = False  # 关闭修改跟踪以减少开销
    # 配置上传路径
    UPLOAD_FOLDER = 'uploads/'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    ALLOWED_PDF_EXTENSIONS = {'pdf'}
