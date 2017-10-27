#!/usr/bin/python3
# -*- coding: utf-8 -*-

import urllib
import sys
import os
import json
import lxml.html
import requests
import operator

from flask import request, Response, Flask

from socket import (AF_INET,
                   error,
                   SHUT_RDWR,
                   socket,
                   SOCK_STREAM)

from contextlib import contextmanager


sys.path.append(os.path.dirname(__file__))
application = Flask(__name__)
application.debug = True


@contextmanager
def _tcpip4_socket(host, port):
    """Open a TCP/IP4 socket to designated host/port.
    This code originates from 'pip install ner',
    but the module itself was broken, so took usefull code
    and improved on it.
    """

    sock = socket(AF_INET, SOCK_STREAM)
    sock.settimeout(50)

    try:
        sock.connect((host, port))
        yield sock
    finally:
        try:
            sock.shutdown(SHUT_RDWR)
        except error:
            log.error("Socket error %s %s" % (host, str(port)))
            pass
        except OSError:
            log.error("OSEerror %s %s" % (host, str(port)))
            pass
        finally:
            sock.close()

def exec_ner(text, text_org, tagname, context=5):
    for s in ("\f", "\n", "\r", "\t", "\v"):  # strip whitespaces
        text = text.replace(s, '')
    text += "\n"  # ensure end-of-line

    with _tcpip4_socket('localhost', 5433) as s:
        if not isinstance(text, bytes):
            text = text.encode('utf-8')
        s.sendall(text)

        tagged_text = s.recv(10*len(text))

    result = tagged_text.decode("utf-8")

    ner = {"raw_response": result,
           "raw_ners": [],
           "ners": []}

    result = "<xml>%s</xml>" % result
    res = lxml.html.fromstring(result)

    ners = {}

    total = ''
    i = -1

    all_tags = []

    offset = 0
    context_tokens = u"”„!,'\",`<>?-+\\"

    convert_next = False

    for item in res.iter():
        if item.tag == 'xml':
            continue
        if item.text == None:
            continue
        if not type(item.tag) == str:
            continue
        if len(item.text) < 2:
            convert_next = True
            continue

        if convert_next:
            item.tag = 'b-per'
            convert_next = False

        print(item, item.tag, item.text)

        if item.tag.startswith('i-'):
            ners[str(i)]["ne"] +=  ' ' + item.text
            offset += len(item.text)

            rightof = text_org[ners[str(i)]["pos"] + len(ners[str(i)]["ne"]):].strip()
            rightof = " ".join(rightof.split()[:context])
            ners[str(i)]["right_context"] = rightof

        else:
            i+=1
            ners[str(i)] = {}

            ners[str(i)]["source"] = tagname
            ners[str(i)]["ne"] = item.text
            ners[str(i)]["pos"] = text_org[offset:].find(item.text) + offset
            offset += text_org[offset:].find(item.text)

            if 'loc' in item.tag:
                ners[str(i)]["type"] = 'location'
            elif 'per' in item.tag:
                ners[str(i)]["type"] = 'person'
            else:
                ners[str(i)]["type"] = 'organisation'

            leftof = text_org[:ners[str(i)]["pos"]].strip()
            left_context = " ".join(leftof.split()[-context:])
            ners[str(i)]["left_context"] = left_context

            rightof = text_org[ners[str(i)]["pos"] + len(ners[str(i)]["ne"]):].strip()
            rightof = " ".join(rightof.split()[:context])
            ners[str(i)]["right_context"] = rightof



    entities = []
    for ner in ners:
        ners[ner]["ner_context"] = ners[ner]["ne"]

        try:
            if ners[ner]["left_context"][-1] in context_tokens:
                ners[ner]["ner_context"] = ners[ner]["left_context"][-1] + ners[ner]["ner_context"]
        except:
            pass

        try:
            if ners[ner]["right_context"][0] in context_tokens:
                ners[ner]["ner_context"] = ners[ner]["ner_context"] + ners[ner]["right_context"][0]
        except:
            pass


    #ners["entities"] = entities

    #if "title" in ners
    #ners["text"] = 

    '''
        try:
            if ners[ner]["left_context"].split()[-1][-1] in context_tokens:
                ners[ner]["ner_context"] = ners[ner]["left_context"].split()[-1] + ners[ner]["ne"]
            else:
        except:
            ners[ner]["ner_context"] = ners[ner]["ne"]

        try:
            if ners[ner]["right_context"].split()[0][0] in context_tokens:
                ners[ner]["ner_context"] += ners[ner]["right_context"].split()[0]
        except:
            pass
    '''


    result = []
    for item in ners:
        result.append(ners.get(item))

    result = sorted(result, key=operator.itemgetter('pos'))
    return result


@application.route('/')
def index():
    text = request.args.get('text')
    url = request.args.get('url')
    mode = request.args.get('mode')
    context = request.args.get('context')

    if context:
        try:
            context = int(context)
        except:
            return ("Error, parameter context not a number.")
    else:
        context = 5

    if not (text or url):
        return ("Inovke with ?url= optional &context=")

    if url:
        try:
            req = requests.get(url)
        except:
            return ("Error, unable to open URL.")

        text = req.content
        parsed_text = {}

        if text.startswith('<?xml'):
            parser = lxml.etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
            xml = lxml.etree.fromstring(text, parser=parser)
            for item in xml.iter():
                if not item.text:
                    continue
                if item.tag == 'title':
                    text = item.text + '. '
                    parsed_text["title"] = item.text
                elif item.text:
                    if not "p" in parsed_text:
                        text += item.text + ' '
                        parsed_text["p"] = [item.text]
                    else:
                        parsed_text["p"].append(item.text)
                        text += item.text + ' '
            parsed_text["p"] = " ".join(parsed_text["p"])

    if not mode:
        mode = 'json'

    if parsed_text:
        if "title" in parsed_text:
            result1 = exec_ner(parsed_text["title"], parsed_text["title"], "title", context)

        result2 = exec_ner(parsed_text["p"], parsed_text["p"], "p", context)
        if "title" in parsed_text:
            result = result1
            for r in result2:
                result.append(r)
        else:
            result = result2
    else:
        result = exec_ner(text, text, "text", context)

    if parsed_text:
        if "title" in parsed_text:
            result.append({"title" : parsed_text["title"],"p" : parsed_text["p"]})
        else:
            result.append({"p" : parsed_text["p"]})
    else:
        result.append({"org_text" : text})
        result.append({"parsed_text" : text})

    result1 = {"entities": [], "text" : []}
    for en in result:
        if en.get('ne'):
            result1["entities"].append(en)
        elif en.get('title'):
            result1["text"].append(en)
        elif en.get('p'):
            result1["text"].append(en)

    if mode == 'json':
        resp = Response(response=json.dumps(result1), mimetype='application/json')

    return resp

if __name__ == '__main__':

    from pprint import pprint
    url = 'http://resolver.kb.nl/resolve?urn=ddd:010988325:mpeg21:a0071:ocr'# ?? <- needs work


    url = 'http://resolver.kb.nl/resolve?urn=ddd:010988325:mpeg21:a0077:ocr'

    url = 'http://resolver.kb.nl/resolve?urn=ddd:010988325:mpeg21:a0073:ocr'

    req = requests.get(url)
    text = req.content
    parser = lxml.etree.XMLParser(ns_clean=True, recover=True, encoding='utf-8')
    xml = lxml.etree.fromstring(text, parser=parser)
    text = ''
    parsed_text = {}
    for item in xml.iter():
        if not item.text:
            continue
        if item.tag == 'title':
            text = item.text + '. '
            parsed_text["title"] = item.text
        elif item.text:
            if not "p" in parsed_text:
                text += item.text + ' '
                parsed_text["p"] = [item.text]
            else:
                parsed_text["p"].append(item.text)
                text += item.text + ' '

    pprint(parsed_text)
    parsed_text["p"] = " ".join(parsed_text["p"])

    if "title" in parsed_text:
       result1 = exec_ner(parsed_text["title"], parsed_text["title"], "title")

    result2 = exec_ner(parsed_text["p"], parsed_text["p"], "p")
    if "title" in parsed_text:
        result = result1
        for r in result2:
            result.append(r)
    else:
        result = result2

    pprint(result)
