import os  
f = open('core/db.py', encoding='utf-8').read()  
open('db_copy.txt','w',encoding='utf-8').write(f)  
print('OK')  
