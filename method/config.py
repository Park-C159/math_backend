class Config:
    SECRET_KEY = 'your_secret_key'
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'mysql+mysqlconnector://root:123456@localhost/math'
    # SQLALCHEMY_TRACK_MODIFICATIONS = False  # 关闭修改跟踪以减少开销