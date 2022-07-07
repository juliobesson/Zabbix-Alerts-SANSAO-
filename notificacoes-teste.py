#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Envio de gráfico por WhatsApp, Telegram e Email através do ZABBIX (Send zabbix alerts graph WhatsApp, Telegram e Mail)
#
# Copyright (C) <2016>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Contacts:
# Eracydes Carvalho (Sansão Simonton) - Monitoring Specialist - Telegram: @sansaoipb
# Thiago Paz - NOC Analyst - thiagopaz1986@gmail.com

pythonVersion = 3.6
import os, sys, re, json, time, smtplib

if len(sys.argv) == 1:
    sys.argv.append("-h")

try:
    if float(".".join(sys.version.split(" ", 1)[0].split(".")[:-1])) < pythonVersion:
        print(
            "\nA versão apontada para o '/usr/bin/python3' é \"{}\".\nInstale/Atualize/Aponte para o {} ou superior e reexecute o comando:\n\ncd /tmp ; wget https://raw.githubusercontent.com/sansaoipb/scripts/master/notificacoes.sh -O notificacoes.sh ; sudo dos2unix notificacoes.sh ; sudo bash notificacoes.sh\n".format(
                sys.version.split(" ", 1)[0], pythonVersion))
        exit(1)
    import requests, urllib3
    from pyrogram import Client

except Exception as e:
    if "No module" in e.args[0]:
        print(
            "\nErro: {}\n\nExecute o comando:\n\nsudo -H -u zabbix python3 -m pip install wheel requests urllib3 pyrogram tgcrypto pycryptodome --user\n".format(
                e.args[0]))

    else:
        print("{}".format(e.args[0]))
    exit(2)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import argparse

import configparser

conf = configparser

import base64
from urllib.parse import quote

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto import Random


class PropertiesReaderX:
    config = None

    def __init__(self, pathToProperties):
        PropertiesReaderX.config = conf.RawConfigParser()
        PropertiesReaderX.config.read(pathToProperties)

    def getValue(self, section, key):
        # type: (object, object) -> object
        return PropertiesReaderX.config.get(section, key)


path = "{0}".format("/".join(sys.argv[0].split("/")[:-1]) + "/{0}")

if sys.platform.startswith('win32') or sys.platform.startswith('cygwin') or sys.platform.startswith(
        'darwin'):  # para debug quando estiver no WINDOWS ou no MAC
    graph_path = os.getcwd()

else:
    graph_path = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionTelegram',
                                                                                     'path.graph')  # Path where graph file will be save temporarily

# Zabbix settings | Dados do Zabbix ####################################################################################
zbx_server = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'url')
zbx_user = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'user')
zbx_pass = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'pass')

# Graph settings | Configuracao do Grafico #############################################################################
height = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection',
                                                                             'height')  # Graph height | Altura
width = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection',
                                                                            'width')  # Graph width  | Largura

# Salutation | Saudação ################################################################################################
Salutation = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'salutation')
if re.search("(sim|s|yes|y)", str(Salutation).lower()):
    hora = int(time.strftime("%H"))

    if hora < 12:
        salutation = 'Bom dia'
    elif hora >= 18:
        salutation = 'Boa noite'
    else:
        salutation = 'Boa tarde'
else:
    salutation = ""

if zbx_server.endswith("/"):
    zbx_server = zbx_server[:-1]


def keepass(value=None):
    import random
    char = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890!@#-_=+,.;:?"
    passwd = ""
    if value:
        char1 = value
    else:
        char1 = len(char)

    while len(passwd) != char1:
        passwd += random.choice(char)
    return passwd


def encrypt(key, source, encode=True):
    source = source.encode("ISO-8859-1")
    key = SHA256.new(key.encode("ISO-8859-1")).digest()  # use SHA-256 over our key to get a proper-sized AES key
    IV = Random.new().read(AES.block_size)  # generate IV
    encryptor = AES.new(key, AES.MODE_CBC, IV)
    padding = AES.block_size - len(source) % AES.block_size  # calculate needed padding
    source += bytes([padding]) * padding  # Python 2.x: source += chr(padding) * padding
    data = IV + encryptor.encrypt(source)  # store the IV at the beginning and encrypt
    return base64.b64encode(data).decode("ISO-8859-1") if encode else data


def decrypt(key, source, decode=True):
    if decode:
        source = base64.b64decode(source.encode("ISO-8859-1"))
    key = SHA256.new(key.encode("ISO-8859-1")).digest()  # use SHA-256 over our key to get a proper-sized AES key
    IV = source[:AES.block_size]  # extract the IV from the beginning
    decryptor = AES.new(key, AES.MODE_CBC, IV)
    data = decryptor.decrypt(source[AES.block_size:])  # decrypt
    padding = data[-1]  # pick the padding value from the end; Python 2.x: ord(data[-1])
    if data[-padding:] != bytes([padding]) * padding:  # Python 2.x: chr(padding) * padding
        raise ValueError("Invalid padding...")
    return data[:-padding].decode("ISO-8859-1")  # remove the padding


def load_json(File):
    with open(File, 'r') as f:
        return json.load(f)


def write_json(fileName, Json):
    with open(fileName, 'w') as f:
        json.dump(Json, f, ensure_ascii=False, indent=True)


# Diretórios

# Log path | Diretório do log
projeto = sys.argv[0].split("/")[-1:][0].split(".")[0]
logName = '{0}.log'.format(projeto)
pathLogs = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'path.logs')

if "default" == pathLogs.lower():
    pathLogs = path.format("log")

arqLog = "{0}".format(os.path.join(pathLogs, logName))

if not os.path.exists(pathLogs):
    os.makedirs(pathLogs)

########################################################################################################################
########################################################################################################################
########################################################################################################################
########################################################################################################################
arqJson = ".env.json"
fileX = os.path.join(pathLogs, arqJson)
fileC = """{
    "code": false,
    "email": {
            "smtp.server": false,
            "mail.user": false,
            "mail.pass": false
    },
    "telegram": {
            "api.id": false,
            "api.hash": false
    },
    "whatsapp": {
        "line": false,
        "acess.key": false,
        "port": false
    }
}"""

if os.path.exists(fileX):
    filOutX = os.popen(f"cat {fileX}").read().replace("acessKey", "acess.key")
    write_json(fileX, json.loads(filOutX))

arqConfig = path.format('configScripts.properties')
configDefault = """[PathSection]
url = http://127.0.0.1/zabbix
user = Admin
pass = zabbix
height = 200
width = 900
stime = 3600
ack = yes
salutation = yes
path.logs = Default

[PathSectionEmail]
salutation.email = yes
message.email = Email enviado com sucesso
mail.from = ZABBIX Monitoring <monitoring@zabbix.com>
smtp.server = smtp.gmail.com:587
mail.user = SeuEmail@gmail.com
mail.pass = SuaSenha

[PathSectionTelegram]
salutation.telegram = yes
message.telegram = Telegram enviado com sucesso
path.graph = /tmp
api.id = 1234567
api.hash = 12asdc64vfda19df165asdvf984dbf45

[PathSectionWhatsApp]
salutation.whatsapp = yes
message.whatsapp = WhatsApp enviado com sucesso
cod.ddi = 55
line = 5511950287353
acess.key = XGja6Sgtz0F01rbWNDTc
port = 13008"""

if not os.path.exists(arqConfig):
    contArq = configDefault
    # os.popen(f"cat > {pathConfig} << EOF\n{configDefault} \nEOF")

else:
    fileIn = f"{configDefault}".split("\n")
    fileOut = os.popen(f"cat {arqConfig}").read().replace("email_from", "mail.from").replace("email.from",
                                                                                             "mail.from").replace(
        "smtp_server", "smtp.server").replace("mail_", "mail.").replace("acessKey", "acess.key")
    contArq = ""
    for lineIn in fileIn:
        linhaIn = re.search(f"(^[a-z.]+) ?= ?(.*)", lineIn)
        if linhaIn:
            keyIn = linhaIn.group(1).rstrip()
            valueOut = re.search(f"\n({keyIn}) ?= ?(.*)", fileOut)
            if valueOut:
                keyOut = valueOut.group(1).split("=")[0].strip().rstrip()
                if keyIn == keyOut:
                    # valueOut = re.search(f"\n({keyIn}) ?= ?(.*)", fileOut).group().strip()
                    valueOut = valueOut.group().strip()
                    if " = " not in valueOut:
                        valueOut = valueOut.replace('=', ' = ')
                    contArq += f"{valueOut}\n"

            else:
                contArq += f"{lineIn}\n"
            continue

        contArq += f"{lineIn}\n"
        continue

    contArq = f"{contArq.rstrip()}\n\n"

arquivo = open(f"{arqConfig}", "w")
arquivo.writelines(contArq)
arquivo.close()

import logging.config
import traceback

file = """{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "simple": {
            "format": "[%(asctime)s][%(levelname)s] - %(message)s"
        }
    },

    "handlers": {
        "file_handler": {
            "class": "logging.handlers.RotatingFileHandler",
            "maxBytes": 5242880,
            "backupCount":5,
            "level": "INFO",
            "formatter": "simple",
            "filename": "python_logging.log",
            "encoding": "utf8"
        }
    },

    "root": {
        "level": "INFO",
        "handlers": ["file_handler"]
    }
}
"""

arqConfig = "logging_configuration.json"
pathDefault = ""


class Log:
    @staticmethod
    def writelog(entry, pathfile, log_level):
        global pathDefault

        try:
            Log.log(entry, pathfile, log_level)
        except Exception:
            try:
                # if "\\" in traceback.format_exc():
                #     linha = re.search("(File)[A-Za-z0-9_\"\\\\\s:.]+", traceback.format_exc()).group()[5:].replace("\"", "")
                #     pathDefault = "{0}\\log\\".format("\\".join(linha.split("\\")[:-1]))
                # else:
                #     linha = re.search("(File)[A-Za-z0-9_\"/\s:.]+", traceback.format_exc()).group()[5:].replace("\"", "")
                #     pathDefault = "{0}/log/".format("/".join(linha.split("/")[:-1]))

                pathDefault = f"{pathLogs}/"
                arquivo = open("{0}{1}".format(pathDefault, arqConfig), "w")
                arquivo.writelines(file)
                arquivo.close()
                Log.log(entry, pathfile, log_level)
            except Exception:
                pass

    @staticmethod
    def log(entry, pathfile, log_level):
        logging.getLogger('suds.client').setLevel(logging.CRITICAL)
        logging.getLogger('suds.wsdl').setLevel(logging.CRITICAL)
        with open("{0}{1}".format(pathDefault, arqConfig), 'r+') as logging_configuration_file:
            config_dict = json.load(logging_configuration_file)
            config_dict["handlers"]["file_handler"]['filename'] = pathfile
        logging.config.dictConfig(config_dict)
        logger = logging.getLogger(__name__)
        logging.getLogger("suds").setLevel(logging.CRITICAL)

        if log_level.upper() == "INFO":
            logger.info(str(entry))
        elif log_level.upper() == "WARNING":
            logger.warning(str(entry))
        elif log_level.upper() == "CRITICAL":
            logger.critical(str(entry))
        elif log_level.upper() == "ERROR":
            logger.error(str(entry))


log = Log

nograph = "--nograph"


def destinatarios(dest):
    destinatario = ["{0}".format(hostsW).strip().rstrip() for hostsW in dest.split(",")]
    return destinatario


def send_mail(dest, itemType, get_graph, key):
    # Mail settings | Configrações de e-mail ###########################################################################
    mail_from = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionEmail', 'mail.from')
    smtp_server0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionEmail',
                                                                                       'smtp.server')
    mail_user0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionEmail', 'mail.user')
    mail_pass0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionEmail', 'mail.pass')
    ####################################################################################################################

    try:
        smtp_server = decrypt(key, smtp_server0)
    except:
        smtp_server = smtp_server0

    try:
        mail_user = decrypt(key, mail_user0)
    except:
        mail_user = mail_user0

    try:
        mail_pass = decrypt(key, mail_pass0)
    except:
        mail_pass = mail_pass0

    try:
        mail_from = email.utils.formataddr(tuple(mail_from.replace(">", "").split(" <")))
    except:
        mail_from = mail_from

    dests = ', '.join(dest)
    msg = body
    msg = msg.replace("\\n", "").replace("\n", "<br>")
    try:
        Subject = re.sub(r"(<(\/)?[a-z]>)", "", subject)
    except:
        Subject = subject

    msgRoot = MIMEMultipart('related')
    msgRoot['Subject'] = Subject
    msgRoot['From'] = mail_from
    msgRoot['To'] = dests

    msgAlternative = MIMEMultipart('alternative')
    msgRoot.attach(msgAlternative)

    saudacao = salutation
    if saudacao:
        saudacao = "<p>{0},</p>".format(salutation)
    else:
        saudacao = ""

    text = '{0}<p>{1}</p>'.format(saudacao, msg)

    if re.search("(0|3)", itemType):
        URL = urlGraph.replace("width=900&height=200", "width=1400&height=300")
        text += f'<br><a href="{URL}"><img src="cid:image1"></a>'
        msgImage = MIMEImage(get_graph.content)
        msgImage.add_header('Content-ID', '<image1>')
        msgRoot.attach(msgImage)

    msgText = MIMEText(text, 'html', _charset='utf-8')
    msgAlternative.attach(msgText)

    try:
        smtp = smtplib.SMTP(smtp_server)
        smtp.ehlo()

        try:
            smtp.starttls()
        except Exception:
            pass

        try:
            smtp.login(mail_user, mail_pass)
        except smtplib.SMTPAuthenticationError as msg:
            print("Error: Unable to send email | Não foi possível enviar o e-mail - {0}".format(
                msg.smtp_error.decode("utf-8").split(". ")[0]))
            log.writelog('Error: Unable to send email | Não foi possível enviar o e-mail - {0}'.format(
                msg.smtp_error.decode("utf-8").split(". ")[0]), arqLog, "WARNING")
            smtp.quit()
            exit()
        except smtplib.SMTPException:
            pass

        try:
            smtp.sendmail(mail_from, dest, msgRoot.as_string())
        except Exception as msg:
            print("Error: Unable to send email | Não foi possível enviar o e-mail - {0}".format(
                msg.smtp_error.decode("utf-8").split(". ")[0]))
            log.writelog('Error: Unable to send email | Não foi possível enviar o e-mail - {0}'.format(
                msg.smtp_error.decode("utf-8").split(". ")[0]), arqLog,
                         "WARNING")
            smtp.quit()
            exit()

        print("Email sent successfully | Email enviado com sucesso ({0})".format(dests))
        log.writelog('Email sent successfully | Email enviado com sucesso ({0})'.format(dests), arqLog, "INFO")
        smtp.quit()
    except smtplib.SMTPException as msg:
        print("Error: Unable to send email | Não foi possível enviar o e-mail ({0})".format(msg))
        log.writelog('Error: Unable to send email | Não foi possível enviar o e-mail ({0})'.format(msg), arqLog,
                     "WARNING")
        logout_api()
        smtp.quit()
        exit()


def send_telegram(dest, itemType, get_graph, key, triggerid):
    # Telegram settings | Configuracao do Telegram #####################################################################
    api_id0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionTelegram', 'api.id')
    api_hash0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionTelegram', 'api.hash')
    ####################################################################################################################

    try:
        api_id = int(decrypt(key, api_id0))
    except:
        api_id = api_id0

    try:
        api_hash = str(decrypt(key, api_hash0))
    except:
        api_hash = api_hash0

    app = Client("SendGraph", api_id=api_id, api_hash=api_hash)

    dest = dest.lower()
    saudacao = salutation
    if saudacao:
        # saudacao = salutation + " {0} \n\n"
        saudacao = salutation + " <b><u>{0}</u></b> \n\n"
    else:
        saudacao = ""

    if re.search("user#|chat#|\'|\"", dest):
        if "#" in dest:
            dest = dest.split("#")[1]

        elif dest.startswith("\"") or dest.startswith("\'"):
            dest = dest.replace("\"", "").replace("\'", "")

    elif dest.startswith("@"):
        dest = dest[1:]

    with app:
        flag = True
        while flag:
            try:
                Contatos = app.get_contacts()
                for contato in Contatos:
                    Id = f"{contato.id}"
                    nome = f"{contato.first_name}"
                    if contato.last_name:
                        nome += f" {contato.last_name}"

                    username = contato.username.lower()
                    if username:
                        if username in dest or dest in Id or dest in nome.lower():
                            dest = nome
                            flag = False
                            break
                    else:
                        if dest in Id or dest in nome.lower():
                            dest = nome
                            flag = False
                            break
            except:
                pass

            try:
                if flag:
                    Dialogos = app.iter_dialogs()
                    for dialogo in Dialogos:
                        Id = f"{dialogo.chat.id}"
                        if dialogo.chat.title:
                            nome = f"{dialogo.chat.title}"
                        else:
                            nome = f"{dialogo.chat.first_name}"
                            if dialogo.chat.last_name:
                                nome += f" {dialogo.chat.last_name}"

                        username = dialogo.chat.username
                        if username:
                            if username in dest or dest in Id or dest in nome.lower():
                                dest = nome
                                flag = False
                                break
                        else:
                            if dest in Id or dest in nome.lower():
                                dest = nome
                                flag = False
                                break
            except:
                flag = False
                try:
                    if re.match("^([0-9-]+)$", dest):
                        dest = int(dest)
                    chat = app.get_chat(dest)
                    Id = "{}".format(chat.id)

                    if chat.title:
                        dest = f"{chat.title}"
                    else:
                        dest = f"{chat.first_name}"
                        if chat.last_name:
                            dest += f" {chat.last_name}"

                except Exception as msg:
                    print(msg.args[0])
                    log.writelog(f'{msg.args[0]}', arqLog, "ERROR")
                    exit()

        Id = int(Id)
        sendMsg = """{}{}\n{}""".format(saudacao.format(dest), subject, body)
        if re.search("(0|3)", itemType):
            try:
                graph = '{0}/{1}.png'.format(graph_path, triggerid)
                with open(graph, 'wb') as png:
                    png.write(get_graph.content)
            except BaseException as e:
                log.writelog(
                    '{1} >> An error occurred at save graph file in {0} | Ocorreu um erro ao salvar o grafico no diretório {0}'.format(
                        graph_path, str(e)), arqLog, "WARNING")
                logout_api()
                exit()

            try:
                app.send_photo(Id, graph, caption=sendMsg)
                print(
                    'Telegram sent photo message successfully | Telegram com gráfico enviado com sucesso ({0})'.format(
                        dest))
                log.writelog(
                    'Telegram sent photo message successfully | Telegram com gráfico enviado com sucesso ({0})'.format(
                        dest), arqLog, "INFO")
            except Exception as e:
                print(
                    'Telegram FAIL at sending photo message | FALHA ao enviar mensagem com gráfico pelo telegram\n%s' % e)
                log.writelog(
                    '{0} >> Telegram FAIL at sending photo message | FALHA ao enviar mensagem com gráfico pelo telegram ({1})'.format(
                        e, dest), arqLog, "ERROR")
                logout_api()
                exit()

            try:
                os.remove(graph)
            except Exception as e:
                print(e)
                log.writelog('{0}'.format(str(e)), arqLog, "ERROR")

        else:
            try:
                app.send_message(Id, sendMsg)
                print('Telegram sent successfully | Telegram enviado com sucesso ({0})'.format(dest))
                log.writelog('Telegram sent successfully | Telegram enviado com sucesso ({0})'.format(dest), arqLog,
                             "INFO")
            except Exception as e:
                print('Telegram FAIL at sending message | FALHA ao enviar mensagem pelo telegram\n%s' % e)
                log.writelog(
                    '{0} >> Telegram FAIL at sending message | FALHA ao enviar mensagem pelo telegram ({1})'.format(e,
                                                                                                                    dest),
                    arqLog, "ERROR")
                logout_api()
                exit()


def send_whatsapp(destiny, itemType, get_graph, key):
    # WhatsApp settings | Configuracao do WhatsApp #####################################################################
    line0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionWhatsApp', 'line')
    acessKey0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionWhatsApp', 'acess.key')
    port0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionWhatsApp', 'port')
    ####################################################################################################################

    try:
        line = decrypt(key, line0)
    except:
        line = line0

    try:
        acessKey = decrypt(key, acessKey0)
    except:
        acessKey = acessKey0

    try:
        port = decrypt(key, port0)
    except:
        port = port0

    saudacao = salutation
    Saudacao = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionWhatsApp',
                                                                                   'salutation.whatsapp')

    if re.search("(sim|s|yes|y)", str(Saudacao).lower()):
        if saudacao:
            saudacao = salutation + ".\\n\\n"
    else:
        saudacao = ""

    msg0 = body.replace("\r", "").split('\n ')[0].replace("\n", "\\n")
    msg = "{}\\n{}".format(subject.replace(r"✅", r"\u2705"), msg0)
    message0 = "{}{}".format(saudacao, msg)

    valida = 0
    message1 = ""
    formatter = [("b", "*"), ("i", "_"), ("u", "")]
    for f in formatter:
        old, new = f
        if re.search(r"(<(/)?{}>)".format(old), message0):
            message1 = re.sub(r"(<(/)?{}>)".format(old), r"{}".format(new), message0)
            valida += 1

    if valida == 0:
        message1 = message0

    message = quote(base64.b64encode(message1.encode("utf-8")))
    if re.search("(0|3)", itemType):
        Graph = quote(base64.b64encode(get_graph.content))  # .decode("ISO-8859-1"))
        try:
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            payload = 'app=NetiZap%20Consumers%201.0&key={key}&text={text}&type=PNG&stream={stream}&filename=grafico'.format(
                key=acessKey, text=message, stream=Graph)
            url = "http://api.meuaplicativo.vip:{port}/services/file_send?line={line}&destiny={destiny}".format(
                port=port, line=line, destiny=destiny)
            result = requests.post(url, auth=("user", "api"), headers=headers, data=payload)

            if result.status_code != 200:
                error = json.loads(result.content.decode("utf-8"))['errors'][0]['message']
                # error = result.content.decode("utf-8")
                log.writelog('{0}'.format(error), arqLog, "ERROR")
                print(
                    'WhatsApp FAIL at sending photo message | FALHA ao enviar mensagem com gráfico pelo WhatsApp\n%s' % error)

            else:
                print(
                    'WhatsApp sent photo message successfully | WhatsApp com gráfico enviado com sucesso ({0})'.format(
                        destiny))
                log.writelog(
                    'WhatsApp sent photo message successfully | WhatsApp com gráfico enviado com sucesso ({0})'.format(
                        destiny), arqLog, "INFO")
                log.writelog('{0}'.format(json.loads(result.text)["result"]), arqLog, "INFO")
        except Exception as e:
            print(e)
            log.writelog('{0}'.format(str(e)), arqLog, "ERROR")
            exit()
    else:
        try:
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            payload = 'App=NetiZap%20Consumers%201.0&AccessKey={}'.format(acessKey)
            url = "http://api.meuaplicativo.vip:{port}/services/message_send?line={line}&destiny={destiny}&reference&text={text}".format(
                port=port, line=line, destiny=destiny, text=message)
            result = requests.post(url, auth=("user", "api"), headers=headers, data=payload)

            if result.status_code != 200:
                error = json.loads(result.content.decode("utf-8"))['errors'][0]['message']
                # error = result.content.decode("utf-8")
                log.writelog('{0}'.format(error), arqLog, "ERROR")
                print('WhatsApp FAIL at sending message | FALHA ao enviar a mensagem pelo WhatsApp\n%s' % error)

            else:
                print('WhatsApp sent successfully | WhatsApp enviado com sucesso ({0})'.format(destiny))
                log.writelog('WhatsApp sent successfully | WhatsApp enviado com sucesso ({0})'.format(destiny), arqLog,
                             "INFO")
                log.writelog('{0}'.format(json.loads(result.text)["result"]), arqLog, "INFO")
        except Exception as e:
            print(e)
            log.writelog('{0}'.format(str(e)), arqLog, "ERROR")
            exit()


def token():
    try:
        login_api = requests.post(f'{zbx_server}/api_jsonrpc.php', headers={'Content-type': 'application/json'},
                                  verify=False, data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "user.login",
                    "params": {
                        "user": zbx_user,
                        "password": zbx_pass
                    },
                    "id": 1
                }
            )
                                  )

        login_api = json.loads(login_api.text.encode('utf-8'))

        if 'result' in login_api:
            auth = login_api["result"]
            return auth

        elif 'error' in login_api:
            print('Zabbix: %s' % login_api["error"]["data"])
            log.writelog('Zabbix: {0}'.format(login_api["error"]["data"]), arqLog, "ERROR")
            exit()
        else:
            print(login_api)
            log.writelog('{0}'.format(login_api), arqLog, "ERROR")
            exit()

    except ValueError as e:
        print(
            'Check declared zabbix URL/IP and try again | Valide a URL/IP do Zabbix declarada e tente novamente\nCurrent: %s' % zbx_server)
        log.writelog(
            'Check declared zabbix URL/IP and try again | Valide a URL/IP do Zabbix declarada e tente novamente. (Current: {0})'.format(
                zbx_server), arqLog, "WARNING")
        exit()
    except Exception as e:
        print(e)
        log.writelog('{0}'.format(str(e)), arqLog, "WARNING")
        exit()


def version_api():
    resultado = requests.post(f'{zbx_server}/api_jsonrpc.php', headers={'Content-type': 'application/json'},
                              verify=False, data=json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "apiinfo.version",
                "params": [],
                "id": 5
            }
        )
                              )
    resultado = json.loads(resultado.content)
    if 'result' in resultado:
        resultado = resultado["result"]
    return resultado


def logout_api():
    requests.post(f'{zbx_server}/api_jsonrpc.php', headers={'Content-type': 'application/json'},
                  verify=False, data=json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "user.logout",
                "params": [],
                "auth": auth,
                "id": 4
            }
        )
                  )


def getgraph(period):
    global urlGraph
    # Graph start time [3600 = 1 hour ago]  |  Hora inicial do grafico [3600 = 1 hora atras]
    stime = int(PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSection', 'stime'))
    dictCores = {
        'FF0000': [
            'FF0000',
            'C71585',
            'FFA500',
            'FF1493',
            'FFC0CB',
            'CD5C5C',
            '8B0000',
            'FFD700',
            '800080',
            'DA70D6',
            'FA8072',
            'FF69B4',
            'DB7093',
            'FFB6C1',
            'FF00FF',
            'EE82EE',
            'FF6347',
            'F08080',
            'B22222',
            'DC143C',
        ],
        '00C800': [
            '008000',
            '00FF00',
            '6B8E23',
            '0000FF',
            '00FFFF',
            '4169E1',
            '7FFFD4',
            '32CD32',
            '708090',
            '00FF7F',
            '66CDAA',
            '40E0D0',
            '008B8B',
            '00BFFF',
            '4682B4',
            'B0C4DE',
            '2E8B57',
            '9ACD32',
            '98FB98',
            '90EE90'
        ]
    }

    try:
        loginpage = requests.get(f'{zbx_server}/index.php', auth=(zbx_user, zbx_pass), verify=False).text
        enter = re.search('<button.*value=".*>(.*?)</button>', loginpage)
        s = requests.Session()

        try:
            enter = str(enter.group(1))
            s.post(f'{zbx_server}/index.php?login=1', params={'name': zbx_user, 'password': zbx_pass, 'enter': enter},
                   verify=False).text
        except:
            pass

        stime = time.strftime("%Y%m%d%H%M%S", time.localtime(time.time() - stime))

        if 4.0 > float(version_api()[:3]):
            period = "period={0}".format(period)
            nome_tempo = f"{{}}"

        else:
            periodD = period // 86400
            segundos_rest = period % 86400
            periodH = segundos_rest // 3600
            segundos_rest = segundos_rest % 3600
            periodM = segundos_rest // 60
            periodS = segundos_rest % 60

            Nome = f"{triggerName} {{}}"
            if periodD > 0:
                period = "from=now-{0}d-{1}h-{2}m&to=now".format(periodD, periodH, periodM)
                nome_tempo = Nome.format(f"({periodD}d {periodH}h:{periodM}m)")

            elif periodD == 0 and periodH == 0:
                period = "from=now-{0}m&to=now".format(periodM)
                nome_tempo = Nome.format(f"({periodM}m)")

            elif periodD == 0 and period % 60 == 0:
                period = "from=now-{0}h&to=now".format(periodH)
                nome_tempo = Nome.format(f"({periodH}h)")

            else:
                period = "from=now-{0}h-{1}m&to=now".format(periodH, periodM)
                nome_tempo = Nome.format(f"({periodH}h:{periodM}m)")

        urlGraph = f"{zbx_server}/chart3.php?name={hostName}: {nome_tempo}&{period}&width={width}&height={height}&stime={stime}"

        j = 0
        for i in range(len(listaItemIds)):
            try:
                cor = dictCores[color][i]
            except:
                if j == len(dictCores['00C800']):
                    j = 0
                cor = dictCores[color][j]
                j += 1

            urlGraph += f"&items[{i}][itemid]={listaItemIds[i]}&items[{i}][drawtype]=5&items[{i}][color]={cor}"

        get_graph = s.get(urlGraph)
        sid = s.cookies.items()[0][1]
        s.post(f'{zbx_server}/index.php?reconnect=1&sid={sid}')

        return get_graph

    except BaseException:
        log.writelog(
            'Can\'t connect to {0}/index.php | Não foi possível conectar-se à {0}/index.php'.format(zbx_server), arqLog,
            "CRITICAL")
        logout_api()
        exit()


def getTrigger(triggerId=None):
    try:
        limit = 8000
        triggerid = requests.post(f'{zbx_server}/api_jsonrpc.php', headers={'Content-type': 'application/json'},
                                  verify=False, data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "trigger.get",
                    "params": {
                        "output": ["description"],
                        'triggerids': triggerId,
                        "limit": limit,
                        "selectItems": ['name', 'value_type', 'lastvalue'],
                        "selectHosts": ["name"],
                        "expandDescription": True,
                    },
                    "auth": auth,
                    "id": 3
                }
            )
                                  )

        if triggerid.status_code != 200:
            print(f"HTTPError {triggerid.status_code}: {triggerid.reason}")
            log.writelog(f'HTTPError {triggerid.status_code}: {triggerid.reason}', arqLog, "WARNING")
            logout_api()
            exit()

        resultTriggers = triggerid.content
        if not resultTriggers:
            print('User has no read permission on environment | Usuário sem permissão de leitura no ambiente')
            log.writelog('User has no read permission on environment | Usuário sem permissão de leitura no ambiente',
                         arqLog, "WARNING")
            logout_api()
            exit()

        triggerid = json.loads(resultTriggers)

        item_type = ""
        if 'result' in triggerid:
            resultado = triggerid["result"]

            if triggerId:
                hostName = triggerid["result"][0]['hosts'][0]['name']
                triggerName = triggerid["result"][0]['description']
                triggerID = triggerid["result"][0]['triggerid']

                for i in range(0, len(resultado)):
                    listaItemIds = []
                    for items in resultado[i]['items']:
                        if items['lastvalue'] != '0' and items['lastvalue']:
                            if items['itemid'] not in listaItemIds:
                                listaItemIds.append(items['itemid'])

                            if not item_type:
                                item_type += items['value_type']

                    return (item_type, triggerName, triggerID, hostName, listaItemIds)

            else:
                for i in range(0, len(resultado)):
                    hostName = resultado[i]['hosts'][0]['name']
                    triggerName = resultado[i]['description']
                    triggerID = resultado[i]['triggerid']
                    listaItemIds = []
                    for items in resultado[i]['items']:
                        if items['lastvalue'] != '0' and re.match("(0|3)", items['value_type']):
                            listaItemIds.append(items['itemid'])

                            if not item_type:
                                item_type += items['value_type']

                    if listaItemIds:
                        return (item_type, triggerName, triggerID, hostName, listaItemIds)

        elif 'error' in triggerid:
            print('Zabbix: %s' % triggerid["error"]["data"])
            log.writelog('Zabbix: {0}'.format(triggerid["error"]["data"]), arqLog, "ERROR")
            exit()

        else:
            print(triggerid)
            log.writelog('{0}'.format(triggerid), arqLog, "ERROR")
            exit()

    except Exception as msg:
        print(msg)
        log.writelog('{0}'.format(msg), arqLog, "ERROR")
        exit()


def get_info(name=None):
    # Telegram settings | Configuracao do Telegram #########################################################################
    api_id0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionTelegram', 'api.id')
    api_hash0 = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionTelegram', 'api.hash')

    try:
        api_id = int(decrypt(codeKey, api_id0))
    except:
        api_id = api_id0

    try:
        api_hash = str(decrypt(codeKey, api_hash0))
    except:
        api_hash = api_hash0

    app = Client("SendGraph", api_id=api_id, api_hash=api_hash)
    ContA = 0
    with app:
        infos = ""
        try:
            dialogos = app.iter_dialogs()
        except Exception as msg:
            if "BOT" in msg.args[0]:
                print("\nEsta função não está disponível para consultas com BOT\n")
            else:
                print(msg.args[0])

            log.writelog('{0}'.format(msg.args[0]), arqLog, "ERROR")
            exit()

        infos += ""
        if name:
            for dialogo in dialogos:
                tipos = {"group": "Grupo", "supergroup": "Super Grupo", "bot": "BOT", "channel": "Canal",
                         "private": "Usuário"}
                tipo = f"Tipo: {tipos[dialogo.chat.type]}"
                Id = f"Id: {dialogo.chat.id}"
                if dialogo.chat.title or '777000' in Id:
                    nome = "Nome: {}".format(dialogo.chat.title or dialogo.chat.first_name)
                else:
                    nome = f"Nome: {dialogo.chat.first_name} "
                    if dialogo.chat.last_name:
                        nome += "{}".format(dialogo.chat.last_name)

                    if dialogo.chat.username:
                        nome += f"\nNome de usuário: {dialogo.chat.username}"

                if name.lower() in nome.lower() or name in Id:
                    if "" == infos:
                        infos += "\nChats encontrados (ContA):\n\n"

                    infos += f"{tipo}\n{Id}\n{nome}\n\n"
                    ContA += 1

            if not infos:
                infos = "Não há registros referente à \"{}\"\n".format(name)

        else:
            infos += "\nChats encontrados (ContA):\n\n"
            for dialogo in dialogos:
                infos += "{}\n".format(dialogo.chat.title or dialogo.chat.first_name)
                ContA += 1

        if ContA == 1:
            infos = re.sub("Chats encontrados \(ContA\)", f"Único chat encontrado", infos)

        infos = re.sub("ContA", f"{ContA}", infos)

    return infos


def create_file():
    # import ipdb; ipdb.set_trace()
    if not os.path.exists(fileX):
        JsonX = json.loads(fileC)
        for obj in JsonX:
            if "code" == obj:
                if not JsonX[obj]:
                    JsonX[obj] = keepass()
                break
        write_json(fileX, JsonX)

    else:
        JsonX = load_json(fileX)

    return JsonX


def get_cripto(flag=False):
    JsonX = create_file()
    # import ipdb; ipdb.set_trace()
    # text = ""
    textK0 = []
    for obj in JsonX:
        if "code" == obj:
            if codeKey:
                JsonX[obj] = codeKey
            else:
                JsonX[obj] = keepass()
            continue
        textK = ""
        for k in JsonX[obj]:
            if JsonX[obj][k] == flag:
                if not textK:
                    textK += f"{obj}: "
                textK += f"{k}, "
                textK0 += [k]

        # if textK:
        #     text += f"{textK[:-2]}\n"
    write_json(fileX, JsonX)

    return textK0, JsonX


def create_cripto():
    textoKey, JsonX = get_cripto()
    key = JsonX['code']
    if textoKey:
        config = path.format('configScripts.properties')
        contArq = os.popen("cat {}".format(config)).read()
        textoKey = ", ".join(textoKey)
        print(f"\nOs seguintes campos podem ser criptografados:\n{textoKey}")
        criptoK = [str(objs).strip().rstrip() for objs in input("\ninforme quais deseja: ").split(",")]
        if [''] == criptoK:
            exit()
        for crip in criptoK:
            for js in JsonX:
                if "code" != js:
                    for k in JsonX[js]:
                        if crip == k:
                            valueR = re.search(f"\n{crip} ?= ?(.*)\n", contArq).group(1)
                            valueC = encrypt(key, valueR)
                            contArq = contArq.replace(f"{valueR}", f"{valueC}")
                            JsonX[js][k] = True

        contArq = contArq.rstrip()
        os.popen(f"cat > {config} << EOF\n{contArq} \nEOF")
        write_json(fileX, JsonX)

    else:
        print(f"\nNão há campos para criptografar.\n")
        exit()


def update_crypto(tag):
    pre = f"{'re' if 're' == tag else 'des'}"
    textoKey, JsonX = get_cripto(flag=True)
    if not textoKey:
        print(f"\nNão há campos para {pre}criptografar.\n")
        exit()

    key = JsonX['code']
    config = path.format('configScripts.properties')
    contArq = os.popen("cat {}".format(config)).read().replace("email_from", "mail.from").replace("smtp_server",
                                                                                                  "smtp.server").replace(
        "mail_", "mail.")
    textoKey = ", ".join(textoKey)
    print(f"\nOs seguintes campos podem ser {pre}criptografados:\n{textoKey}")
    criptoK = [str(objs).strip().rstrip() for objs in input("\ninforme quais deseja: ").split(",")]
    if [''] == criptoK:
        exit()
    for crip in criptoK:
        for js in JsonX:
            if "code" != js:
                for k in JsonX[js]:
                    if crip == k:
                        valueR = re.search(f"\n{crip} ?= ?(.*)\n", contArq).group(1)
                        if 'de' == tag:
                            valor = valueR
                            valueC = decrypt(key, valor)
                            JsonX[js][k] = False
                        else:
                            valor = input(f"\nAgora informe um valor para o campo '{crip}': ")
                            valueC = encrypt(key, valor)

                        contArq = contArq.replace(f"{valueR}", f"{valueC}")

    contArq = contArq.rstrip()
    os.popen(f"cat > {config} << EOF\n{contArq} \nEOF")
    write_json(fileX, JsonX)


def multi_input():
    try:
        while True:
            data = map(str, input("").split("\n"))
            if not data:
                break
            yield data
    except KeyboardInterrupt:
        return


def input_complete(input_list):
    if "--test" in input_list[-1]:
        return True
    else:
        return False


def get_input(prompt1, prompt2):
    L = list()
    prompt = prompt1
    while True:
        L.append(input(prompt))
        if input_complete(L):
            return "\n".join(L).replace("--test", "").strip().rstrip()
        print()
        prompt = prompt2


def send(msg=False):
    global subject, body, listaItemIds, triggerName, hostName, period, color, item_type, triggerid
    try:

        if msg:
            subject = input("Digite o 'Assunto': ")
            message = get_input("\nDigite a 'Mensagem' terminando com '--test': ", " ")
            triggerid, eventid, color, period, body = message.split('#', 4)
            period = int(period)

            item_type, triggerName, triggerid, hostName, listaItemIds = getTrigger(triggerid)

        else:
            item_type, triggerName, triggerid, hostName, listaItemIds = getTrigger()
            subject = '<b>testando o envio com o item</b>:'
            color = '00C800'
            period = 3600
            body = '{0}'.format(triggerName)


    except Exception as msg:
        print(msg)
        log.writelog(''.format(msg), arqLog, "WARNING")

    return triggerid, item_type, period


def main2(test=None):
    inicio = time.time()
    codDDI = PropertiesReaderX(path.format('configScripts.properties')).getValue('PathSectionWhatsApp', 'cod.ddi')

    triggerid, item_type, period = send(test)
    try:

        dest = sys.argv[2]
        destino = destinatarios(dest)

        if nograph in sys.argv:
            item_type = "1"
            get_graph = ""
        else:
            get_graph = getgraph(period)

        emails = []
        for x in destino:
            if re.match(f"^({codDDI})?\d+(-)?\d+(@g\.us)?", x):
                send_whatsapp(x, item_type, get_graph, codeKey)

            elif re.search("^.*@[a-z0-9-]+\.[a-z]+(\.[a-z].*)?$", x.lower()):
                emails.append(x)

            else:
                telegram = x.replace("_", " ")
                send_telegram(telegram, item_type, get_graph, codeKey, triggerid)

        if [] != emails:
            send_mail(emails, item_type, get_graph, codeKey)

        fim = time.time()
        total = fim - inicio
        print("\nTempo de execução do script: {:.2f}{}\n".format(total if total > 1 else 1000 * total,
                                                                 's' if total > 1 else 'ms'))

    except Exception as msg:
        print(msg)
        log.writelog(''.format(msg), arqLog, "WARNING")


def main():
    global auth, codeKey
    JSON = create_file()
    codeKey = JSON['code']

    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--infoAll', action="store_true", help="Consult all information")
    parser.add_argument('-e', '--encrypt', action="store_true", help="Encrypt information")
    parser.add_argument('-d', '--decrypt', action="store_true", help="Decrypt information")
    parser.add_argument('-r', '--reEncrypt', action="store_true", help="Re-encrypt information")
    parser.add_argument('-i', '--info', action="store", dest="contact", help="Consult specific user/chat information")
    parser.add_argument('-s', '--send', action="store", dest="destiny", help="Send test")
    parser.add_argument('-t', '--test', action="store", dest="argvs_Environment", help="Send test environment")

    try:
        args = parser.parse_args()
    except:
        print("\n")
        exit()

    if args.encrypt:
        create_cripto()
        exit()

    elif args.reEncrypt:
        update_crypto('re')
        exit()

    elif args.decrypt:
        update_crypto('de')
        exit()

    elif args.destiny:
        auth = token()
        main2()
        logout_api()
        exit()

    elif args.argvs_Environment:
        auth = token()
        main2(True)
        logout_api()
        exit()

    elif args.contact:
        nome = args.contact

    elif args.infoAll:
        nome = None

    r = get_info(nome)
    print(r)
    exit()


if __name__ == '__main__':
    main()
