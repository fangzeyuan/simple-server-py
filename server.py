#!/usr/bin/env python

# This is a simple web server for a traffic counting application.
# It's your job to extend it by adding the backend functionality to support
# recording the traffic in a SQL database. You will also need to support
# some predefined users and access/session control. You should only
# need to extend this file. The client side code (html, javascript and css)
# is complete and does not require editing or detailed understanding.

# import the various libraries needed
import http.cookies as Cookie # some cookie handling support
from http.server import BaseHTTPRequestHandler, HTTPServer # the heavy lifting of the web server
import urllib # some url parsing support
import json # support for json encoding
import sys # needed for agument handling
import sqlite3
import random 
import time
from datetime import datetime,timedelta,date
import functools
from collections import defaultdict


#connect the database and create a cursor
coon = sqlite3.connect('traffic.db')
cursor = coon.cursor()

class DateTransformer:
    '''
   #last_login =0
   # last_logout = 0
    last_month_end =0 
    last_month_start =0
    last_week_start =0 
    last_week_end =0
    day = 0
    week = 0
    month = 0
    records = 0'''
    def __init__(self,start,end,records):
        self.records = records
        #self.last_login = start
        #self.last_logout =end
        end = datetime.fromtimestamp(end) 
        last_day_start = end - timedelta(minutes=end.minute,hours=end.hour,seconds=end.second)
        last_day_end =  last_day_start + timedelta(days=1)
        last_week_start = end - timedelta(days=end.weekday() + 7,minutes=end.minute,hours=end.hour,seconds=end.second)
        last_week_end = end - timedelta(days=end.weekday() + 1,minutes=end.minute,hours=end.hour,seconds=end.second)
        this_month_start = datetime(end.year, end.month, 1)
       # this_month_end = datetime(end.year, end.month + 1 , 1) - timedelta(days=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = datetime(last_month_end.year, last_month_end.month, 1)
        self.last_month_end=last_month_end
        self.last_month_start = last_month_start
        self.last_week_start = last_week_start
        self.last_week_end = last_week_end
        self.last_day_start = last_day_start
        self.last_day_end = last_day_end
        '''print("last w start",last_week_start)
        print("last w end",last_week_end)
        print("last m start",last_month_start)
        print("last m end",last_month_end)'''
    def set_day(self):
        '''day =  round((self.last_logout-self.last_login)/3600,1)
        self.day = day'''
        day =0
        for rec in self.records:
            start, end = rec
            if start ==0 or end==0:
                continue
            start = datetime.fromtimestamp(start)
            end = datetime.fromtimestamp(end)
          #  print(start,"  ",self.last_day_start,"  ",end,"  ",self.last_day_end)
            if max(start , self.last_day_start) <= min(end, self.last_day_end):
                #considering boundary 
                if start < self.last_day_start:
                    start = self.last_day_start
                if end >  self.last_day_end:
                    end = self.last_day_end
                day += round((end-start).seconds/3600,1)
        self.day = day
    def set_week(self):
        week =0
        for rec in self.records:
            start, end = rec
            if start ==0 or end==0:
                continue
            start = datetime.fromtimestamp(start)
            end = datetime.fromtimestamp(end)
           # print(start,"  ",self.last_week_start,"  ",end,"  ",self.last_week_end)
            if max(start , self.last_week_start) <= min(end, self.last_week_end):
                #considering boundary 
                if start < self.last_week_start:
                    start = self.last_week_start
                if end >  self.last_week_end:
                    end = self.last_week_end
                week += round((end-start).seconds/3600,1)
        self.week = week
        
    def set_month(self):
        month =0
        for rec in self.records:
            start, end = rec
            if start ==0 or end==0:
                continue
            start = datetime.fromtimestamp(start)
            end = datetime.fromtimestamp(end)
            # if overlapping 
            if max(start,self.last_month_start) <= min(end , self.last_month_end):
                #considering boundary 
                if start < self.last_month_start:
                    start = self.last_month_start
                if end >  self.last_month_end:
                    end = self.last_month_end
                month += round((end-start).seconds/3600,1)
        self.month = month
    def get_summary(self):  
        self.set_day()
        self.set_month()
        self.set_week()
        summary = (self.day,self.week,self.month)
        summary= list(map(str,summary))
        return ','.join(summary)+'\n'
    


    

def build_response_refill(where, what):
    """This function builds a refill action that allows part of the
       currently loaded page to be replaced."""
    return {"type":"refill","where":where,"what":what}


def build_response_redirect(where):
    """This function builds the page redirection action
       It indicates which page the client should fetch.
       If this action is used, only one instance of it should
       contained in the response and there should be no refill action."""
    return {"type":"redirect", "where":where}


def handle_validate(iuser, imagic):
    """Decide if the combination of user and magic is valid"""
    ## alter as required
    #select count(*) from session
    print('iuser-------------',iuser) 
    print('imagic-------------',imagic) 
    userid = cursor.execute('select userid from users where username == ?',(iuser,)).fetchone()

    if userid is None:
        return False
    userid =userid[0]
    session = cursor.execute('select * from session  where userid==? AND magic ==?',(userid,imagic)).fetchone()
    print('session-------------',session)
    #if (iuser == 'test') and (imagic == '1234567890'):
    now = int(time.time())
    #If the session exists and it is activated or not expired, it is validated
    if session is not None and (session[4]== 0 or session[4]>= now):
        return True
    else:
        return False


def handle_delete_session(iuser, imagic):
    """Remove the combination of user and magic from the data base, ending the login"""
    userid = cursor.execute('select userid from users where username ==?',(iuser,)).fetchone()[0]
    cursor.execute('delete from session where userid==? AND magic==? ',(userid,imagic))
    coon.commit()
    return

def handle_login_request(iuser, imagic, parameters):
    """A user has supplied a username (parameters['usernameinput'][0])
       and password (parameters['passwordinput'][0]) check if these are
       valid and if so, create a suitable session record in the database
       with a random magic identifier that is returned.
       Return the username, magic identifier and the response action set."""
    
    
    if handle_validate(iuser, imagic) == True:
        # the user is already logged in, so end the existing session.
        handle_delete_session(iuser, imagic)

    response = []
    ## alter as required

    # check if username input is none.
    if 'usernameinput' not in parameters:
        user = '!'
        magic = ''
        response.append(build_response_refill('message', 'Input Error: Username is blank.'))
        return [user,magic,response] 
    
    uname = parameters['usernameinput'][0]

    query = cursor.execute('select * from users where username==?',(uname,)).fetchone()
    
    """if parameters['usernameinput'][0] == 'test': ## The user is valid
        response.append(build_response_redirect('/page.html'))
        user = 'test'
        magic = '1234567890'"""

    if 'passwordinput' not in parameters or query is None:
        user = '!'
        magic = ''
        response.append(build_response_refill('message', 'Input Error: Username or Password is wrong.'))
        return [user,magic,response] 
    # If there exists such a user and the password matches we randomly generate a magic number for it
    if query[2]==parameters['passwordinput'][0]:
        response.append(build_response_redirect('/page.html'))
        user = uname
        magic = random.randint(1000000000,9999999999)
        sid = cursor.execute('SELECT COUNT(*) FROM session').fetchone()[0]
        sid += 1 
        now = int(time.time())
        # session duratation is forever.
        session =(sid,query[0],magic,now,0)
        cursor.execute('INSERT INTO session VALUES (?,?,?,?,?)',session)
        coon.commit()
        

    else: ## The user is not valid
        response.append(build_response_refill('message', 'Invalid password'))
        user = '!'
        magic = ''
    return [user, magic, response]


def handle_add_request(iuser, imagic, parameters):
    """The user has requested a vehicle be added to the count
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings) and the response action set."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
    else: ## a valid session so process the addition of the entry.
        if 'locationinput' not in parameters:
            response.append(build_response_refill('message', 'Location entry can not be null.'))
 
        else:
            n = cursor.execute('select count(*) from traffic').fetchone()[0]
            n  = 0 if n==None else n
            sid = int(n)
            now =int(time.time())
            typeinput = parameters['typeinput'][0]
            loc = parameters['locationinput'][0]
            occupancy = parameters['occupancyinput'][0]
            mode =1
            rec = (n,sid,now,typeinput,occupancy,loc,mode)
            cursor.execute("INSERT INTO traffic VALUES (?,?,?,?,?,?,? );",rec)
            coon.commit()        
            response.append(build_response_refill('message', 'Entry added.'))
            response.append(build_response_refill('total', n+1))

    user = ''
    magic = ''
    return [user, magic, response]


def handle_undo_request(iuser, imagic, parameters):
    """The user has requested a vehicle be removed from the count
       This is intended to allow counters to correct errors.
       parameters['locationinput'][0] the location to be recorded
       parameters['occupancyinput'][0] the occupant count to be recorded
       parameters['typeinput'][0] the type to be recorded
       Return the username, magic identifier (these can be empty  strings) and the response action set."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        #Invalid sessions redirect to login
        response.append(build_response_redirect('/index.html'))
    else: ## a valid session so process the recording of the entry.
        if 'locationinput' not in parameters:
            response.append(build_response_refill('message', 'Location entry can not be null.'))
            
        else:
            typeinput = parameters['typeinput'][0]
            loc = parameters['locationinput'][0]
            
            occupancy = parameters['occupancyinput'][0] 
            cursor.execute('delete from traffic where recordid= (select max(recordid) from traffic where type==? AND location==? AND occupancy==?)',(typeinput,loc,occupancy))
            coon.commit()
            n = cursor.execute('select count(*) from traffic').fetchone()[0]
            n  = 0 if n==None else n
            n = int(n)
            response.append(build_response_refill('message', 'Entry Un-done.'))
            response.append(build_response_refill('total', n))   

    user = ''
    magic = ''
    return [user, magic, response]


def handle_back_request(iuser, imagic, parameters):
    """This code handles the selection of the back button on the record form (page.html)
       You will only need to modify this code if you make changes elsewhere that break its behaviour"""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
        response.append(build_response_redirect('/summary.html'))
    user = ''
    magic = ''
    return [user, magic, response]


def handle_logout_request(iuser, imagic, parameters):
    """This code handles the selection of the logout button on the summary page (summary.html)
       You will need to ensure the end of the session is recorded in the database
       And that the session magic is revoked."""
    response = []
    ## alter as required
    now = int(time.time())
    userid = cursor.execute('select userid from users where username = ?',(iuser,)).fetchone()[0]
    cursor.execute('update session set end=? where userid=? and magic=? ',(now,userid,imagic));
    coon.commit()
    response.append(build_response_redirect('/index.html'))
    user = '!'
    magic = ''
    return [user, magic, response]


def handle_summary_request(iuser, imagic, parameters):
    """This code handles a request for an update to the session summary values.
       You will need to extract this information from the database.
       You must return a value for all vehicle types, even when it's zero."""
    response = []
    ## alter as required
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
       
        sum_dict={'car':0,'taxi':0,'bus':0,'motorbike':0,'bicycle':0,'van':0,'truck':0,'other':0,'total':0}
        tmp= dict(cursor.execute('select type,count(*) from traffic group by type').fetchall())
        sum_dict.update(tmp)
        tmp = cursor.execute('select count(*) from traffic').fetchone()[0]
        sum_dict['total']=tmp
        response.append(build_response_refill('sum_car', sum_dict['car']))
        response.append(build_response_refill('sum_taxi', sum_dict['taxi']))
        response.append(build_response_refill('sum_bus', sum_dict['bus']))
        response.append(build_response_refill('sum_motorbike', sum_dict['motorbike']))
        response.append(build_response_refill('sum_bicycle', sum_dict['bicycle']))
        response.append(build_response_refill('sum_van', sum_dict['van']))
        response.append(build_response_refill('sum_truck', sum_dict['truck']))
        response.append(build_response_refill('sum_other', sum_dict['other']))
        response.append(build_response_refill('total', sum_dict['total']))
   
    user = ''
    magic = ''
    return [user, magic, response]

def handle_traffic_csv_request(iuser, imagic):
    response=[]
    info = ''
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
        records = cursor.execute('select location,type,occupancy from traffic').fetchall()
        records2= [ (x,y,'0','0','0','0') for x,y,z in records]
        records3 = []
        for r1,r2 in zip(records,records2):
            occup = r1[2]
            if isinstance(occup,int):
                tmp = list(r2)
                tmp[occup+1] ='1'
                r2 = tuple(tmp)
            records3.append(r2)
        for rec in  records3:
            info += ','.join(rec) + '\n'
    user = ''
    magic = ''
    return [user, magic, response,info]
def handle_hour_csv_request(iuser,imagic):
    '''This code handles hour.csv request, we first check whether the user is validate '''
    response=[]
    info = ''
    if handle_validate(iuser, imagic) != True:
        response.append(build_response_redirect('/index.html'))
    else:
        last  =cursor.execute('select u.username,start, end from users u left join session s on u.userid=s.userid where not exists(select * from session where s. end<end)').fetchall()
        '''records = cursor.execute('select u.username,CASE WHEN count(*) != 0 THEN group_concat(start) ELSE 0 END,CASE WHEN count(*)!=0 THEN group_concat(end)'+
            +'ELSE 0 END from users u left join session s on u.userid = s.userid ').fetchall()
        '''
        last = [ (k,0,0) if v1 is None else (k,v1,v2) for (k,v1,v2) in last]
        last_dict = {}
        for k,v1,v2 in last:
            last_dict[k]= (v1,v2)

     
        records = cursor.execute('select u.username,start,end from users u left join session s on u.userid = s.userid ').fetchall()
        records_dict={}
        for k,v1,v2 in records:
            if v1 is None :
                v1 =0
            if v2 is None :
                v2 = 0 
            if k not in records_dict:
                records_dict[k]=[]
                records_dict[k].append((v1,v2))
            else:
               records_dict[k].append((v1,v2)) 
        for k in last_dict.keys():
            dt = DateTransformer(last_dict[k][0],last_dict[k][1],records_dict[k])
            info+= k+',' + dt.get_summary()
          
                
    user = ''
    magic = ''
    return [user, magic, response,info]
# HTTPRequestHandler class
class myHTTPServer_RequestHandler(BaseHTTPRequestHandler):

    # GET This function responds to GET requests to the web server.
    def do_GET(self):

        # The set_cookies function adds/updates two cookies returned with a webpage.
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(x, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            x.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            x.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        print(user_magic)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # Return a CSS (Cascading Style Sheet) file.
        # These tell the web client how the page should appear.
        if self.path.startswith('/css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return a Javascript file.
        # These tell contain code that the web client can execute.
        elif self.path.startswith('/js'):
            self.send_response(200)
            self.send_header('Content-type', 'text/js')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # A special case of '/' means return the index.html (homepage)
        # of a website
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./index.html', 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # Return html pages.
        elif parsed_path.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('.'+parsed_path.path, 'rb') as file:
                self.wfile.write(file.read())
            file.close()

        # The special file 'action' is not a real file, it indicates an action
        # we wish the server to execute.
        elif parsed_path.path == '/action':
            self.send_response(200) #respond that this is a valid page request
            # extract the parameters from the GET request.
            # These are passed to the handlers.
            parameters = urllib.parse.parse_qs(parsed_path.query)

            if 'command' in parameters:
                # check if one of the parameters was 'command'
                # If it is, identify which command and call the appropriate handler function.
                if parameters['command'][0] == 'login':
                    [user, magic, response] = handle_login_request(user_magic[0], user_magic[1], parameters)
                    #The result of a login attempt will be to set the cookies to identify the session.
                    set_cookies(self, user, magic)
                elif parameters['command'][0] == 'add':
                    [user, magic, response] = handle_add_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'undo':
                    [user, magic, response] = handle_undo_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'back':
                    [user, magic, response] = handle_back_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'summary':
                    [user, magic, response] = handle_summary_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'logout':
                    [user, magic, response] = handle_logout_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                else:
                    # The command was not recognised, report that to the user.
                    response = []
                    response.append(build_response_refill('message', 'Internal Error: Command not recognised.'))

            else:
                # There was no command present, report that to the user.
                response = []
                response.append(build_response_refill('message', 'Internal Error: Command not found.'))

            text = json.dumps(response)
            print(text)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(text, 'utf-8'))

        elif self.path.endswith('/statistics/hours.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for /statistics/hours.csv should be handled.
            ## you should check a valid user is logged in. You are encouraged to wrap this behavour in a function.

            [user, magic, response,info] = handle_hour_csv_request(user_magic[0], user_magic[1])
            if user == '!': # Check if we've been tasked with discarding the cookies.
                set_cookies(self, '', '') 
            text = "Username,Day,Week,Month\n"
            text+=info

            '''text += "test1,0.0,0.0,0.0\n" # not real data
            text += "test2,0.0,0.0,0.0\n"
            text += "test3,0.0,0.0,0.0\n"
            text += "test4,0.0,0.0,0.0\n"
            text += "test5,0.0,0.0,0.0\n"
            text += "test6,0.0,0.0,0.0\n"
            text += "test7,0.0,0.0,0.0\n"
            text += "test8,0.0,0.0,0.0\n"
            text += "test9,0.0,0.0,0.0\n"
            text += "test10,0.0,0.0,0.0\n"  '''     

            encoded = bytes(text, 'utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('hours.csv'))
            self.send_header("Content-Length", len(encoded))
            self.end_headers()
            self.wfile.write(encoded)

        elif self.path.endswith('/statistics/traffic.csv'):
            ## if we get here, the user is looking for a statistics file
            ## this is where requests for  /statistics/traffic.csv should be handled.
            ## you should check a valid user is checked in. You are encouraged to wrap this behavour in a function.
            [user, magic, response,info] = handle_traffic_csv_request(user_magic[0], user_magic[1])
            if user == '!': # Check if we've been tasked with discarding the cookies.
                set_cookies(self, '', '')            
            text = "Location,Type,Occupancy1,Occupancy2,Occupancy3,Occupancy4\n"
            text +=info
            #text += '"Main Road",car,0,0,0,0\n' # not real datad 
            encoded = bytes(text, 'utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format('traffic.csv'))
            self.send_header("Content-Length", len(encoded))
            self.end_headers()
            self.wfile.write(encoded)

        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404)
            self.end_headers()
        return

def run():
    """This is the entry point function to this code."""
    print('starting server...')
    ## You can add any extra start up code here
    # Server settings
    # Choose port 8081 over port 80, which is normally used for a http server
    if(len(sys.argv)<2): # Check we were given both the script name and a port number
        print("Port argument not provided.")
        return
    server_address = ('127.0.0.1', int(sys.argv[1]))
    httpd = HTTPServer(server_address, myHTTPServer_RequestHandler)
    print('running server on port =',sys.argv[1],'...')
    httpd.serve_forever() # This function will not return till the server is aborted.

run()
