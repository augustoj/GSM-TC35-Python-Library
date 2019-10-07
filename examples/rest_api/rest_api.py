#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
  REST API to use the GSM module (in progress):
   - Are GSM module and PIN ready to work? (GET http://127.0.0.1:8080/api/ping)
   - Check call status (GET http://127.0.0.1:8080/api/call)
   - Call (POST http://127.0.0.1:8080/api/call with header data 'phone_number' and optional 'hide_phone_number')
   - Hang up call (DELETE http://127.0.0.1:8080/api/call)
   - Pick up call (PUT http://127.0.0.1:8080/api/call)
   - Get SMS/MMS (GET http://127.0.0.1:8080/api/sms with optional header data 'type')
   - Send SMS/MMS (POST http://127.0.0.1:8080/api/sms with header data 'phone_number', 'content' and optional 'is_content_in_hexa_format')
   - Delete SMS/MMS (DELETE http://127.0.0.1:8080/api/sms with optional header data 'type_or_index')
   - Get module date (GET http://127.0.0.1:8080/api/date)
   - Set module date to current date (POST http://127.0.0.1:8080/api/date)
   - More to come soon...

  Requirement:
   - Install (pip install) 'flask', 'flask_restful' and 'flask-httpauth'

  TODO:
   - Get config as file parameters (using 'getopt') instead of hardcoded in file
   - Add more API: Phonebook/Info/Reboot/...
   - Use HTTPS: https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https
   - Use better authentification (basic-auth is not optimized, token based auth would be more secured): https://blog.miguelgrinberg.com/post/restful-authentication-with-flask
   - Have possibility to chose between authentification type (no auth, basic auth, token-based auth)
   - Use sleep mode ?
"""
__author__ = 'Quentin Comte-Gaz'
__email__ = "quentin@comte-gaz.com"
__license__ = "MIT License"
__copyright__ = "Copyright Quentin Comte-Gaz (2019)"
__python_version__ = "3.+"
__version__ = "0.1 (2019/10/06)"
__status__ = "Example in progress (not secured and not fully implemented)"


from flask import Flask, request
from flask_restful import Resource, Api
from flask_httpauth import HTTPBasicAuth

from datetime import datetime
import time
import logging
import binascii
import serial

# Import our internal database helper
from internal_db import InternalDB

# Relative path to import GSMTC35 (not needed if GSMTC35 installed from pip)
import sys
sys.path.append("../..")

from GSMTC35 import GSMTC35


# ---- Config ----
pin = "1234"
puk = "12345678"
port = "COM8"
api_database_filename = "sms.db"
http_port = 8080
http_prefix = "/api"
BASIC_AUTH_DATA = {
  "basic_user": "test"
}
use_debug = True

# ---- App base ----
if use_debug:
  logger = logging.getLogger()
  logger.setLevel(logging.DEBUG)

app = Flask(__name__)
api = Api(app, prefix=http_prefix)

api_database = InternalDB(api_database_filename)

# ---- Authentification (basic-auth) ----
auth = HTTPBasicAuth()

@auth.verify_password
def verify(username, password):
  """Verify basic authentification credentials (confront to BASIC_AUTH_DATA)

  Keyword arguments:
    username -- (str) Username
    username -- (str) Password

  return: (bool) Access granted?
  """
  if not (username and password):
    return False

  return BASIC_AUTH_DATA.get(username) == password

# ---- Base functions ----
def getGSM():
  """Base function to get initialized GSM class

  return (bool, GSMTC35, string): success, GSM class, error explanation
  """
  gsm = GSMTC35.GSMTC35()

  try:
    if not gsm.isInitialized():
      if not gsm.setup(_port="COM8", _pin=pin, _puk=puk):
        return False, gsm, str("Failed to initialize GSM/SIM")

  except serial.serialutil.SerialException:
    return False, gsm, str("Failed to connect to GSM module")

  return True, gsm, str("")

def checkBoolean(value):
  """Return a bool from a string (or bool)"""
  if type(value) == bool:
    return value
  return str(value).lower() == "true" or str(value) == "1"

# ---- API class ----
class Ping(Resource):
  """Are GSM module and PIN ready to work?"""
  @auth.login_required
  def get(self):
    """Are GSM module and PIN ready to work? (GET)

    return (json):
      - (bool) 'result': Request worked?
      - (str) 'status': Are GSM module and PIN ready to work?
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      return {"result": True, "status": gsm.isAlive()}
    else:
      return {"result": False, "error": error}

class Date(Resource):
  """Get module internal date/Set module internal date to current date"""
  @auth.login_required
  def get(self):
    """Get module date as '%m/%d/%Y %H:%M:%S format' (GET)

    return (json):
      - (bool) 'result': Request worked?
      - (str) 'date': Module date
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      gsm_date = gsm.getDateFromInternalClock()
      if gsm_date != -1:
        return {"result": True, "date": gsm_date.strftime("%m/%d/%Y %H:%M:%S")}
      else:
        return {"result": False, "error": "Module failed to send date in time."}
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def post(self):
    """Set module date to current computer date (POST)

    return (json):
      - (bool) 'result': Request sent?
      - (bool) 'status': Module date updated?
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      return {"result": True, "status": gsm.setInternalClockToCurrentDate()}
    else:
      return {"result": False, "error": error}

class Call(Resource):
  """Call/Get call status/Pick up call/Hang up call"""
  @auth.login_required
  def get(self):
    """Get current call state (GET)

    return (json):
      - (bool) 'result': Request worked?
      - (str) 'status': Current call state
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      phone_status, phone = gsm.getCurrentCallState()
      res = {"result": True, "status": GSMTC35.GSMTC35.eCallToString(phone_status)}
      if len(phone) > 0:
        res["phone"] = phone
      return res
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def post(self):
    """Call specific phone number, possible to hide your phone (POST)

    Header should contain:
      - (str) 'phone_number': Phone number to call
      - (bool, optional, default: false) 'hide_phone_number': Hide phone number

    return (json):
      - (bool) 'result': Request worked?
      - (bool) 'status': Call in progress?
      - (str, optional) 'error': Error explanation if request failed
    """
    _phone_number = request.headers.get('phone_number', default = None, type = str)
    if _phone_number == None:
      return {"result": False, "error": "Please specify a phone number (phone_number)"}
    _hide_phone_number = request.headers.get('hide_phone_number', default = "false", type = str)
    _hide_phone_number = checkBoolean(_hide_phone_number)
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      return {"result": True, "status": gsm.call(phone_number=_phone_number, hide_phone_number=_hide_phone_number)}
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def put(self):
    """Pick-up call (PUT)

    return (json):
      - (bool) 'result': Request worked?
      - (bool) 'status': Pick-up worked?
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      return {"result": True, "status": gsm.pickUpCall()}
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def delete(self):
    """Hang-up call (DELETE)

    return (json):
      - (bool) 'result': Request worked?
      - (bool) 'status': Hang-up worked?
      - (str, optional) 'error': Error explanation if request failed
    """
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      return {"result": True, "status": gsm.hangUpCall()}
    else:
      return {"result": False, "error": error}

class Sms(Resource):
  """Send SMS/Get SMS/Delete SMS"""
  @auth.login_required
  def get(self):
    """Get SMS (GET)

    Header should contain:
      - (str, optional, default: All phone number) 'phone_number': Specific phone number to get SMS from
      - (int, optional, default: All timestamp) 'after_timestamp': Minimum timestamp (UTC) to get SMS from
      - (int, optional, default: No limit) 'limit': Maximum number of SMS to get

    return (json):
      - (bool) 'result': Request worked?
      - (list of sms) 'sms': List of all found SMS
      - (str, optional) 'error': Error explanation if request failed
    """
    _phone_number = request.headers.get('phone_number', default = None, type = str)
    _after_timestamp = request.headers.get('after_timestamp', default = None, type = int)
    _limit = request.headers.get('limit', default = None, type = int)
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      # Get all SMS from GSM module
      all_gsm_sms = gsm.getSMS()
      if all_gsm_sms:
        # Insert all GSM module SMS into the database
        for gsm_sms in all_gsm_sms:
          # TODO: Merge multipart SMS into one MMS before storing it into one entity in the database
          _timestamp = int(time.mktime(datetime.strptime(str(str(gsm_sms['date']) + " " + str(gsm_sms['time'].split(' ')[0])), "%y/%m/%d %H:%M:%S").timetuple()))
          api_database.insertSMS(timestamp=_timestamp, received=True, phone_number=gsm_sms['phone_number'], content=gsm_sms['sms_encoded'])
        # Delete all SMS from the module (because they are stored in the database)
        gsm.deleteSMS()
      # Return all SMS following the right pattern
      res, all_db_sms = api_database.getSMS(phone_number=_phone_number, after_timestamp=_after_timestamp, limit=_limit)
      if res:
        return {"result": True, "sms": all_db_sms}
      else:
        return {"result": False, "error": "Failed to get SMS from database"}
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def post(self):
    """Send SMS (POST)

    Header should contain:
      - (str) 'phone_number': Phone number to send the SMS
      - (str) 'content': Content of the SMS (in utf-8 or hexa depending on other parameters)
      - (bool, optional, default: False) 'is_content_in_hexa_format': Is content in hexadecimal format?

    return (json):
      - (bool) 'result': Request worked?
      - (bool) 'status': SMS sent?
      - (str, optional) 'error': Error explanation if request failed
    """
    _phone_number = request.headers.get('phone_number', default = None, type = str)
    if _phone_number == None:
      return {"result": False, "error": "Please specify a phone number (phone_number)"}
    _content = request.headers.get('content', default = None, type = str)
    if _content == None:
      return {"result": False, "error": "Please specify a SMS content (content)"}
    _is_in_hexa_format = request.headers.get('is_content_in_hexa_format', default = "false", type = str)
    _is_in_hexa_format = checkBoolean(_is_in_hexa_format)
    valid_gsm, gsm, error = getGSM()
    if valid_gsm:
      if _is_in_hexa_format:
        try:
          _content = bytearray.fromhex(_content).decode('utf-8')
        except (AttributeError, UnicodeEncodeError, UnicodeDecodeError):
          return {"result": False, "error": "Failed to decode content"}
      status_send_sms = gsm.sendSMS(_phone_number, _content)
      if status_send_sms:
        if not api_database.insertSMS(timestamp=int(time.time()), received=False, phone_number=str(_phone_number), content=str(binascii.hexlify(_content.encode()).decode())):
          logging.warning("Failed to insert sent SMS into the database")
      return {"result": True, "status": status_send_sms}
    else:
      return {"result": False, "error": error}
  @auth.login_required
  def delete(self):
    """Delete SMS (DELETE)

    Header should contain:
      - (int, optional, default: All ID) 'id': ID to delete
      - (str, optional, default: All phone numbers) 'phone_number': Phone number to delete
      - (int, optional, default: All timestamp) 'before_timestamp': Timestamp (UTC) before it should be deleted

    return (json):
      - (bool) 'result': Request worked?
      - (int) 'count': Number of deleted SMS
      - (str, optional) 'error': Error explanation if request failed
    """
    _id = request.headers.get('id', default = None, type = int)
    _phone_number = request.headers.get('phone_number', default = None, type = str)
    _before_timestamp = request.headers.get('before_timestamp', default = None, type = int)
    result, count_deleted = api_database.deleteSMS(id=_id, phone_number=_phone_number, before_timestamp=_before_timestamp)
    if result:
      return {"result": True, "count": int(count_deleted)}
    else:
      return {"result": False, "error": "Failed to delete all SMS from database"}

api.add_resource(Call, '/call')
api.add_resource(Ping, '/ping')
api.add_resource(Sms, '/sms')
api.add_resource(Date, '/date')


# ---- Launch application ----
if __name__ == '__main__':
  app.run(port=http_port, debug=use_debug)