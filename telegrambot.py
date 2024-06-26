import html
import json
import traceback
import logging
import socket
import threading
from typing import Final
from telegram.constants import ParseMode
from hashlib import sha256
from pymongo import MongoClient
from telegram import (InlineQueryResultArticle, InlineQueryResultPhoto, InputTextMessageContent, Update,
                      InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (ApplicationBuilder, ContextTypes, InlineQueryHandler, CommandHandler, filters, MessageHandler,
                          ConversationHandler, CallbackQueryHandler)

from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

settings = open("settings.json", "r") #chage this to open("sample_settings.json", "r") for your test
settings = json.load(settings)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


CHANNEL_ID: Final = settings[0]['channel_id']
TOKEN: Final = '6777553545:AAFmGKGc1mqUORYJh9s4fRRaB4tXd7jJj8c'
# Connect to database
client = MongoClient(settings[0]['mongo_uri'])
db = client['TelegramBot']
users_collection = db['users']
logged_in_collection = db['logged_in']
files_collection = db['files']


def handle_client(client_socket):
    # Handle incoming client connections here
    data = client_socket.recv(1024)
    # Process the data received from the client
    print(f"Received data: {data.decode()}")
    client_socket.close()


def run_tcp_server():
    HOST = '0.0.0.0'  # Listen on all available interfaces
    PORT = 8000  # Choose a port number for your TCP server

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()

        print(f"TCP Server listening on {HOST}:{PORT}")

        while True:
            client_socket, _ = server_socket.accept()
            handle_client(client_socket)

def run_flask():
    app.run(debug=False, host='0.0.0.0')


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f'\n\nبه بات تلگرامی {settings[0]["bot_name"]} خوش آمدید، برای ادامه لطفا یکی از آپشن های زیر را انتخاب کنید.\n\n'
    text += '\n\nبرای دیدن لیست کامل دستورات و راهنمایی لطفا برروی /help بزنید\n\n'
    options = ['/login برای ورود به اکانت', '/ticket برای درخواست پشتیبانی']
    text += '\n'.join(options)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open('help.txt', 'rb') as f:
        byte_string = f.read()
        text = byte_string.decode('UTF-8')
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

USERNAME, PASSWORD, SET_PASS = range(3)
REGISTER = 0
STATE0, STATE1, STATE2, PAGINATION = range(4)


async def forward_audio_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='ابتدا باید /login کنید')
        return ConversationHandler.END
    all_topics = {'اصول فقه': 'osool', 'تذکره': 'tazkareh', 'دره نجفیه': 'dorre', 'رجوم الشیاطین': 'rojoom',
                  'رساله غیبت': 'gheibat', 'سلطانیه': 'soltanieh', 'شرایط دعا': 'Doa', 'قرآن محشی': 'mohassha',
                  'متفرقه': 'others', 'معادیه': "ma'adieh", 'معرفت سر اختیار': 'marefat', 'منطق': 'mantegh',
                  'مواعظ': 'mavaez', 'میزان': 'mizan'}

    response = create_menu(name_dict=all_topics)
    reply_markup = InlineKeyboardMarkup(response)
    context.user_data['query_item'] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text='لطفا از فهرست پایین یک مورد را انتخاب کنید',
                                   reply_markup=reply_markup)
    return STATE0


async def button1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # mohassha
    context.user_data['query_item'].append(query.data)
    all_topics = {'baghareh': 'سوره بقره', 'hamd': 'سوره حمد',
                  'ekhlas': 'سوره اخلاص', 'jozv30': 'جزء سی',
                  'FakhrRazi': 'فخر رازی', 'Taftazani': 'تفتازانی',
                  'moghadame': 'مقدمه', '1': 'جلد اول', '2': 'جلد دوم',
                  '92': 'سال 1992'}
    reverse_all_topics = {value: key for key, value in all_topics.items()}
    files = sort_result(
        list(files_collection.find({'file_name': {'$regex': '-'.join(context.user_data['query_item'])}})))
    s = list()
    try:
        for file in files:
            s.append(all_topics[file['file_name'].split('-')[1].replace('.mp3', '')])
        s = set(s)
        sub_menu = {i: reverse_all_topics[i] for i in s}
    except:
        sub_menu = {}
        for file in files:
            sub_menu[file['title']] = file['file_name']

        if len(sub_menu) > 100:
            text = f'تعداد فایل ها زیاد است، لطفا شماره فایل مورد نظر در درس {sub_menu[list(sub_menu.keys())[0]].split("-")[0]} را بگویید'
            values = list(sub_menu.values())
            ranges = [int(float(x.split('-')[-1].removesuffix('.mp3'))) for x in values]
            min_num = min(ranges)
            max_num = max(ranges)
            text += f'\n\n این درس از شماره {min_num} تا {max_num} دارد'
            await query.edit_message_text(text=text)
            return PAGINATION

        reply_markup = InlineKeyboardMarkup(create_menu(name_dict=sub_menu))
        await query.edit_message_text(text=f'you choose: {query.data}', reply_markup=reply_markup)
        return STATE2

    reply_markup = InlineKeyboardMarkup(create_menu(name_dict=sub_menu))
    await query.edit_message_text(text=f'you choose: {query.data}', reply_markup=reply_markup)
    return STATE1


async def button2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # mohassha-ekhlas
    context.user_data['query_item'].append(query.data)

    files = sort_result(
        list(files_collection.find({'file_name': {'$regex': '-'.join(context.user_data['query_item'])}})))
    if await send_file(files, update, context, query):
        return ConversationHandler.END
    sub_menu = dict()
    for file in files:
        sub_menu[file['title']] = file['file_name']

    if len(sub_menu) > 100:
        text = f'تعداد فایل ها زیاد است، لطفا شماره فایل مورد نظر در درس {sub_menu[list(sub_menu.keys())[0]].split("-")[0]} را بگویید'
        values = list(sub_menu.values())
        ranges = [int(float(x.split('-')[-1].removesuffix('.mp3'))) for x in values]
        min_num = min(ranges)
        max_num = max(ranges)
        text += f'\n\n این درس از شماره {min_num} تا {max_num} دارد'
        await query.edit_message_text(text=text)
        return PAGINATION

    reply_markup = InlineKeyboardMarkup(create_menu(name_dict=sub_menu))
    await query.edit_message_text(text=f'you choose: {query.data}', reply_markup=reply_markup)
    return STATE2


async def button3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query  # mohassha-ekhlas-2
    context.user_data['query_item'].append(query.data)
    files = sort_result(list(files_collection.find({'file_name': {'$regex': context.user_data['query_item'][-1]}})))
    for file in files:
        await update.effective_chat.forward_from(from_chat_id=CHANNEL_ID, message_id=file['message_id'])
    await query.edit_message_text(text='فایل با موفقیت ارسال شد')
    return ConversationHandler.END


async def send_file(files, update: Update, context: ContextTypes.DEFAULT_TYPE, query):
    if len(files) == 1:
        await query.edit_message_text(text='فایل با موفقیت ارسال شد')
        await update.effective_chat.forward_from(from_chat_id=CHANNEL_ID, message_id=files[0]['message_id'])
        return True
    return False


async def pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file_name = context.user_data['query_item'][-1] + '-' + update.message.text
    files = list(files_collection.find({"file_name": {"$regex": f'^{file_name}\D'}}))
    if len(files) == 0:
        text = 'فایل با این شماره وجود ندارد'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    for file in files:
        await update.effective_chat.forward_from(from_chat_id=CHANNEL_ID, message_id=file['message_id'])
    return ConversationHandler.END


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    await query.edit_message_text(text='نشست شما در این فراخوانی به پایان رسیده لطفا مجددا دستور را وارد '
                                       'کنید')

def do_sort(item):
    file_name = item.get('file_name')
    file_name = file_name.split('-')
    if not file_name[-1].removesuffix('.mp3').isdigit():
        return 0
    pos_1, pos_2 = 0, 0
    pos_1 = int(float(file_name[-1].removesuffix('.mp3')))
    try:
        pos_2 = int(file_name.split('-')[-2])
    except:
        pass
    return pos_2*100 + pos_1

def sort_result(result):
    return sorted(result, key=do_sort)


def create_menu(count: int=None, name_dict: dict=None):
    response = []
    i = 0
    if name_dict is not None:
        for key, value in name_dict.items():
            if i % 2 == 0:
                response.append([InlineKeyboardButton(key, callback_data=value)])
            else:
                response[i // 2].append(InlineKeyboardButton(key, callback_data=value))
            i += 1
    elif count is not None:
        for i in range(count):
            if i % 2 == 0:
                response.append([InlineKeyboardButton(str(i+1), callback_data=i)])
            else:
                response[i//2].append(InlineKeyboardButton(str(i+1), callback_data=i))
    return response


def is_authorized(chat_id: int) -> bool:
    if logged_in_collection.find_one({'chat_id': chat_id}):
        return True
    return False


def is_admin(chat_id: int) -> bool:
    user = logged_in_collection.find_one({'chat_id': chat_id})
    if user:
        username = user['username']
        if users_collection.find_one({'username': username})['is_admin']:
            return True
    return False

async def login_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update.effective_chat.id):
        text = 'شما قبلا وارد شدید و میتوانید از امکانات استفاده کنید.'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                       reply_to_message_id=update.effective_message.message_id)
        return ConversationHandler.END
    text = 'لظفا نام کاربری خودرا وارد کنید، اگر نام کاربری ندارید با پشتیبانی ارتباط بگیرید.'
    text += '\n\n'
    text += 'ضمنا در هر مرحله برای لغو عملیات ورود دستور /cancel را وارد کنید.'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return USERNAME


async def login_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.lower()
    user = users_collection.find_one({'username': username})
    if user:
        context.user_data['username'] = username
        if user['password']==None:
            text = 'لطفا برای خود رمزی تعیین کنید:'
            await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                           reply_to_message_id=update.effective_message.message_id)
            return SET_PASS

        text = 'لطفا کلمه عبور خود را وارد کنید.'
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                       reply_to_message_id=update.effective_message.message_id)
        return PASSWORD
    text = 'کاربر با این مشخصات یافت نشد، مجددا با /login وارد شوید.'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                       reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def login_check_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    password = sha256(password.encode('utf-8')).hexdigest()
    user = users_collection.find_one({'username': context.user_data['username'].lower(), "password": password})
    if user:
        text = 'شما با موفقیت وارد شدید'
        logged_in_collection.insert_one({'chat_id': update.effective_chat.id,
                                         'username': context.user_data['username']})
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
        await context.bot.delete_message(chat_id=update.effective_chat.id,
                                         message_id=update.effective_message.message_id)
        return ConversationHandler.END
    text = 'رمز عبور اشتباه است مجددا با دستور /login وارد شوید'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def login_set_password_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    password = sha256(password.encode('utf-8')).hexdigest()
    users_collection.find_one_and_update({'username': context.user_data['username']},
                                         {'$set': {'password': password}})
    logged_in_collection.insert_one({'chat_id': update.effective_chat.id, 'username': context.user_data['username']})
    text = 'شما با موفقیت وارد شدید'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    await context.bot.delete_message(chat_id=update.effective_chat.id,
                                     message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def login_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'عملیات ورود لغو شد!'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def register_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'عملیات ثبت نام لغو شد!'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def audio_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'عملیات لغو شد!'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END


async def ticket_cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = 'عملیات درخواست پشتیبانی لغو شد!'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                   reply_to_message_id=update.effective_message.message_id)
    return ConversationHandler.END
async def logout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_authorized(update.effective_chat.id):
        logged_in_collection.delete_one({'chat_id': update.effective_chat.id})
        await context.bot.send_message(chat_id=update.effective_chat.id, text='خارج شدید',
                                       reply_to_message_id=update.effective_message.id)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='شما اصلا وارد نشده اید!',
                                       reply_to_message_id=update.effective_message.id)


async def register_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if is_admin(chat_id):
        text = '\n\nلطفا با فرم زیر نام کاربری و دسترسی ادمین بودن را (با صفر یا یک) وارد کنید\n\n'
        text += 'username_example:admin_status\n\n'
        text += '\n\nمثلا اگر نام کاربری ali میباشد و کاربر غیر ادمین است از دستور زیر باید استفاده شود\n\n'
        text += 'ali:0'
        await context.bot.send_message(chat_id=chat_id, text=text)
        return REGISTER
    await context.bot.send_message(chat_id=chat_id, text='شما مجاز به ثبت نام شخص دیگری نیستید')


async def register_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(update.message.text.split(':')) != 2 or update.message.text.split(':')[1] not in ['0', '1']:
            raise Exception('Error - Check your input format')
        username, is_admin = update.message.text.split(':')
        username = username.lower()
        if users_collection.find_one({'username': username}):
            raise Exception('User already exists')
        users_collection.insert_one({'username': username, 'password': None, 'is_admin': int(is_admin)})
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f'کاربر با موفقیت ایجاد شد!')
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=str(e)+'\ntry again with /register')
    return ConversationHandler.END


TICKET = 0
async def ticket_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text='لطفا مشکل خودرا در یک پیام با جزئیات توضیح دهید')
    return TICKET


async def ticket_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    chat_id = update.effective_chat.id
    username = update.effective_chat.username
    text = f'{chat_id=}, {username=}, \nmessage:\n{message}'
    await context.bot.send_message(chat_id=settings[0]['developer_id'], text=text)
    await context.bot.send_message(chat_id=chat_id, text='پیام شما برای پشتیبان ارسال شد!')
    return ConversationHandler.END


async def push_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='شما حق استفاده از این دستور را ندارید')
        return
    try:
        mode = context.args[0]
        message = update.message.text.split(" ")[2:]
        message = ' '.join(message)
    except:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='bad arguments. try /push <mode> <message>')
        return

    if mode.lower() == 'public':
        chats = logged_in_collection.find()
        for chat in chats:
            await context.bot.send_message(chat_id=int(chat['chat_id']), text=message)
    else:
        try:
            await context.bot.send_message(chat_id=int(mode), text=message)
        except:
            await context.bot.send_message(chat_id=update.effective_chat.id, text='bad chat id.')
            return
    await context.bot.send_message(chat_id=update.effective_chat.id, text='Done!')


async def sessions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='شما دسترسی به این قابلیت ندارید')
    all_users = list(users_collection.find())
    logged_in_users = list(logged_in_collection.find())
    logged_in_usernames = []

    await context.bot.send_message(chat_id=update.effective_chat.id,
                                 text='لیست تمامی افراد در زیر آمده، افرادی که لاگین هستند با تیک سبز مشخص شده اند')
    for lgu in logged_in_users:
        logged_in_usernames.append(lgu['username'])
    result = []
    for user in all_users:
        if user['username'] in logged_in_usernames:
            result.append(user['username']+' ✅')
        else:
            result.append(user['username'])
    await context.bot.send_message(chat_id=update.effective_chat.id, text='\n'.join(result))


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message about an exception, but as a
    # list of strings rather than a single string, so we have to join them together.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    try:
        logs = json.dumps(update_str)
        logs = json.loads(logs)
        c_id = logs['message']['chat']['id']
        await context.bot.send_message(chat_id=c_id, text='Error - Unhandled Exception Occurred, details sent to developer')
    except:
        await context.bot.send_message(chat_id=settings[0]['developer_id'], text='Error Sending Message to Client')
    # Finally, send the message
    await context.bot.send_message(
        chat_id=settings[0]['developer_id'], text=message, parse_mode=ParseMode.HTML
    )

def run_telegram_bot():
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))

    login = ConversationHandler(
        entry_points=[CommandHandler('login', login_handler)],
        states={USERNAME: [MessageHandler(filters.TEXT & ~ filters.COMMAND, login_password_handler)],
                PASSWORD: [MessageHandler(filters.TEXT & ~ filters.COMMAND, login_check_user_handler)],
                SET_PASS: [MessageHandler(filters.TEXT & ~ filters.COMMAND, login_set_password_handler)]},
        fallbacks=[MessageHandler(filters.COMMAND, login_cancel_handler)]
    )

    register = ConversationHandler(
        entry_points=[CommandHandler('register', register_handler)],
        states={REGISTER: [MessageHandler(filters.TEXT & ~ filters.COMMAND, register_info_handler)]},
        fallbacks=[CommandHandler('cancel', register_cancel_handler)]
    )

    ticket = ConversationHandler(
        entry_points=[CommandHandler('ticket', ticket_handler)],
        states={TICKET: [MessageHandler(filters.TEXT & ~ filters.COMMAND, ticket_info_handler)]},
        fallbacks=[CommandHandler('cancel', ticket_cancel_handler)]
    )

    audio = ConversationHandler(
        entry_points=[CommandHandler('audio', forward_audio_handler)],
        states={STATE0: [CallbackQueryHandler(button1)],
                STATE1: [CallbackQueryHandler(button2)],
                STATE2: [CallbackQueryHandler(button3)],
                PAGINATION: [MessageHandler(filters.TEXT & ~ filters.COMMAND, pagination_handler)]},
        fallbacks=[CommandHandler('cancel', audio_cancel_handler)]
    )
    application.add_handler(login)
    application.add_handler(register)
    application.add_handler(ticket)
    application.add_handler(audio)
    application.add_handler(CallbackQueryHandler(cancel_callback))
    application.add_handler(CommandHandler('logout', logout_handler))
    application.add_handler(CommandHandler('push', push_message_handler))
    application.add_handler(CommandHandler('help', help_handler))
    application.add_handler(CommandHandler('sessions', sessions_handler))
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    tcp_server_thread = threading.Thread(target=run_tcp_server)
    tcp_server_thread.start()
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    run_telegram_bot()
