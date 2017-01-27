# #
# Copyright 2016 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# This action is used in conjunction with the slack slash command /wsk.
# The action receives as parameter a dictionary that contains two keys "payload" and "response-url".
# The value associated with the "payload" key has the following structure:
#       <action-name> [<param-name> <param-value>]*
# The action invokes the action received in the payload with the parameter list, if any. The invoke is done in blocking mode, such that the result 
# of the action execution is received. 
# The value for the "response-url" key contains the url where the response can be sent back to slack. 
# If the action executes successfully, its result is packaged in a json document with one field "message" that contains the response from the action. 
# If any of the operations fail for some reason, the response back to slack is a json with one field "message" which declares error and a reason for the error.

import base64
import httplib
import json
import ssl
from urlparse import urlparse


# types of errors and corresponding strings
parameter_error = {"text": "error retrieving parameter list with two key fields: payload and response-url"}
action_name_error = {"text": "error retrieving the name of the action, the payload seems empty"}

def createParamDict(parameters):
    paramDict = {}
    for i in range(1, len(parameters) - 1):
        paramDict[parameters[i]] = parameters[i+1]
    return paramDict

def request(method, urlString, body = '', headers = {}, auth = None, verbose = False):
    url = urlparse(urlString)
    if url.scheme == 'http':
        conn = httplib.HTTPConnection(url.netloc)
    else:
        if hasattr(ssl, '_create_unverified_context'):
            conn = httplib.HTTPSConnection(url.netloc, context=ssl._create_unverified_context())
        else:
            conn = httplib.HTTPSConnection(url.netloc)

    if auth != None:
        auth = base64.encodestring(auth).replace('\n', '')
        headers['Authorization'] = 'Basic %s' % auth

    try:
        conn.request(method, urlString, body, headers)
        res = conn.getresponse()
        body = ''
        try:
            body = res.read()
        except httplib.IncompleteRead as e:
            body = e.partial

        # patch the read to return just the body since the normal read
        # can only be done once
        res.read = lambda: body
    except Exception, e:
        res = dict2obj({ 'status' : 500, 'error': str(e) })
    return res

def doInvoke(action, parameters, auth):
    namespace = 'ioana%40us.ibm.com_dev'
    url = 'https://openwhisk.ng.bluemix.net/api/v1/namespaces/' + namespace + '/actions/' + action +'?blocking=true&result=true'
    print(url) 
    payload = json.dumps(parameters)
    headers = {
        'Content-Type': 'application/json'
    }
    res = request('POST', url, payload, headers, auth = auth)
    return res    


def sendResponseToSlack(url, payload):
    headers = {
        'Content-Type': 'application/json'
    }
    res = request('POST', url, payload, headers)
    return res

# this is a whisk action in python, main function needs to be declared
def main(dict):
    # check the two fields
    print("Start wsk_action_proxy")
    print(dict)
    auth = None
    if 'auth' in dict:
        auth = dict['auth']
    if 'payload' in dict:
        payload = dict['payload']
    else:
        return parameter_error
    if 'response_url' in dict:
        response_url = dict['response_url']
    else:
        return parameter_error
    
    # check there is a least a parameter in the payload
    parameters = payload.split(' ')
    action = parameters[0]  
    if len(action) == 0:
        return action_name_error
    action_params = createParamDict(parameters)
    print(action_params)
    # call the action given the parameters
    # for now, only default namespace actions are called
    res = doInvoke(action, action_params, auth)
    print('done invoke')
    if res.status == httplib.OK:
        # send response back to slack using the response url
        # form a message with a field text
        message = { 'text': res.read(), 'response_type': 'in_channel'}
        slackRes = sendResponseToSlack(response_url, json.dumps(message))
        if slackRes.status == httplib.OK:
            print('successful transaction with Slack!')
        else:
            print('Slack returned error code ' + str(slackRes.status))
            print(slackRes.read())
    else:
        print('error received from action, returning error to slack')
        dict = {'text': 'an error occurred ' + str(res.status) + " " + res.read()}
        sendResponseToSlack(response_url, json.dumps(dict))
    print('all done!')

