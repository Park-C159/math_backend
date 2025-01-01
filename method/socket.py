from time import sleep

from flask_socketio import SocketIO, emit, Namespace
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation import TextIteratorStreamer
from threading import Thread

socketio = SocketIO(cors_allowed_origins="*")

# 模型路径
model_path = 'models/Yi-1.5-6B-Chat'

# 加载 Tokenizer 和 Model
# device = torch.device('cuda:0')
tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=False)
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    device_map="auto",  # 自动将模型分配到 GPU
    torch_dtype='auto'
).eval()


# 定义对话函数
def chat():
    # 初始化对话历史
    history = [
        {"role": "user", "content": "你是一个AI数学助手，你将帮助大学生解答各方面的数学疑问。"}
    ]

    while True:
        # 获取用户输入
        user_input = input("用户: ").strip()
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("对话结束。")
            break

        # 构造消息格式
        messages = [{"role": "user", "content": user_input}]
        for past_msg in history:
            messages.insert(0, past_msg)

        # 准备模型输入
        input_ids = tokenizer.apply_chat_template(conversation=messages, tokenize=True, return_tensors='pt')
        # input_ids = input_ids.to(device)
        input_ids = input_ids.to('cuda')

        # 使用 TextIteratorStreamer 实现逐字输出
        streamer = TextIteratorStreamer(tokenizer, timeout=60, skip_special_tokens=True)
        generation_thread = Thread(target=model.generate, kwargs={
            "input_ids": input_ids,
            "streamer": streamer,
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.95,
            "eos_token_id": tokenizer.eos_token_id
        })
        generation_thread.start()

        print("助手: ", end="", flush=True)
        response = ""
        for token in streamer:
            # 跳过特殊标记
            if "|im_start|" not in token:
                response += token
                print(token, end="", flush=True)

        print()

        # 更新对话历史
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": response})


import uuid


class ChatNamespace(Namespace):
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.connected = False  # 标志客户端连接状态
        self.session_id = None  # 唯一标识符
        self.history = []  # 对话历史

    def on_connect(self):
        print("Client connected")
        self.connected = True
        # 为新连接生成唯一 session_id
        self.session_id = str(uuid.uuid4())
        print(f"New session_id: {self.session_id}")
        # 初始化对话历史
        self.history = [
            {"role": "user", "content": "你是一个AI数学助手，你将帮助大学生解答各方面的数学疑问。"}
        ]

    def on_disconnect(self):
        print(f"Client disconnected (session_id: {self.session_id})")
        self.connected = False  # 设置断开标志

    def on_user_message(self, message):
        print(f"Received message: {message} (session_id: {self.session_id})")
        # 向对话历史中添加用户消息
        self.history.append({"role": "user", "content": message})
        # 创建线程处理生成逻辑，传递当前 session_id
        Thread(target=self.stream_response, args=(message, self.session_id)).start()

    def stream_response(self, user_input, session_id):
        # 准备模型输入
        input_ids = tokenizer.apply_chat_template(conversation=self.history, tokenize=True, return_tensors='pt')
        input_ids = input_ids.to('cuda')

        # 使用 TextIteratorStreamer 实现逐字输出
        streamer = TextIteratorStreamer(tokenizer, timeout=60, skip_special_tokens=True)
        generation_thread = Thread(target=model.generate, kwargs={
            "input_ids": input_ids,
            "streamer": streamer,
            "max_new_tokens": 512,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.95,
            "eos_token_id": tokenizer.eos_token_id
        })
        generation_thread.start()

        response = ""  # 收集生成的完整响应
        for token in streamer:
            # 如果客户端断开或 session_id 不匹配，停止生成
            if not self.connected or self.session_id != session_id:
                print(f"Stopping generation for session_id: {session_id}")
                return

            if "|im_start|" not in token:  # 跳过特殊标记
                response += token
                socketio.emit('server_response', token, namespace='/chat_ai')  # 实时发送生成的 token

        # 向对话历史中添加模型响应
        self.history.append({"role": "assistant", "content": response})
        # 发送结束信号
        socketio.emit('server_response', '[END]', namespace='/chat_ai')
