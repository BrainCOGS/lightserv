import json
import pyperclip

def getKeys(val, old="$"):
    if isinstance(val, dict):
        for k in val.keys():
            getKeys(val[k], old + "." + str(k))
    elif isinstance(val, list):
        for i,k in enumerate(val):
            getKeys(k, old + "." + str(i))
    else:
        print("{} : {}".format(old,str(val)))

data = json.loads(pyperclip.paste())
getKeys(data)