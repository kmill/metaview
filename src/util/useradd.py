# useradd.py
# a command-line utility for adding users to the metaview database.

import pymongo
import sys
import getpass
import hashlib

DATABASE_NAME = "metaview"

if len(sys.argv) != 2 :
    print "Usage: python useradd.py username"
    exit(1)

username = sys.argv[1].strip()

try :
    password1 = getpass.getpass("Password: ")
    password2 = getpass.getpass("Retype password: ")
except getpass.GetPassWarning :
    print "\nYour terminal is echoing the password."

if password1 != password2 :
    print "Passwords do not match."
    exit(1)

try :
    blob_base = raw_input("Blob base ["+username+"]: ").strip()
except KeyboardInterrupt :
    print
    exit(1)

if not blob_base :
    blob_base = username

user_entry = { "username" : username,
               "password" : hashlib.md5(password1).hexdigest(),
               "blob_base" : blob_base }

db = pymongo.Connection()[DATABASE_NAME]
db["users"].ensure_index("username", unique=True)
db["users"].insert(user_entry)

print "User added."
