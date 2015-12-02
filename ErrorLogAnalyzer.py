#!/usr/bin/env python
# coding=utf-8

#---------------------------------------------------------
# Name:         Tomcat错误日志发送邮件脚本
# Purpose:      收集Tomcat异常日志并发送邮件
# Version:      1.0
# Created:      2015-11-30
# Python：      2.7/2.4  皆可使用
#--------------------------------------------------------

from smtplib import SMTP
from email import MIMEText
from email import Header
from os.path import getsize
from re import compile, IGNORECASE
from time import sleep
from socket import gethostbyname
from socket import gethostname
from ConfigParser import ConfigParser
import Queue
from threadpool import ThreadPool, WorkRequest
import traceback
from threading import Lock
import logging

LOGFILE = "./runtimelog"
# 定义主机 帐号 密码 收件人 邮件主题
smtpserver = 'smtp.126.com'
sender = 'reonard@126.com'
password = 'o8987378'
subject = u'--Web服务器日志错误信息'
From = u'reonard@126.com'
To = u'jinming.huang@cimc.com'

# 定义配置文件的路径
# CONFIG_FILE = "./logAnalyzer.conf"
CONFIG_FILE = "C:\\test.ini"
PARAMS = ("name", "logfile", "scaninterval", "matchpattern", "timepattern", "mailreceiver")

# 定义一个队列，用于邮件发送线程获取多个扫描线程的错误日志
mail_queue = Queue.Queue()

# 定义一个互斥锁用于多个线程更新配置文件中的lastpos
mutex = Lock()

def init_logger():
    logger = logging.getLogger("RuntimeLog")
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)-6s: %(message)s', '%H:%M:%S %Y-%b-%d',)
    file_handler = logging.FileHandler(LOGFILE)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


# 发送邮件函数
def send_mail(**appconfs):
    global mail_queue, subject
    logger = logging.getLogger("RuntimeLog")
    logger.info("-----Email Thread Started-----")
    logger.info(appconfs)

    while True:
        # 从队列中获取邮件发送请求
        mailreq = mail_queue.get()

        # 获取app名称
        _app = mailreq.keys()[0]
        logger.info("Mailing received message from : %s" % _app)

        # 获取该app对应的错误日志信息
        error = mailreq[_app]
        logger.info("Received error message is %s" % error)

        # 从配置文件中获取该app对应的收件人
        receiver = appconfs[_app]["mailreceiver"]
        logger.info("Sending email to %s" % receiver)

        # 定义邮件的头部信息
        header = Header.Header
        msg = MIMEText.MIMEText(error, 'plain', 'utf-8')
        msg['From'] = header(From)
        msg['To'] = header(To)
        msg['Subject'] = header(subject+'\n')

        # 连接SMTP服务器，然后发送信息
        try:
            smtp = SMTP(smtpserver)
            smtp.login(sender, password)
            smtp.sendmail(sender, receiver.split(","), msg.as_string())
            logger.info("Email Sent")
            smtp.close()
        except:
            logger.error("%s cannot send email %s" % _app, error)

# 写入本次日志文件的本次位置
def write_this_position(_app, last_position):
    logger = logging.getLogger("RuntimeLog")
    _cf = ConfigParser()
    _cf.read(CONFIG_FILE)
    _cf.set(_app, "lastpos", last_position)
    logger.info("Writing Last position for %s - %s" % (_app, last_position))
    try:
        fp = open(CONFIG_FILE, 'w')
        _cf.write(fp)
    except:
        logger.error("Error Writing Conf File for app %s" % _app)
        raise RuntimeError("Error Writing Conf File")
    finally:
        fp.close()

# 分析文件找出异常的行

def analysis_log(*_app_section, **appconf):
    global mail_queue
    logger = logging.getLogger("RuntimeLog")
    _app = "".join(_app_section)
    logger.info("-----Scanner for %s started !-----" % _app)
    log_time = ""
    logfile = appconf["logfile"]

    pattern = compile(appconf["matchpattern"], IGNORECASE)
    timepattern = compile((appconf["timepattern"]))
    last_position = 0
    _scaninterval = int(appconf["scaninterval"])
    logger.info("Start Analyzing for app - %s, matchpattern is %s, timepattern is %s,\
    scaninterval is %s % (_app, appconf["matchpattern"], appconf["timepattern"], appconf["scaninterval"]))

    while True:
        error_list = []                                         #定义一个列表，用于存放错误信息.

        try:
            data = open(logfile, 'r')
        except:
            logger.error("can not open log file for app - %s", _app)
            raise RuntimeError("can not open log file")

        this_position = getsize(logfile)                   # 得到现在文件的大小，相当于得到了文件指针在末尾的位置

        if last_position:
            if this_position < last_position:              # 如果这次的位置 小于 上次的位置说明日志文件轮换过了，那么就从头开始
                data.seek(0)
            elif this_position == last_position:           # 如果这次的位置 等于 上次的位置说明还没有新的日志产生
                sleep(_scaninterval)
                continue
            elif this_position > last_position:            # 如果是大于上一次的位置，就移动文件指针到上次的位置
                data.seek(last_position)
        else:
            data.seek(this_position)

        for line in data:
            timematch = timepattern.search(line)
            if timematch:
                log_time = timematch.group(0)
            if pattern.search(line):
                error_list.append(log_time + " " + line)

        last_position = data.tell()

        # if mutex.acquire():          # 获取锁写入本次读取的位置
        #     try:
        #         write_this_position(_app, data.tell())
        #     except:
        #         logger.error("Can't Write Last position %s for app %s !" % (data.tell(), _app))
        #         raise RuntimeError("Can't Write Last position !" + _app)
        #     finally:
        #         mutex.release()

        data.close()
        error_set_list = list(set(error_list))
        error_set_list.sort(key=error_list.index)

        error_msg = ''.join(error_set_list[0:5]) + "".join(error_set_list[-5:])     # 生成前5和后5个错误日志
        if error_msg:
            logger.info("Sending error into queue for app - %s" % _app)
            mail_queue.put({_app: error_msg})   # 将错误信息投入邮件队列发送
            sleep(900)
        sleep(_scaninterval)

# 扫描线程异常回调函数
def scanStop(request, exc_info):
    logger = logging.getLogger("RuntimeLog")
    logger.error("-----Scan worker for App %s has terminated !-----" % request.kwds['name'])
    traceback.print_exception(*exc_info)

# 邮件发送线程异常回调函数
def mailStop(request, exc_info):
    logger = logging.getLogger("RuntimeLog")
    logger.error("-----MailSender has terminated !-----")
    traceback.print_exception(*exc_info)

if __name__ == "__main__":

    params = {}
    workers = []     # 线程池工作请求队列，包含扫描和邮件发送队列
    scanworkers = []   # 日志扫描分析队列
    mailqueue = Queue.Queue()
    init_logger()
    logger = logging.getLogger("RuntimeLog")

    try:
        cf = ConfigParser()
        cf.read(CONFIG_FILE)
    except:
        print "Could not get config !"
        exit(-1)

    _hostname = cf.get("HostInfo", "HostIp")
    _hostIP = cf.get("HostInfo", "HostName")
    subject = "[Host]: " + _hostname + " [IP]: " + _hostIP + subject
    print "Main Engine Start ..."
    logger.info("Main Engine Start ...")
    logger.info("HostIp is %s, HostName is %s" % (_hostIP, _hostname))

    apps = cf.sections()
    apps.remove("HostInfo")
    if len(apps) == 0:
        print "No App Defined, Check Conf File!"
        exit(-1)

    logger.info("Prepare analyzing for apps - %s", ",".join(apps))

    # 创建线程池，和配置文件中的app数量一致，加多一个邮件发送线程
    pool = ThreadPool(len(apps)+1)

    for app in apps:
        params[app] = dict(cf.items(app))
        for param in PARAMS:
            if param not in params[app].keys():
                print "No param %s defined for %s, check conf file" % (param, app)
                exit(-1)

        # 创建文件扫描worker，之后加入workers列表
        scanworkers.append(WorkRequest(analysis_log, (app,), params[app], exc_callback=scanStop))

    workers.extend(scanworkers)
    # 创建邮件发送worker，并加入workers列表
    mailsender = WorkRequest(send_mail, None, params, exc_callback=mailStop)
    workers.append(mailsender)

    # 投放worker请求，等待线程结束（扫描线程和邮件线程永不会结束）
    for req in workers:
        pool.putRequest(req)
    pool.wait()
