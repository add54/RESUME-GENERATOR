#!/usr/bin/env python3

import cherrypy
import weasyprint
from jinja2 import Template, FileSystemLoader, Environment
from base64 import b64encode
import os
import json
import random
import psycopg2
import base64

class App(object):

    def __init__(self):
        loader = FileSystemLoader('templates')
        self.templateEnv = Environment(loader =  loader)
        connString = os.environ.get("POSTGRES_CONNECTION", "dbname=cvgenerator user=cvgenerator")
        self.baseUrl = os.environ.get("BASE_URL", "")
        self.conn = psycopg2.connect(connString)
        self.conn.autocommit = True
        self.cur = self.conn.cursor()
        self.cur.execute('CREATE TABLE IF NOT EXISTS cvdata (key TEXT PRIMARY KEY, data JSON, picmimetype varchar(15), pic bytea);')


    def getData(self, key):
        self.cur.execute('SELECT data FROM cvdata WHERE key = %s', (key, ))
        s = self.cur.fetchone()

        if s == None or s[0] == None:
            data = {}
        else:
            data = s[0]

        return data

    def ensureKey(self, key):
        try:
            self.cur.execute('INSERT INTO cvdata (key) values (%s)', (key, ))
        except psycopg2.IntegrityError:
            pass

    def setData(self, key, data):
        self.ensureKey(key)
        self.cur.execute('UPDATE cvdata SET data = %s WHERE key = %s', (data, key))


    def getPic(self, key):
        self.cur.execute('SELECT picmimetype, pic FROM cvdata where key = %s', (key, ))
        mimetype, picBytes = self.cur.fetchone()
        if mimetype == None:
            return None
        else:
            foo =  'data:%s;base64,%s' % (mimetype, base64.b64encode(picBytes).decode('utf-8'))
            print(foo[0:100])
            return foo


    def setPic(self, key, picMimeType, picBytes):
        self.ensureKey(key)
        self.cur.execute('UPDATE cvdata SET picmimetype = %s, pic = %s WHERE key = %s', (picMimeType, picBytes, key))

    @cherrypy.expose('cv')
    @cherrypy.tools.json_in()
    def cv(self, **kwargs):
        isPng = kwargs['type'] == 'png'
        doBase64 = kwargs.get('base64') != None
        if (isPng):
            responseType = 'application/png'
        else:
            responseType = 'application/pdf'


        key = kwargs['key']
        try: # get from request and persist if request contains, otherwise get from db
            data = cherrypy.request.json
            self.setData(key, json.dumps(data))
        except AttributeError:
            data = self.getData(key)

        savedPicDataUri = self.getPic(key)

        if savedPicDataUri != None:
            data['image'] = savedPicDataUri
        else:
            data['image'] = 'placeholder.jpg'

        cherrypy.response.headers['Content-Type'] = responseType
        template = self.templateEnv.get_template('cv.html')
        style = weasyprint.CSS(string = """
        .pic {
          position: absolute;
          left: -8px;
          top: -8px;
          height: 1080px;
          z-index: -1;
          width: 726px;
          margin: 0;
        }

        .right-pane {
          position: absolute;
          left: 726px;
          top: 0;
          background-color: white;
          margin: 0;
          height: 1080px;
          padding-left: 50px;
          padding-top: 50px;
          padding-right: 200px;
        }

        .intro-texts {
          min-height: 220px;
        }

        .experience {
          float: left;
          width: 442px;
        }

        .education {
          float: left;
          width: 472px;
          padding-left: 30px;
        }

        .social {
          position: fixed;
          font-family: Sharp Sans No1 Bold;
          width: 472px;
          bottom: 50px;
          left: 1248px;
          color: green;
        }

        .social span {
          display: block;
        }

        .left-pane {
          position: relative;
          left: 0;
          top: 0;
          margin: 0;
          padding: 0;
          width: 726px;
          height: 1080px;
        }

        dt {
          font-family: Sharp Sans No1 Bold;
        }

        dd {
          margin-left: 0;
        }

        .keywords {
          position: absolute;
          font-family: Sharp Sans No1 Bold;
          left: 50%;
          margin-right: -50%;
          transform: translate(-50%, 0);
          bottom: 50px;
          background-color: #C4E2D9;
          padding-left: 10px;
          padding-right: 30px;
          min-width: 350px;
        }

        h1.name {
          padding-top: 0px;
          padding-bottom: 10px;
          margin-top: 0;
          margin-bottom: 0;
        }

        .title {
          margin-top: 15px;
        }

        h1, h2, h3 {
          font-family: Sharp Sans No1 Black;
          letter-spacing: 2px;
        }

        h3 {
          text-transform: uppercase;
        }

        body {
          font-family: Sharp Sans No1 Medium;
          font-size: 30px;
          line-height: 1.2em;
        }

        @page {
          size: 1920px 1080px;
          margin: 0;
        }
        """)
        doc = weasyprint.HTML(base_url=".", string = template.render(data))
        if isPng:
            bytes = doc.write_png(target=None, stylesheets=[style])
        else:
            bytes =  doc.write_pdf(target=None, stylesheets=[style])

        if isPng:
            extension = 'png'
        else:
            extension = 'pdf'

        cherrypy.response.headers['Content-Disposition'] = 'attachment; filename=cv.' + extension + ';'

        if doBase64:
            return b64encode(bytes)
        else:
            return bytes

    @cherrypy.expose('')
    def index(self, **kwargs):
        try:
            key = kwargs['key']
        except KeyError:
            raise cherrypy.HTTPRedirect('%s/?key=%08x' % (self.baseUrl, random.getrandbits(32)))

        data = self.getData(key)

        return self.templateEnv.get_template('index.html').render(data)


    @cherrypy.expose('upload')
    def upload(self, **kwargs):
        key = kwargs['key']
        self.setPic(key, kwargs['mimetype'], cherrypy.request.body.read())


cherrypy.quickstart(App(), '/',
                    {'/style.css':
                     {'tools.staticfile.on': True,
                      'tools.staticfile.filename': os.getcwd() + '/style.css'
                     },
                     '/index.js':
                     {'tools.staticfile.on': True,
                      'tools.staticfile.filename': os.getcwd() + '/index.js'
                     },
                     'global': {
                         'server.socket_host': '0.0.0.0',
                         'server.socket_port': 8000
                     }
                    })
