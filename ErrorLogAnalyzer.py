#!/usr/bin/env python
# coding=utf-8

#---------------------------------------------------------
# Name:         Tomcat错误日志发送邮件脚本
# Purpose:      收集Tomcat异常日志并发送邮件
# Version:      1.0
# Created:      2015-05-22
# Python：       2.7/2.4  皆可使用
#--------------------------------------------------------

from smtplib import SMTP
from email import MIMEText
from email import Header
from os.path import getsize
from sys import exit
from re import compile, IGNORECASE
from time import sleep
from socket import gethostbyname
from socket import gethostname


#定义主机 帐号 密码 收件人 邮件主题
smtpserver = 'smtp.126.com'
sender = 'reonard@126.com'
password = 'o8987378'
receiver = ('jinming.huang@cimc.com', 'bo.zhou.ds@cimc.com','huibing.liu@cimc.com','chunhua.huang@cimc.com', 'yongting.yang@cimc.com')
subject = u'--Web服务器Tomcat日志错误信息'
From = u'reonard@126.com'
To = u'jinming.huang@cimc.com'

#定义tomcat日志文件位置
tomcat_log = '/u01/ces/tomcat-7.0.59-interface/logs'

#该文件是用于记录上次读取日志文件的位置,执行脚本的用户要有创建该文件的权限
last_position_logfile = './last_position.index'

#匹配的错误信息关键字的正则表达式
pattern = compile(r'OutOfMemoryError|CommunicationsException|TimeOut|JedisConnectionException', IGNORECASE)
timepattern = compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')

# 发送邮件函数
def send_mail(error):

    #定义邮件的头部信息
    header = Header.Header
    msg = MIMEText.MIMEText(error, 'plain', 'utf-8')
    msg['From'] = header(From)
    msg['To'] = header(To)
    msg['Subject'] = header(subject+'\n')

    #连接SMTP服务器，然后发送信息
    smtp = SMTP(smtpserver)
    smtp.login(sender, password)
    smtp.sendmail(sender, receiver, msg.as_string())
    smtp.close()


#读取上一次日志文件的读取位置
def get_last_position(file):
    try:
        data = open(file,'r')
        last_position = data.readline()
        if last_position:
            last_position = int(last_position)
        else:
            last_position = 0
    except:
        last_position = 0

    return last_position

#写入本次日志文件的本次位置
def write_this_position(file, last_positon):
    try:
        data = open(file,'w')
        data.write(str(last_positon))
        data.write('\n' + "Don't Delete This File,It is Very important for Looking Tomcat Error Log !! \n")
        data.close()
    except:
        print "Can't Create File !" + file
        exit()

#分析文件找出异常的行
def analysis_log(file):

    error_list = []                                         #定义一个列表，用于存放错误信息.
    try:
        data = open(file, 'r')
    except:
        exit()
    last_position = get_last_position(last_position_logfile) #得到上一次文件指针在日志文件中的位置
    this_postion = getsize(tomcat_log)                      #得到现在文件的大小，相当于得到了文件指针在末尾的位置
    if last_position:
        if this_postion < last_position:                        #如果这次的位置 小于 上次的位置说明 日志文件轮换过了，那么就从头开始
            data.seek(0)
        elif this_postion == last_position:                     #如果这次的位置 等于 上次的位置 说明 还没有新的日志产生
            return ""
        elif this_postion > last_position:                      #如果是大于上一次的位置，就移动文件指针到上次的位置
            data.seek(last_position)
    else:
        data.seek(this_postion)

    for line in data:
        timematch = timepattern.search(line)
        if timematch:
            log_time = timematch.group(0)
        if pattern.search(line):
            error_list.append(log_time + " " + line)
    write_this_position(last_position_logfile, data.tell())  #写入本次读取的位置
    data.close()
    error_set_list = list(set(error_list))
    error_set_list.sort(key=error_list.index)

    return ''.join(error_set_list[0:5]) + "".join(error_set_list[-5:])        # 返回前5和后5个错误日志

#调用发送邮件函数发送邮件

if __name__ == "__main__":
    _hostname = gethostname()
    _hostIP = gethostbyname(_hostname)
    subject = "[Host]: " + _hostname + " [IP]: " + _hostIP + subject

    while True:
        error_info = analysis_log(tomcat_log)

        if error_info:
            print error_info
            send_mail(error_info)
            sleep(12000)
        sleep(5)
